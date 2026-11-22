import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jwt.exceptions import InvalidAudienceError
from mes_common.security import Principal
from mes_person_service import operator
from mes_person_service.authorization import authorize_operator
from mes_person_service.delegation import _clear_signing_config
from mes_person_service.main import app


def _principal(roles):
    return Principal(
        subject="synthetic-operator-subject",
        username=None,
        roles=frozenset(roles),
        claims={
            "iss": "https://identity.example.invalid/realms/synthetic",
            "sub": "synthetic-operator-subject",
        },
    )


def _configure_ui():
    operator._settings.persons_oidc_issuer_url = operator._settings.oidc_issuer_url
    operator._settings.persons_oidc_client_id = "interoperabilidad-admin"
    operator._settings.persons_oidc_redirect_uri = "http://127.0.0.1:8003/admin/personas"


def _configure_delegation(monkeypatch, tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path = tmp_path / "delegation-private.pem"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    monkeypatch.setenv("PERSONS_DELEGATION_ISSUER", "https://platform.example.invalid/delegation")
    monkeypatch.setenv("PERSONS_DELEGATION_AUDIENCE", "registro-personas")
    monkeypatch.setenv("PERSONS_DELEGATION_KEY_ID", "synthetic-key-1")
    monkeypatch.setenv("PERSONS_DELEGATION_PRIVATE_KEY_FILE", str(key_path))
    monkeypatch.setenv("PERSONS_DELEGATION_TTL_SECONDS", "60")
    _clear_signing_config()
    return key


def test_admin_page_requires_explicit_oidc_configuration():
    operator._settings.persons_oidc_issuer_url = None
    operator._settings.persons_oidc_client_id = None
    operator._settings.persons_oidc_redirect_uri = None
    with TestClient(app) as client:
        assert client.get("/admin/personas").status_code == 503


def test_admin_page_uses_explicit_local_callback(monkeypatch, tmp_path):
    _configure_delegation(monkeypatch, tmp_path)
    _configure_ui()
    with TestClient(app) as client:
        response = client.get("/admin/personas")
    assert response.status_code == 200
    assert "http://127.0.0.1:8003/admin/personas" in response.text
    assert "redirect=location.origin" not in response.text
    assert "claims.azp!==clientId" in response.text
    assert "servidor rechazó la autenticación (401)" in response.text
    assert "claims.nbf!==undefined" in response.text


def test_persons_operator_uses_dedicated_issuer_and_client(monkeypatch, tmp_path):
    _configure_delegation(monkeypatch, tmp_path)
    issuer = "https://identidad.reduniv.edu.cu/realms/reduniv-institucional"
    client_id = "interoperabilidad-admin"
    operator._settings.oidc_issuer_url = "https://identidad.reduniv.edu.cu/realms/interoperabilidad"
    operator._settings.persons_oidc_issuer_url = issuer
    operator._settings.persons_oidc_client_id = client_id
    operator._settings.persons_oidc_redirect_uri = "https://persona.example.invalid/admin/personas"
    policy = tmp_path / "policy.json"
    policy.write_text(
        '{"operators":[{"issuer":"' + issuer + '","subject":"operator-1",'
        '"permissions":["persons.read"],"sources":["reduniv.conecta"]}]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PERSONS_AUTHORIZATION_POLICY_FILE", str(policy))
    principal = Principal(
        subject="operator-1",
        username=None,
        roles=frozenset(),
        claims={"iss": issuer, "sub": "operator-1", "azp": client_id},
    )
    observed = {}

    def decode(token, **kwargs):
        observed.update(token=token, **kwargs)
        return principal

    monkeypatch.setattr(operator, "decode_access_token", decode)
    try:
        request = SimpleNamespace(state=SimpleNamespace(correlation_id="correlation-123"))
        result = asyncio.run(operator.persons_operator_principal("synthetic-access-token", request))
        assert result.roles == frozenset({"persons.read", "persons.source.reduniv.conecta"})
        assert observed == {
            "token": "synthetic-access-token",
            "issuer": issuer,
            "audience": "mes-api",
        }
    finally:
        _clear_signing_config()


def test_rejected_operator_token_logs_only_safe_failure_stage(monkeypatch, tmp_path):
    _configure_delegation(monkeypatch, tmp_path)
    _configure_ui()
    logged = []
    monkeypatch.setattr(operator._security_logger, "warning", lambda *args: logged.append(args))

    def reject(_token, **_kwargs):
        raise HTTPException(status_code=401) from InvalidAudienceError(
            "synthetic-private-token-content"
        )

    monkeypatch.setattr(operator, "decode_access_token", reject)
    request = SimpleNamespace(state=SimpleNamespace(correlation_id="correlation-456"))
    with pytest.raises(HTTPException):
        asyncio.run(operator.persons_operator_principal("synthetic-access-token", request))

    assert logged == [
        (
            "persons_operator_authentication_rejected correlation_id=%s stage=%s",
            "correlation-456",
            "audience",
        )
    ]
    assert "synthetic-access-token" not in repr(logged)
    assert "synthetic-private-token-content" not in repr(logged)
    _clear_signing_config()


def test_no_token_is_denied_before_proxy():
    with TestClient(app) as client:
        response = client.get("/api/v1/personas")
    assert response.status_code == 401


def test_generic_role_is_denied():
    app.dependency_overrides[operator.persons_operator_principal] = lambda: _principal(
        {"api-reader"}
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/personas")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_functional_permissions_come_from_platform_policy_not_token_roles(monkeypatch, tmp_path):
    policy = tmp_path / "policy.json"
    policy.write_text(
        '{"operators":[{"issuer":"https://identity.example.invalid/realms/synthetic",'
        '"subject":"synthetic-operator-subject","permissions":["persons.read"],'
        '"sources":["reduniv.conecta"]}]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PERSONS_AUTHORIZATION_POLICY_FILE", str(policy))
    principal = Principal(
        subject="synthetic-operator-subject",
        username="ignored-user-claim",
        roles=frozenset({"persons.admin", "persons.register", "persons.source.other"}),
        claims={"iss": "https://identity.example.invalid/realms/synthetic"},
    )
    authorized = authorize_operator(principal)
    assert authorized.roles == frozenset({"persons.read", "persons.source.reduniv.conecta"})


def test_operator_missing_from_application_policy_is_denied(monkeypatch, tmp_path, caplog):
    policy = tmp_path / "policy.json"
    policy.write_text('{"operators":[]}', encoding="utf-8")
    monkeypatch.setenv("PERSONS_AUTHORIZATION_POLICY_FILE", str(policy))
    with pytest.raises(HTTPException) as error:
        authorize_operator(_principal({"persons.read"}))
    assert error.value.status_code == 403
    assert "synthetic-operator-subject" not in caplog.text


def test_create_requires_source_scope_and_forwards_scoped_delegation(monkeypatch, tmp_path):
    signing_key = _configure_delegation(monkeypatch, tmp_path)
    principal = _principal({"persons.register", "persons.source.reduniv.conecta"})
    app.dependency_overrides[operator.persons_operator_principal] = lambda: principal
    observed = {}

    async def request(_client, method, url, **kwargs):
        observed.update(method=method, url=url, **kwargs)
        return httpx.Response(201, json={"person_id": str(uuid4())})

    payload = {
        "display_name": "Persona ficticia",
        "source": {
            "source_system": "reduniv.conecta",
            "source_entity_type": "estudiante",
            "source_record_id": "SYN-001",
        },
        "provenance": {
            "system": "reduniv.conecta",
            "evidence_ref": str(uuid4()),
            "observed_at": "2026-11-20T12:00:00Z",
        },
    }
    try:
        with (
            patch("mes_person_service.operator.httpx.AsyncClient.request", new=request),
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/v1/personas", headers={"Idempotency-Key": str(uuid4())}, json=payload
            )
        assert response.status_code == 201
        assert observed["json"]["source"] == {
            "system": "reduniv.conecta",
            "entity": "estudiante",
            "external_id": "SYN-001",
        }
        forwarded = observed["headers"]["Authorization"].removeprefix("Bearer ")
        claims = jwt.decode(
            forwarded,
            signing_key.public_key(),
            algorithms=["RS256"],
            audience="registro-personas",
            issuer="https://platform.example.invalid/delegation",
        )
        assert claims["token_use"] == "persons_delegation_v1"
        assert claims["permissions"] == ["persons.create"]
        assert claims["sources"] == ["reduniv.conecta"]
        assert claims["sub"] == "synthetic-operator-subject"
        assert claims["actor_iss"] == "https://identity.example.invalid/realms/synthetic"
        assert forwarded != "synthetic-token"
    finally:
        app.dependency_overrides.clear()
        _clear_signing_config()


def test_reference_link_needs_separate_permission_and_translates_contract(monkeypatch, tmp_path):
    _configure_delegation(monkeypatch, tmp_path)
    roles = {"persons.read", "persons.review", "persons.link", "persons.source.reduniv.aprende"}
    app.dependency_overrides[operator.persons_operator_principal] = lambda: _principal(roles)
    observed = {}

    async def request(_client, method, url, **kwargs):
        observed.update(method=method, url=url, **kwargs)
        return httpx.Response(
            201, json={"system": "reduniv.aprende", "entity": "alumno", "external_id": "A-01"}
        )

    person_id = uuid4()
    payload = {
        "source": {
            "source_system": "reduniv.aprende",
            "source_entity_type": "alumno",
            "source_record_id": "A-01",
        },
        "provenance": {
            "system": "reduniv.aprende",
            "evidence_ref": str(uuid4()),
            "observed_at": "2026-11-20T12:00:00Z",
        },
    }
    try:
        with (
            patch("mes_person_service.operator.httpx.AsyncClient.request", new=request),
            TestClient(app) as client,
        ):
            response = client.post(f"/api/v1/personas/{person_id}/referencias", json=payload)
        assert response.status_code == 201
        assert observed["json"]["source"]["system"] == "reduniv.aprende"
        claims = jwt.decode(
            observed["headers"]["Authorization"].split()[1],
            options={"verify_signature": False},
            algorithms=["RS256"],
        )
        assert set(claims["permissions"]) == {
            "persons.read",
            "persons.review",
            "persons.references.link",
        }
        assert claims["sources"] == ["reduniv.aprende"]
    finally:
        app.dependency_overrides.clear()
        _clear_signing_config()


def test_upstream_url_must_be_explicit_loopback(monkeypatch):
    for url in [
        "https://external.example.invalid",
        "http://127.0.0.1:8003@external.example.invalid",
        "http://127.0.0.1:8003/path",
        "http://127.0.0.1:8003?target=external",
        "http://[",
    ]:
        monkeypatch.setenv("REGISTRY_PERSONS_URL", url)
        with pytest.raises(HTTPException) as error:
            operator._upstream_base()
        assert error.value.status_code == 503


def test_forward_does_not_log_private_reference_or_delegation(monkeypatch):
    marker, token = "SYNTHETIC-PRIVATE-REFERENCE", "SYNTHETIC-DELEGATION-TOKEN"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"items": []}))
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        operator.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs)
    )
    monkeypatch.setenv("REGISTRY_PERSONS_URL", "http://127.0.0.1:8013")
    with patch.object(operator, "issue_delegation", return_value=token):
        asyncio.run(
            operator._forward(
                "GET",
                "/v1/referencias/resolver",
                _principal({"persons.read"}),
                SimpleNamespace(state=SimpleNamespace(correlation_id=uuid4())),
                params={"external_id": marker},
                permissions={"persons.read"},
                sources={"reduniv.conecta"},
            )
        )
    assert marker not in token
