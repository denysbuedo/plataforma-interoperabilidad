# ruff: noqa: E501 - the embedded HTML/JS template is intentionally an unprocessed string.
"""Operator-only UI and delegated authorization proxy to Person Registry."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from ipaddress import ip_address
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2AuthorizationCodeBearer
from mes_common.problem import ProblemDetails
from mes_common.security import Principal, decode_access_token
from mes_common.settings import get_settings
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from mes_person_service.authorization import authorize_operator
from mes_person_service.delegation import _signing_config, issue_delegation

router = APIRouter()
_settings = get_settings("person-service")
_persons_docs_issuer = (_settings.persons_oidc_issuer_url or _settings.oidc_issuer_url).rstrip("/")
persons_oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{_persons_docs_issuer}/protocol/openid-connect/auth",
    tokenUrl=f"{_persons_docs_issuer}/protocol/openid-connect/token",
    scopes={"openid": "Authenticate the operator"},
)
_security_logger = logging.getLogger("mes.persons.security")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

Alias = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)*$", max_length=64)
]
_SAFE_HOST = re.compile(r"^[A-Za-z0-9.-]+$")


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: Alias | None = None
    source_entity_type: Alias | None = None
    source_record_id: str | None = Field(default=None, min_length=1, max_length=200)
    system: Alias | None = None
    entity: Alias | None = None
    external_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def normalize_aliases(self):
        values = (
            ("source_system", "system"),
            ("source_entity_type", "entity"),
            ("source_record_id", "external_id"),
        )
        for canonical, legacy in values:
            new, old = getattr(self, canonical), getattr(self, legacy)
            if new is not None and old is not None and new != old:
                raise ValueError(f"conflicting {canonical} and legacy alias")
            if new is None and old is None:
                raise ValueError(f"{canonical} is required")
            setattr(self, canonical, new if new is not None else old)
        return self

    @field_validator("external_id", "source_record_id")
    @classmethod
    def opaque_reference(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value != value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("invalid reference")
        return value

    @property
    def registry_payload(self) -> dict[str, str]:
        return {
            "system": self.source_system,
            "entity": self.source_entity_type,
            "external_id": self.source_record_id,
        }


class SourceReferenceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: Alias
    source_entity_type: Alias
    source_record_id: str = Field(min_length=1, max_length=200)


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: Alias
    evidence_ref: UUID
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone required")
        return value


class SourceReferenceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: SourceReference
    provenance: Provenance

    @model_validator(mode="after")
    def provenance_matches_source(self):
        if self.source.source_system != self.provenance.system:
            raise ValueError("provenance system must match source system")
        return self


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int = Field(ge=400, le=599)
    correlation_id: UUID


def _operator_error_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {
            "application/json": {"schema": ProblemDetails.model_json_schema(by_alias=True)},
            "application/problem+json": {"schema": Problem.model_json_schema()},
        },
    }


def _canonical_registry_payload(value: Any) -> Any:
    """Translate only Registry's source-reference shape; preserve provenance.system."""
    if isinstance(value, list):
        return [_canonical_registry_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _canonical_registry_payload(item) for key, item in value.items()}
    if {"system", "entity", "external_id"} <= result.keys():
        result["source_system"] = result.pop("system")
        result["source_entity_type"] = result.pop("entity")
        result["source_record_id"] = result.pop("external_id")
    return result


def _json_script_value(value: str) -> str:
    return (
        json.dumps(value, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _roles(principal: Principal, *required: str) -> None:
    if not set(required).issubset(principal.roles):
        _log_denial(principal, "|".join(required))
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _has_source_role(principal: Principal, source: str) -> bool:
    return f"persons.source.{source}" in principal.roles


def _persons_oidc_config() -> tuple[str, str, str]:
    issuer = _settings.persons_oidc_issuer_url
    client = _settings.persons_oidc_client_id
    callback = _settings.persons_oidc_redirect_uri
    if not issuer or not client or not callback:
        raise HTTPException(
            status_code=503, detail="Person operator authentication is not configured"
        )
    _signing_config()
    try:
        callback_parts = urlsplit(callback)
        issuer_parts = urlsplit(issuer)
    except ValueError:
        raise HTTPException(
            status_code=503, detail="Person operator authentication is not configured"
        ) from None
    callback_host = callback_parts.hostname or ""
    try:
        callback_loopback = callback_host == "localhost" or ip_address(callback_host).is_loopback
    except ValueError:
        callback_loopback = False
    callback_secure = callback_parts.scheme == "https" or (
        callback_parts.scheme == "http" and callback_loopback
    )
    try:
        issuer_port_valid = issuer_parts.port is None or 1 <= issuer_parts.port <= 65535
    except ValueError:
        issuer_port_valid = False
    if (
        issuer_parts.scheme != "https"
        or not issuer_parts.hostname
        or not _SAFE_HOST.fullmatch(issuer_parts.hostname)
        or "*" in issuer
        or not issuer_port_valid
        or issuer_parts.username
        or issuer_parts.password
        or issuer_parts.query
        or issuer_parts.fragment
        or not callback_secure
        or not callback_parts.hostname
        or not _SAFE_HOST.fullmatch(callback_parts.hostname)
        or "*" in callback
        or callback_parts.path != "/admin/personas"
        or callback_parts.query
        or callback_parts.fragment
        or callback_parts.username
        or callback_parts.password
    ):
        raise HTTPException(
            status_code=503, detail="Person operator authentication is not configured"
        )
    return issuer.rstrip("/"), client, callback


async def persons_operator_principal(
    token: Annotated[str, Depends(persons_oauth2_scheme)],
) -> Principal:
    issuer, client_id, _callback = _persons_oidc_config()
    principal = decode_access_token(
        token,
        issuer=issuer,
        audience=_settings.oidc_audience,
        authorized_party=client_id,
    )
    return authorize_operator(principal)


def _log_denial(principal: Principal, permission: str) -> None:
    issuer = str(principal.claims.get("iss", ""))
    actor_id = uuid5(NAMESPACE_URL, f"{issuer}\x00{principal.subject}")
    _security_logger.warning("authorization_denied actor_id=%s permission=%s", actor_id, permission)


def _upstream_base() -> str:
    base = os.environ.get("REGISTRY_PERSONS_URL", "http://127.0.0.1:8013").rstrip("/")
    parsed = None
    port = None
    try:
        parsed = urlsplit(base)
        host = parsed.hostname or ""
        loopback = host == "localhost" or ip_address(host).is_loopback
        port = parsed.port
    except ValueError:
        loopback = False
    if (
        parsed is None
        or parsed.scheme != "http"
        or port is None
        or not loopback
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path
    ):
        raise HTTPException(status_code=503, detail="Person service unavailable")
    return base


async def _forward(
    method: str,
    path: str,
    principal: Principal,
    request: Request,
    *,
    body: Any = None,
    params: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    permissions: set[str],
    sources: set[str] | None = None,
) -> Response:
    token = issue_delegation(principal, permissions=permissions, sources=sources or set())
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": str(request.state.correlation_id),
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        async with httpx.AsyncClient(
            timeout=8.0, follow_redirects=False, trust_env=False
        ) as client:
            result = await client.request(
                method,
                f"{_upstream_base()}{path}",
                headers=headers,
                json=body,
                params=params,
            )
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="Person service unavailable") from None
    media_type = result.headers.get("content-type", "application/json").split(";", 1)[0]
    if media_type not in {"application/json", "application/problem+json"}:
        raise HTTPException(status_code=502, detail="Invalid person service response")
    try:
        content = json.dumps(
            _canonical_registry_payload(result.json()), separators=(",", ":")
        ).encode()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="Invalid person service response") from None
    return Response(
        content=content,
        status_code=result.status_code,
        media_type=media_type,
        headers={
            "X-Correlation-ID": str(request.state.correlation_id),
            "Cache-Control": "no-store",
        },
    )


@router.get("/admin/personas", response_class=HTMLResponse, include_in_schema=False)
async def persons_admin() -> HTMLResponse:
    issuer, client_id, callback = _persons_oidc_config()
    issuer_origin = f"{urlsplit(issuer).scheme}://{urlsplit(issuer).netloc}"
    page = (
        _ADMIN_HTML.replace("__ISSUER_JSON__", _json_script_value(issuer))
        .replace("__CLIENT_ID_JSON__", _json_script_value(client_id))
        .replace("__CALLBACK_JSON__", _json_script_value(callback))
    )
    return HTMLResponse(
        page,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                f"connect-src 'self' {issuer_origin}; img-src 'self' data:; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'self'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/api/v1/personas")
async def list_people(
    request: Request,
    principal: Annotated[Principal, Depends(persons_operator_principal)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> Response:
    _roles(principal, "persons.read")
    return await _forward(
        "GET",
        "/v1/personas",
        principal,
        request,
        params={"limit": limit, "offset": offset},
        permissions={"persons.list", "persons.read"},
        sources={
            r.removeprefix("persons.source.")
            for r in principal.roles
            if r.startswith("persons.source.")
        },
    )


@router.post("/api/v1/personas", status_code=201)
async def create_person(
    data: Annotated[dict[str, Any], Body()],
    request: Request,
    principal: Annotated[Principal, Depends(persons_operator_principal)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> Response:
    _roles(principal, "persons.register")
    source = data.get("source")
    source_system = (
        (source.get("source_system") or source.get("system")) if isinstance(source, dict) else None
    )
    if not isinstance(source_system, str) or not _has_source_role(principal, source_system):
        _log_denial(principal, "persons.source")
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        source_input = SourceReference.model_validate(source)
        provenance = Provenance.model_validate(data.get("provenance"))
        if provenance.system != source_input.source_system:
            raise ValueError("provenance system must match source system")
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid person source or provenance") from None
    registry_body = {**data, "source": source_input.registry_payload}
    return await _forward(
        "POST",
        "/v1/personas",
        principal,
        request,
        body=registry_body,
        idempotency_key=str(idempotency_key),
        permissions={"persons.create"},
        sources={source_system},
    )


@router.get("/api/v1/personas/referencias/resolver")
async def resolve_reference(
    request: Request,
    principal: Annotated[Principal, Depends(persons_operator_principal)],
    source_system: Alias | None = None,
    source_entity_type: Alias | None = None,
    source_record_id: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    system: Alias | None = None,
    entity: Alias | None = None,
    external_id: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> Response:
    _roles(principal, "persons.read")
    values = (
        (source_system, system),
        (source_entity_type, entity),
        (source_record_id, external_id),
    )
    if any(a is not None and b is not None and a != b for a, b in values) or any(
        a is None and b is None for a, b in values
    ):
        raise HTTPException(status_code=422, detail="Invalid source reference")
    source_system, source_entity_type, source_record_id = tuple(
        a if a is not None else b for a, b in values
    )
    if not _has_source_role(principal, source_system):
        _log_denial(principal, "persons.source")
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return await _forward(
        "GET",
        "/v1/referencias/resolver",
        principal,
        request,
        params={
            "system": source_system,
            "entity": source_entity_type,
            "external_id": source_record_id,
        },
        permissions={"persons.read"},
        sources={source_system},
    )


@router.get("/api/v1/personas/revisiones")
async def list_reviews(
    request: Request,
    principal: Annotated[Principal, Depends(persons_operator_principal)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> Response:
    _roles(principal, "persons.review")
    return await _forward(
        "GET",
        "/v1/revisiones",
        principal,
        request,
        params={"limit": limit, "offset": offset},
        permissions={"persons.review"},
        sources={
            r.removeprefix("persons.source.")
            for r in principal.roles
            if r.startswith("persons.source.")
        },
    )


@router.get("/api/v1/personas/{person_id}/referencias")
async def person_references(
    person_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(persons_operator_principal)],
) -> Response:
    _roles(principal, "persons.read")
    return await _forward(
        "GET",
        f"/v1/personas/{person_id}/referencias",
        principal,
        request,
        permissions={"persons.read"},
        sources={
            r.removeprefix("persons.source.")
            for r in principal.roles
            if r.startswith("persons.source.")
        },
    )


@router.post(
    "/api/v1/personas/{person_id}/referencias",
    status_code=201,
    response_model=SourceReferenceView,
    responses={
        200: {"model": SourceReferenceView, "description": "Referencia ya vinculada al destino"},
        401: _operator_error_response("Falta token o token no válido"),
        403: _operator_error_response("Permisos insuficientes para la persona o fuente"),
        404: _operator_error_response("Persona inexistente o no consultable"),
        409: {
            "description": "Conflicto de referencia pendiente de revisión",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema()}},
        },
        422: _operator_error_response("Solicitud inválida"),
        503: _operator_error_response("Registro de Personas no disponible"),
    },
    openapi_extra={
        "x-required-roles": [
            "persons.read",
            "persons.review",
            "persons.link",
            "persons.source.<alias>",
        ],
        "x-resource-authorization": "El operador debe poder consultar el person_id seleccionado",
    },
)
async def add_person_reference(
    person_id: UUID,
    data: Annotated[SourceReferenceLink, Body()],
    request: Request,
    principal: Annotated[Principal, Depends(persons_operator_principal)],
) -> Response:
    _roles(principal, "persons.read", "persons.review", "persons.link")
    if not _has_source_role(principal, data.source.source_system):
        _log_denial(principal, "persons.source")
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return await _forward(
        "POST",
        f"/v1/personas/{person_id}/referencias",
        principal,
        request,
        body={
            "source": data.source.registry_payload,
            "provenance": {
                "system": data.provenance.system,
                "evidence_ref": str(data.provenance.evidence_ref),
                "observed_at": data.provenance.observed_at.isoformat(),
            },
        },
        permissions={"persons.read", "persons.review", "persons.references.link"},
        sources={data.source.source_system},
    )


@router.get("/api/v1/personas/{person_id}")
async def get_person(
    person_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(persons_operator_principal)],
) -> Response:
    _roles(principal, "persons.read")
    return await _forward(
        "GET",
        f"/v1/personas/{person_id}",
        principal,
        request,
        permissions={"persons.read"},
        sources={
            r.removeprefix("persons.source.")
            for r in principal.roles
            if r.startswith("persons.source.")
        },
    )


_ADMIN_HTML = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Personas · Administración</title><style>
:root{font:16px/1.5 system-ui;color:#172536;background:#f3f6fa}body{margin:0}main{max-width:960px;margin:4vh auto;padding:20px}.card{background:white;padding:24px;border:1px solid #d8e1eb;border-radius:12px;margin:16px 0}h1{margin:0}p,.hint{color:#596a7a}.bar{display:flex;gap:12px;align-items:center;justify-content:space-between}form{display:grid;gap:10px;max-width:620px}input,button{font:inherit;padding:10px;border:1px solid #b7c5d3;border-radius:6px}button{background:#075db5;color:white;border:0;cursor:pointer}button.secondary{background:white;color:#075db5;border:1px solid #b7c5d3}.row{display:flex;gap:8px;flex-wrap:wrap}.status{white-space:pre-wrap}.result{padding:12px;background:#f4f7fa;border-radius:6px;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #e2e8ef;padding:8px} [hidden]{display:none!important}
</style></head><body><main><div class="bar"><div><p>Administración institucional</p><h1>Registro de Personas</h1></div><button id="login">Iniciar sesión institucional</button><button id="logout" class="secondary" hidden>Salir del módulo</button></div>
<p id="identity" class="hint">Inicia sesión para consultar o registrar personas.</p><p id="status" class="status" role="status"></p>
<section id="app" hidden>
<section class="card"><h2>Buscar persona</h2><form id="search"><label>person_id<input name="person_id" placeholder="UUID institucional"></label><p>O busca por referencia exacta de origen:</p><div class="row"><input name="system" placeholder="sistema" maxlength="64"><input name="entity" placeholder="entidad" maxlength="64"><input name="external_id" placeholder="referencia exacta" maxlength="200"></div><button>Buscar</button></form><div id="person" class="result" hidden></div></section>
<section class="card"><h2>Registrar persona</h2><form id="create"><label>Nombre institucional<input name="display_name" required maxlength="200"></label><label>Sistema de origen<input name="system" required maxlength="64"></label><label>Entidad de origen<input name="entity" required maxlength="64"></label><label>Referencia de origen<input name="external_id" required maxlength="200"></label><label>UUID de evidencia autorizada<input name="evidence_ref" required></label><label>Fecha observada (ISO 8601)<input name="observed_at" type="datetime-local" required></label><button>Registrar</button></form></section>
<section class="card"><div class="bar"><h2>Colisiones para revisión</h2><button id="refresh-reviews" class="secondary">Actualizar</button></div><div id="reviews"></div></section></section></main>
<script>
const issuer=__ISSUER_JSON__,clientId=__CLIENT_ID_JSON__,redirect=__CALLBACK_JSON__;let token='';
const $=id=>document.getElementById(id),status=m=>$('status').textContent=m;
function b64(bytes){return btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')}
async function discovery(){const d=await fetch(issuer+'/.well-known/openid-configuration',{cache:'no-store'}).then(r=>r.json()),base=new URL(issuer);if(d.issuer!==issuer)throw Error('Emisor OIDC no válido');for(const endpoint of [d.authorization_endpoint,d.token_endpoint,d.jwks_uri]){const u=new URL(endpoint);if(u.protocol!=='https:'||u.origin!==base.origin||!u.pathname.startsWith(base.pathname+'/'))throw Error('Configuración OIDC no válida')}return d}
async function login(){const verifier=b64(crypto.getRandomValues(new Uint8Array(32))),challenge=b64(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))),state=b64(crypto.getRandomValues(new Uint8Array(24))),nonce=b64(crypto.getRandomValues(new Uint8Array(24)));sessionStorage.setItem('pkce',JSON.stringify({verifier,state,nonce}));const d=await discovery();const u=new URL(d.authorization_endpoint);Object.entries({client_id:clientId,redirect_uri:redirect,response_type:'code',scope:'openid',code_challenge:challenge,code_challenge_method:'S256',state,nonce}).forEach(([k,v])=>u.searchParams.set(k,v));location.assign(u)}
function b64bytes(s){s=s.replace(/-/g,'+').replace(/_/g,'/');return Uint8Array.from(atob(s+'='.repeat((4-s.length%4)%4)),c=>c.charCodeAt(0))}
async function verifyIdToken(value,pending,d){const parts=value.split('.');if(parts.length!==3)throw Error('Token OIDC inválido');const head=JSON.parse(new TextDecoder().decode(b64bytes(parts[0]))),claims=JSON.parse(new TextDecoder().decode(b64bytes(parts[1])));if(head.alg!=='RS256'||!head.kid)throw Error('Firma OIDC no admitida');const jwks=await fetch(d.jwks_uri).then(r=>r.json()),jwk=jwks.keys.find(k=>k.kid===head.kid&&k.kty==='RSA'&&(!k.use||k.use==='sig'));if(!jwk)throw Error('Clave OIDC no disponible');const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);const valid=await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,b64bytes(parts[2]),new TextEncoder().encode(parts[0]+'.'+parts[1]));const aud=Array.isArray(claims.aud)?claims.aud:[claims.aud],now=Date.now()/1000;if(!valid||claims.iss!==issuer||!aud.includes(clientId)||claims.azp!==clientId||claims.nonce!==pending.nonce||typeof claims.exp!=='number'||!Number.isFinite(claims.exp)||claims.exp<=now||(claims.nbf!==undefined&&(typeof claims.nbf!=='number'||!Number.isFinite(claims.nbf)||claims.nbf>now))||typeof claims.iat!=='number'||!Number.isFinite(claims.iat)||claims.iat>now+60||typeof claims.sub!=='string'||!claims.sub)throw Error('Respuesta de autenticación OIDC inválida');}
async function callback(){const q=new URLSearchParams(location.search),code=q.get('code');if(q.has('error')){history.replaceState({},'',location.pathname);status('El proveedor no completó el inicio de sesión.');return}if(!code)return;const pending=JSON.parse(sessionStorage.getItem('pkce')||'null');sessionStorage.removeItem('pkce');history.replaceState({},'',location.pathname);if(!pending||q.get('state')!==pending.state)throw Error('Respuesta de autenticación inválida');const d=await discovery(),body=new URLSearchParams({grant_type:'authorization_code',client_id:clientId,code,redirect_uri:redirect,code_verifier:pending.verifier});const result=await fetch(d.token_endpoint,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body}).then(r=>r.json());if(!result.access_token||!result.id_token)throw Error('No se pudo completar el inicio de sesión');await verifyIdToken(result.id_token,pending,d);token=result.access_token;$('app').hidden=false;$('login').hidden=true;$('logout').hidden=false;$('identity').textContent='Sesión institucional activa';status('Identidad validada de nuevo por el backend en cada operación.');}
async function api(path,opts={}){const r=await fetch(path,{...opts,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json',...(opts.headers||{})},cache:'no-store'});const data=await r.json().catch(()=>({}));if(!r.ok){if(r.status===401)throw Error('La sesión institucional expiró. Inicia sesión nuevamente.');if(r.status===403)throw Error('No tienes permiso para consultar esta persona o usar la fuente seleccionada.');if(r.status===409)throw Error('Conflicto de referencia. Requiere revisión manual; no se fusionó ningún registro.');throw Error(data.detail||data.title||'Operación denegada ('+r.status+')')}return data}
function showPerson(p,refs=[]){$('person').hidden=false;$('person').replaceChildren();const title=document.createElement('strong');title.textContent=p.display_name+' · '+p.person_id;$('person').append(title);for(const ref of refs){const row=document.createElement('p');row.textContent=`Origen autorizado: ${ref.source_system||ref.system}/${ref.source_entity_type||ref.entity} · ${ref.source_record_id||ref.external_id}`;$('person').append(row)}const section=document.createElement('section');section.innerHTML='<h3>Vincular otra referencia de origen</h3><form id="link-reference"><label>Sistema<input name="system" required maxlength="64"></label><label>Entidad<input name="entity" required maxlength="64"></label><label>Referencia exacta<input name="external_id" required maxlength="200"></label><label>UUID de evidencia autorizada<input name="evidence_ref" required></label><label>Fecha observada (ISO 8601)<input name="observed_at" type="datetime-local" required></label><button type="button">Vincular referencia</button></form><p id="link-status" role="status"></p>';$('person').append(section);const form=section.querySelector('form'),button=form.querySelector('button');button.onclick=async e=>{e.preventDefault();status('Vinculando referencia…');const f=new FormData(form),source={system:f.get('system'),entity:f.get('entity'),external_id:f.get('external_id')},data={source,provenance:{system:source.system,evidence_ref:f.get('evidence_ref'),observed_at:new Date(f.get('observed_at')).toISOString()}};try{await api('/api/v1/personas/'+encodeURIComponent(p.person_id)+'/referencias',{method:'POST',body:JSON.stringify(data)});const updated=await api('/api/v1/personas/'+encodeURIComponent(p.person_id)+'/referencias');showPerson(p,updated);status('Referencia vinculada y auditada.')}catch(x){section.querySelector('#link-status').textContent=x.message;status(x.message)}};form.onsubmit=e=>{e.preventDefault();button.click()}}
$('login').onclick=()=>login().catch(e=>status(e.message));$('logout').onclick=()=>{token='';sessionStorage.removeItem('pkce');$('app').hidden=true;$('login').hidden=false;$('logout').hidden=true;$('identity').textContent='Acceso al módulo cerrado';status('')};
$('search').onsubmit=async e=>{e.preventDefault();$('person').replaceChildren();$('person').hidden=true;status('Buscando…');try{const f=new FormData(e.target),id=f.get('person_id');const p=id?await api('/api/v1/personas/'+encodeURIComponent(id)):await api('/api/v1/personas/referencias/resolver?'+new URLSearchParams({system:f.get('system'),entity:f.get('entity'),external_id:f.get('external_id')}));const refs=await api('/api/v1/personas/'+p.person_id+'/referencias');showPerson(p,refs);status('Consulta auditada.')}catch(x){status(x.message)}};
$('create').onsubmit=async e=>{e.preventDefault();status('Registrando…');try{const f=new FormData(e.target),source={system:f.get('system'),entity:f.get('entity'),external_id:f.get('external_id')},data={display_name:f.get('display_name'),source,provenance:{system:source.system,evidence_ref:f.get('evidence_ref'),observed_at:new Date(f.get('observed_at')).toISOString()}};const p=await api('/api/v1/personas',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify(data)});showPerson(p,[source]);status('Persona registrada. person_id: '+p.person_id);e.target.reset()}catch(x){status(x.message)}};
$('refresh-reviews').onclick=async()=>{try{const page=await api('/api/v1/personas/revisiones');const root=$('reviews');root.replaceChildren();const summary=document.createElement('p');summary.textContent=page.total+' colisión(es) pendientes. No se fusionan automáticamente.';root.append(summary);for(const item of page.items){const row=document.createElement('p');row.textContent=`${item.kind} · ${item.case_id} · ${new Date(item.created_at).toLocaleString()}`;root.append(row)}status('Lista de revisión consultada y auditada.')}catch(x){status(x.message)}};
callback().catch(e=>status(e.message));
</script></body></html>"""
