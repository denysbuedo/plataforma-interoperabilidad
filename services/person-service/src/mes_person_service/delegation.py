"""Issue narrowly scoped, short-lived authorization tokens for Registro de Personas."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import jwt
from fastapi import HTTPException
from jwt.exceptions import InvalidKeyError
from mes_common.security import Principal

_SOURCE_ALIAS = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)*$")
_KEY_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_MAX_TOKEN_TTL_SECONDS = 120
_ROLE_PERMISSIONS = {
    "persons.read": frozenset({"persons.read", "persons.list"}),
    "persons.register": frozenset({"persons.create"}),
    "persons.review": frozenset({"persons.review"}),
    "persons.link": frozenset({"persons.references.link"}),
}
_REGISTRY_PERMISSIONS = frozenset().union(*_ROLE_PERMISSIONS.values())


@dataclass(frozen=True)
class _SigningConfig:
    issuer: str
    audience: str
    key_id: str
    ttl_seconds: int
    private_key: str


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Person delegation is not configured")


@lru_cache(maxsize=1)
def _signing_config() -> _SigningConfig:
    issuer = os.environ.get("PERSONS_DELEGATION_ISSUER", "").rstrip("/")
    audience = os.environ.get("PERSONS_DELEGATION_AUDIENCE", "")
    key_id = os.environ.get("PERSONS_DELEGATION_KEY_ID", "")
    key_file = os.environ.get("PERSONS_DELEGATION_PRIVATE_KEY_FILE", "")
    ttl_value = os.environ.get("PERSONS_DELEGATION_TTL_SECONDS", "60")
    parsed_issuer = urlsplit(issuer)
    try:
        ttl_seconds = int(ttl_value)
    except ValueError:
        raise _unavailable() from None
    if (
        parsed_issuer.scheme != "https"
        or not parsed_issuer.hostname
        or parsed_issuer.username is not None
        or parsed_issuer.password is not None
        or "*" in issuer
        or parsed_issuer.query
        or parsed_issuer.fragment
        or not audience
        or len(audience) > 128
        or not _KEY_ID.fullmatch(key_id)
        or not key_file
        or not 1 <= ttl_seconds <= _MAX_TOKEN_TTL_SECONDS
    ):
        raise _unavailable()
    try:
        private_key = Path(key_file).read_text(encoding="ascii")
    except OSError:
        raise _unavailable() from None
    if not private_key.startswith("-----BEGIN PRIVATE KEY-----"):
        raise _unavailable()
    return _SigningConfig(issuer, audience, key_id, ttl_seconds, private_key)


def _operator_grants(principal: Principal) -> tuple[frozenset[str], frozenset[str]]:
    permissions = frozenset().union(
        *(_ROLE_PERMISSIONS.get(role, frozenset()) for role in principal.roles)
    )
    sources = frozenset(
        role.removeprefix("persons.source.")
        for role in principal.roles
        if role.startswith("persons.source.") and role.removeprefix("persons.source.")
    )
    return permissions, sources


def issue_delegation(
    principal: Principal,
    *,
    permissions: set[str] | frozenset[str],
    sources: set[str] | frozenset[str],
) -> str:
    """Mint a per-operation assertion after the browser's OIDC token was validated."""
    config = _signing_config()
    granted_permissions, granted_sources = _operator_grants(principal)
    requested_permissions = frozenset(permissions)
    requested_sources = frozenset(sources)
    actor_issuer = principal.claims.get("iss")
    subject = principal.subject
    if (
        not requested_permissions
        or not requested_permissions <= _REGISTRY_PERMISSIONS
        or not requested_permissions <= granted_permissions
        or not requested_sources <= granted_sources
        or len(requested_sources) > 64
        or any(
            not _SOURCE_ALIAS.fullmatch(source) or len(source) > 64 for source in requested_sources
        )
        or not isinstance(actor_issuer, str)
        or not actor_issuer.startswith("https://")
        or len(actor_issuer) > 500
        or not subject
        or len(subject) > 255
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    now = datetime.now(UTC)
    claims = {
        "iss": config.issuer,
        "aud": config.audience,
        "sub": subject,
        "actor_iss": actor_issuer,
        "token_use": "persons_delegation_v1",
        "permissions": sorted(requested_permissions),
        "sources": sorted(requested_sources),
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=config.ttl_seconds)).timestamp()),
    }
    try:
        return jwt.encode(
            claims,
            config.private_key,
            algorithm="RS256",
            headers={"kid": config.key_id, "typ": "JWT"},
        )
    except (InvalidKeyError, ValueError):
        raise _unavailable() from None


def _clear_signing_config() -> None:
    """Test hook to clear configuration cached from the process environment."""
    _signing_config.cache_clear()
