from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from mes_common.settings import get_settings

_settings = get_settings("security")
_issuer = _settings.oidc_issuer_url.rstrip("/")

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{_issuer}/protocol/openid-connect/auth",
    tokenUrl=f"{_issuer}/protocol/openid-connect/token",
    scopes={
        "openid": "Authenticate the caller",
        "profile": "Read the caller profile",
    },
)

_jwks_url = _settings.oidc_jwks_url or f"{_issuer}/protocol/openid-connect/certs"
_jwks_client = PyJWKClient(_jwks_url, cache_keys=True)
_pinned_public_key = (
    Path(_settings.oidc_public_key_file).read_text(encoding="ascii")
    if _settings.oidc_public_key_file
    else None
)


@lru_cache(maxsize=8)
def _jwks_client_for_issuer(issuer: str) -> PyJWKClient:
    """Create a cached Keycloak JWKS client for a separately configured issuer."""
    return PyJWKClient(f"{issuer.rstrip('/')}/protocol/openid-connect/certs", cache_keys=True)


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    username: str | None
    roles: frozenset[str]
    claims: dict[str, Any]


def _unauthorized(detail: str = "Invalid or missing access token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_access_token(
    token: str,
    *,
    issuer: str | None = None,
    audience: str | None = None,
    authorized_party: str | None = None,
) -> Principal:
    """Validate a Keycloak token, optionally for a separately trusted client issuer."""
    expected_issuer = (issuer or _issuer).rstrip("/")
    expected_audience = audience or _settings.oidc_audience
    try:
        if expected_issuer == _issuer:
            signing_key = (
                _pinned_public_key
                if _pinned_public_key is not None
                else _jwks_client.get_signing_key_from_jwt(token).key
            )
        else:
            signing_key = (
                _jwks_client_for_issuer(expected_issuer).get_signing_key_from_jwt(token).key
            )
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=expected_audience,
            issuer=expected_issuer,
            options={
                "require": ["exp", "iat", "iss", "sub", "aud"],
                "verify_signature": True,
            },
        )
    except (InvalidTokenError, PyJWKClientError) as exc:
        raise _unauthorized() from exc

    if authorized_party is not None and claims.get("azp") != authorized_party:
        raise _unauthorized()

    realm_access = claims.get("realm_access", {})
    resource_access = claims.get("resource_access", {})
    client_access = (
        resource_access.get(_settings.oidc_audience, {})
        if isinstance(resource_access, dict)
        else {}
    )
    realm_roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
    client_roles = client_access.get("roles", []) if isinstance(client_access, dict) else []
    realm_roles = realm_roles if isinstance(realm_roles, list) else []
    client_roles = client_roles if isinstance(client_roles, list) else []
    roles = frozenset(str(role) for role in [*realm_roles, *client_roles])
    return Principal(
        subject=str(claims["sub"]),
        username=claims.get("preferred_username"),
        roles=roles,
        claims=claims,
    )


async def authenticated_principal(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Principal:
    return decode_access_token(token)


def require_any_role(*required_roles: str) -> Callable[..., Awaitable[Principal]]:
    required = frozenset(required_roles)

    async def dependency(
        principal: Annotated[Principal, Depends(authenticated_principal)],
    ) -> Principal:
        if required.isdisjoint(principal.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return principal

    return dependency
