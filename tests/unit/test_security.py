from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from mes_common import security
from mes_common.security import Principal, require_any_role


def principal(*roles: str) -> Principal:
    return Principal(
        subject="test-subject",
        username="tester",
        roles=frozenset(roles),
        claims={},
    )


@pytest.mark.anyio
async def test_role_dependency_accepts_any_required_role() -> None:
    dependency: Any = require_any_role("api-reader", "api-admin")
    result = await dependency(principal("api-reader"))
    assert result.subject == "test-subject"


@pytest.mark.anyio
async def test_role_dependency_rejects_missing_role() -> None:
    dependency: Any = require_any_role("api-admin")
    with pytest.raises(HTTPException) as caught:
        await dependency(principal("api-reader"))
    assert caught.value.status_code == 403


@pytest.fixture
def oidc_key(monkeypatch: pytest.MonkeyPatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer = "https://identity.example.invalid/realms/per002"
    monkeypatch.setattr(security, "_issuer", issuer)
    monkeypatch.setattr(security, "_pinned_public_key", key.public_key())
    monkeypatch.setattr(security._settings, "oidc_audience", "mes-api")
    return key, issuer


def mint(key, issuer: str, **updates: Any) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": issuer,
        "aud": "mes-api",
        "sub": "synthetic-operator",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "realm_access": {"roles": ["persons.read", "persons.source.demo"]},
    }
    claims.update(updates)
    return jwt.encode(claims, key, algorithm="RS256")


def test_platform_validates_signature_issuer_audience_and_vigency(oidc_key) -> None:
    key, issuer = oidc_key
    valid = security.decode_access_token(mint(key, issuer))
    assert valid.subject == "synthetic-operator"
    assert valid.roles == frozenset({"persons.read", "persons.source.demo"})

    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rejected = [
        jwt.encode(
            {"iss": issuer, "aud": "mes-api", "sub": "synthetic", "iat": 1, "exp": 2},
            wrong_key,
            algorithm="RS256",
        ),
        mint(key, "https://other.example.invalid/realm"),
        mint(key, issuer, aud="other-api"),
        mint(key, issuer, exp=int((datetime.now(UTC) - timedelta(seconds=60)).timestamp())),
        mint(key, issuer, iat=int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())),
    ]
    for token in rejected:
        with pytest.raises(HTTPException) as caught:
            security.decode_access_token(token)
        assert caught.value.status_code == 401


def test_access_token_accepts_persons_issuer_only_for_configured_azp(oidc_key, monkeypatch) -> None:
    key, _global_issuer = oidc_key
    persons_issuer = "https://identidad.reduniv.edu.cu/realms/reduniv-institucional"
    client_id = "interoperabilidad-admin"
    jwks = Mock()
    jwks.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    monkeypatch.setattr(security, "_jwks_client_for_issuer", lambda issuer: jwks)

    token = mint(
        key,
        persons_issuer,
        azp=client_id,
        nbf=int(datetime.now(UTC).timestamp()) - 1,
    )
    principal = security.decode_access_token(
        token,
        issuer=persons_issuer,
        audience="mes-api",
        authorized_party=client_id,
    )
    assert principal.claims["azp"] == client_id
    jwks.get_signing_key_from_jwt.assert_called_once_with(token)

    for claims in (
        {"azp": "another-client"},
        {"azp": None},
    ):
        invalid = mint(key, persons_issuer, **claims)
        with pytest.raises(HTTPException) as caught:
            security.decode_access_token(
                invalid,
                issuer=persons_issuer,
                audience="mes-api",
                authorized_party=client_id,
            )
        assert caught.value.status_code == 401


def test_malformed_signed_role_claims_do_not_grant_access(oidc_key) -> None:
    key, issuer = oidc_key
    token = mint(key, issuer, realm_access=None, resource_access=["malformed"])
    principal = security.decode_access_token(token)
    assert principal.roles == frozenset()
