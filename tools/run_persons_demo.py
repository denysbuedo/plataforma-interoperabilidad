# ruff: noqa: E501 - embedded demo HTML/JS is served as an unprocessed template.
"""Run a loopback-only PER-002 web demo with a synthetic operator and test data."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import secrets
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import uvicorn
from alembic import command
from alembic.config import Config
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

PLATFORM_ROOT = Path(__file__).resolve().parents[1]
ISSUER = "https://identity.per002-demo.invalid/realms/local"
AUDIENCE = "mes-api"
DELEGATION_ISSUER = "https://platform.per002-demo.invalid/persons-delegation"
DELEGATION_AUDIENCE = "registro-personas"
DEMO_ROLES = [
    "persons.read",
    "persons.register",
    "persons.review",
    "persons.link",
]
_SOURCE_ALIAS = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)*$")


def _validate_test_database(value: str):
    try:
        url = make_url(value)
    except Exception:
        raise ValueError("Use only the dedicated local per001_test database") from None
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.database != "per001_test"
        or url.query
    ):
        raise ValueError("Use only the dedicated local per001_test database")
    return url


def _token(private_key, source_system: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "synthetic-per002-operator",
            "azp": "interoperabilidad-admin",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "realm_access": {"roles": [*DEMO_ROLES, f"persons.source.{source_system}"]},
        },
        private_key,
        algorithm="RS256",
    )


def create_demo_app(
    service_root: Path,
    database_url: str,
    source_system: str = "demo",
    source_entity: str = "fixture",
):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    service_root = service_root.resolve(strict=True)
    if not (service_root / "src/registro_personas/api.py").is_file():
        raise ValueError("Expected the independent registro-personas source tree")
    sys.path.insert(0, str(service_root / "src"))
    from mes_common import security as platform_security
    from mes_person_service import operator
    from mes_person_service.main import app
    from registro_personas.api import create_app as create_person_app
    from registro_personas.db import _engine_for, get_session

    base_url = _validate_test_database(database_url)
    if any(
        not value or len(value) > 64 or not _SOURCE_ALIAS.fullmatch(value)
        for value in (source_system, source_entity)
    ):
        raise ValueError("Use valid lowercase source aliases for the local demo")
    schema = "per002_demo_" + secrets.token_hex(6)
    if not re.fullmatch(r"per002_demo_[0-9a-f]{12}", schema):
        raise ValueError("Invalid temporary demo schema")

    operator_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    delegation_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    temporary_keys = tempfile.TemporaryDirectory(prefix="per002-demo-key-")
    delegation_public_key_path = Path(temporary_keys.name) / "delegation-public.pem"
    delegation_private_key_path = Path(temporary_keys.name) / "delegation-private.pem"
    delegation_public_key_path.write_bytes(
        delegation_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    delegation_private_key_path.write_bytes(
        delegation_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    admin_engine = create_engine(base_url, hide_parameters=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped_url = base_url.set(query={"options": f"-csearch_path={schema}"})
    migration_engine = create_engine(
        base_url,
        hide_parameters=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        with migration_engine.begin() as connection:
            config = Config(str(service_root / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    except Exception:
        migration_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()
        temporary_keys.cleanup()
        raise
    migration_engine.dispose()

    os.environ["REGISTRY_DATABASE_URL"] = scoped_url.render_as_string(hide_password=False)
    os.environ["REGISTRY_DELEGATION_ISSUER"] = DELEGATION_ISSUER
    os.environ["REGISTRY_DELEGATION_AUDIENCE"] = DELEGATION_AUDIENCE
    os.environ["REGISTRY_DELEGATION_KEY_ID"] = "per002-demo"
    os.environ["REGISTRY_DELEGATION_PUBLIC_KEY_FILE"] = str(delegation_public_key_path)
    os.environ.pop("REGISTRY_DELEGATION_JWKS_URL", None)
    os.environ["PERSONS_DELEGATION_ISSUER"] = DELEGATION_ISSUER
    os.environ["PERSONS_DELEGATION_AUDIENCE"] = DELEGATION_AUDIENCE
    os.environ["PERSONS_DELEGATION_KEY_ID"] = "per002-demo"
    os.environ["PERSONS_DELEGATION_PRIVATE_KEY_FILE"] = str(delegation_private_key_path)
    os.environ["PERSONS_DELEGATION_TTL_SECONDS"] = "60"
    policy_path = Path(temporary_keys.name) / "authorization-policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "operators": [
                    {
                        "issuer": ISSUER,
                        "subject": "synthetic-per002-operator",
                        "permissions": [
                            "persons.read",
                            "persons.register",
                            "persons.review",
                            "persons.link",
                        ],
                        "sources": [source_system],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    os.environ["PERSONS_AUTHORIZATION_POLICY_FILE"] = str(policy_path)
    os.environ["REGISTRY_PERSONS_URL"] = "http://127.0.0.1:8013"
    _engine_for.cache_clear()
    from registro_personas.security import _verifier

    _verifier.cache_clear()
    platform_security._issuer = ISSUER
    platform_security._pinned_public_key = operator_key.public_key()
    platform_security._settings.oidc_audience = AUDIENCE
    from mes_common.settings import get_settings

    persons_settings = get_settings("person-service")
    persons_settings.persons_oidc_issuer_url = ISSUER
    persons_settings.persons_oidc_client_id = "interoperabilidad-admin"
    persons_settings.persons_oidc_redirect_uri = "http://127.0.0.1:8003/admin/personas"

    person_app = create_person_app()

    def local_session():
        engine = _engine_for(os.environ["REGISTRY_DATABASE_URL"])
        with Session(engine, expire_on_commit=False) as session:
            yield session

    person_app.dependency_overrides[get_session] = local_session
    real_async_client = operator.httpx.AsyncClient
    operator.httpx.AsyncClient = lambda **kwargs: real_async_client(
        transport=operator.httpx.ASGITransport(app=person_app), **kwargs
    )

    @app.post("/_demo/login", include_in_schema=False)
    def demo_login(request: Request):
        host = request.client.host if request.client else ""
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = False
        if not local:
            raise HTTPException(status_code=404)
        return {
            "access_token": _token(operator_key, source_system),
            "token_type": "Bearer",
        }

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def demo_home():
        page = (
            _DEMO_HTML.replace("__SOURCE_SYSTEM_ATTR__", source_system)
            .replace("__SOURCE_ENTITY_ATTR__", source_entity)
            .replace("__SOURCE_SYSTEM_JSON__", json.dumps(source_system))
            .replace("__SOURCE_ENTITY_JSON__", json.dumps(source_entity))
        )
        return HTMLResponse(
            page,
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": (
                    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                    "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
                ),
                "Referrer-Policy": "no-referrer",
            },
        )

    def cleanup() -> None:
        operator.httpx.AsyncClient = real_async_client
        _engine_for.cache_clear()
        admin_engine.dispose()
        with create_engine(base_url, hide_parameters=True).begin() as connection:
            if re.fullmatch(r"per002_demo_[0-9a-f]{12}", schema):
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        temporary_keys.cleanup()

    return app, cleanup


_DEMO_HTML = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Demo local · Registro de Personas</title><style>
:root{font:16px/1.5 system-ui;color:#172536;background:#f3f6fa}body{margin:0}main{max-width:960px;margin:4vh auto;padding:20px}.card{background:white;padding:24px;border:1px solid #d8e1eb;border-radius:12px;margin:16px 0}h1{margin:0}.notice{padding:14px;background:#fff4dc;border-left:4px solid #d08a19}.muted{color:#596a7a}.bar,.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap;justify-content:space-between}form{display:grid;gap:10px;max-width:620px}input,button{font:inherit;padding:10px;border:1px solid #b7c5d3;border-radius:6px}button{background:#075db5;color:white;border:0;cursor:pointer}.secondary{background:white;color:#075db5;border:1px solid #b7c5d3}.result{padding:12px;background:#f4f7fa;border-radius:6px;overflow-wrap:anywhere;white-space:pre-wrap}[hidden]{display:none!important}
</style></head><body><main><div class="bar"><div><p class="muted">Entorno aislado · solo datos ficticios</p><h1>Registro Institucional de Personas</h1></div><button id="login">Entrar como operador ficticio</button><button id="logout" class="secondary" hidden>Salir</button></div>
<p class="notice">Esta página firma un token sintético temporal. No autentica con Keycloak ni representa una cuenta real. Las rutas de plataforma y Registro verifican el token y los permisos normalmente.</p><p id="status" role="status" class="muted">Entra para comenzar la prueba.</p>
<section id="workspace" hidden><section class="card"><h2>Buscar persona</h2><form id="search"><label>person_id<input name="person_id" placeholder="UUID institucional"></label><p class="muted">O busca una referencia exacta de origen:</p><div class="row"><input name="system" value="__SOURCE_SYSTEM_ATTR__" required><input name="entity" value="__SOURCE_ENTITY_ATTR__" required><input name="external_id" placeholder="Referencia ficticia" maxlength="200"></div><button id="search-button" type="button">Buscar</button></form><div id="person" class="result" hidden></div></section>
<section class="card"><h2>Registrar persona</h2><form id="create"><label>Nombre ficticio<input name="display_name" required maxlength="200"></label><label>Referencia ficticia<input name="external_id" required maxlength="200"></label><button id="create-button">Registrar</button></form><p id="create-result" class="result" role="status" aria-live="polite" hidden></p></section>
<section class="card"><div class="bar"><h2>Colisiones para revisión</h2><button id="refresh" class="secondary">Actualizar</button></div><div id="reviews" class="result"></div></section></section></main>
<script>
let bearer='';const $=id=>document.getElementById(id),status=m=>$('status').textContent=m;
async function api(path,options={}){const response=await fetch(path,{...options,headers:{Authorization:'Bearer '+bearer,'Content-Type':'application/json',...(options.headers||{})},cache:'no-store'});const data=await response.json().catch(()=>({}));if(!response.ok){if(response.status===401)throw Error('La sesión ficticia venció. Vuelve a entrar como operador.');if(response.status===403)throw Error('La demo solo autoriza sistema «demo». Mantén sistema demo y entidad fixture.');if(response.status===409)throw Error('La referencia ya existe en otra persona; requiere revisión manual. No se fusionó ningún registro.');throw Error(data.detail||data.title||'Acceso denegado ('+response.status+')')}return data}
$('login').onclick=async()=>{try{const answer=await fetch('/_demo/login',{method:'POST'}).then(r=>r.json());bearer=answer.access_token;$('workspace').hidden=false;$('login').hidden=true;$('logout').hidden=false;status('Operador ficticio autenticado. El backend valida el JWT en cada solicitud.')}catch(e){status(e.message)}};
$('logout').onclick=()=>{bearer='';$('workspace').hidden=true;$('login').hidden=false;$('logout').hidden=true;status('Acceso local cerrado.')};
function showPerson(person,refs=[]){const box=$('person');box.replaceChildren();box.hidden=false;const heading=document.createElement('strong');heading.textContent=person.display_name+' · '+person.person_id;box.append(heading);for(const ref of refs){const row=document.createElement('p');row.textContent='Origen autorizado: '+ref.system+'/'+ref.entity+' · '+ref.external_id;box.append(row)}const section=document.createElement('section');section.innerHTML='<h3>Vincular otra referencia de origen</h3><p class="muted">Entorno local con datos ficticios. Escribe un identificador de prueba nuevo.</p><form id="link-reference"><label>Sistema<input name="system" value="__SOURCE_SYSTEM_ATTR__" readonly required></label><label>Entidad<input name="entity" value="__SOURCE_ENTITY_ATTR__" readonly required></label><label>Referencia nueva<input name="external_id" placeholder="demo-ref-003" required maxlength="200"></label><button type="button">Vincular referencia</button></form><p id="link-status" class="muted" role="status"></p>';box.append(section);const form=section.querySelector('form'),button=form.querySelector('button');button.onclick=async event=>{event.preventDefault();const fields=new FormData(form),now=new Date(),source={system:fields.get('system'),entity:fields.get('entity'),external_id:fields.get('external_id')};try{await api('/api/v1/personas/'+person.person_id+'/referencias',{method:'POST',body:JSON.stringify({source,provenance:{system:source.system,evidence_ref:crypto.randomUUID(),observed_at:now.toISOString()}})});const refs=await api('/api/v1/personas/'+person.person_id+'/referencias');showPerson(person,refs);status('Referencia vinculada y auditada.')}catch(e){section.querySelector('#link-status').textContent=e.message}};form.onsubmit=event=>{event.preventDefault();button.click()}}
const searchForm=$('search'),searchButton=$('search-button');const runSearch=async()=>{$('person').replaceChildren();$('person').hidden=true;try{const form=new FormData(searchForm),id=form.get('person_id');const person=id?await api('/api/v1/personas/'+encodeURIComponent(id)):await api('/api/v1/personas/referencias/resolver?'+new URLSearchParams({system:form.get('system'),entity:form.get('entity'),external_id:form.get('external_id')}));const refs=await api('/api/v1/personas/'+person.person_id+'/referencias');showPerson(person,refs);status('Consulta completada y auditada.')}catch(e){status(e.message)}};searchButton.onclick=runSearch;searchForm.onsubmit=event=>{event.preventDefault();searchButton.click()};
async function refreshReviews(){const result=await api('/api/v1/personas/revisiones');$('reviews').textContent=result.items.length?result.items.map(item=>item.kind+' · '+item.case_id+' · '+new Date(item.created_at).toLocaleString()).join('\n'):'Sin colisiones pendientes.';return result.items.length}
$('create').onsubmit=async event=>{event.preventDefault();const button=$('create-button'),message=$('create-result');button.disabled=true;message.hidden=true;try{const form=new FormData(event.target),now=new Date(),source={system:__SOURCE_SYSTEM_JSON__,entity:__SOURCE_ENTITY_JSON__,external_id:form.get('external_id')};const person=await api('/api/v1/personas',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({display_name:form.get('display_name'),source,provenance:{system:source.system,evidence_ref:crypto.randomUUID(),observed_at:now.toISOString()}})});showPerson(person,[source]);status('Persona registrada. person_id: '+person.person_id);message.textContent='Registro creado. person_id: '+person.person_id;message.hidden=false;event.target.reset()}catch(e){status(e.message);message.textContent=e.message+' No se creó ni fusionó otra persona.';message.hidden=false;if(e.message.includes('referencia ya existe')){try{const count=await refreshReviews();message.textContent=e.message+' Se añadió un caso a revisión. Casos visibles: '+count+'.'}catch(_){}}}finally{button.disabled=false}};
$('refresh').onclick=async()=>{try{const count=await refreshReviews();status('Revisiones consultadas y auditadas: '+count+'.')}catch(e){status(e.message)}};
</script></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Loopback-only PER-002 fictional-data web demo")
    parser.add_argument("--service-root", type=Path, required=True)
    parser.add_argument("--database-url", default=os.environ.get("REGISTRY_TEST_DATABASE_URL", ""))
    parser.add_argument("--port", type=int, default=8085)
    parser.add_argument("--source-system", default="demo")
    parser.add_argument("--source-entity", default="fixture")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    app, cleanup = create_demo_app(
        args.service_root,
        args.database_url,
        source_system=args.source_system,
        source_entity=args.source_entity,
    )
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    finally:
        cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
