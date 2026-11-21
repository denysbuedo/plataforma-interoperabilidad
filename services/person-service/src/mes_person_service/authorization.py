"""Application-owned functional authorization policy for operator Personas."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from mes_common.security import Principal

_ALIAS = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)*$")
_PERMISSIONS = frozenset({"persons.read", "persons.register", "persons.review", "persons.link"})
_security_logger = logging.getLogger("mes.persons.security")


def authorize_operator(principal: Principal) -> Principal:
    """Replace all IdP roles with grants from the platform-owned external policy."""
    policy_path = os.environ.get("PERSONS_AUTHORIZATION_POLICY_FILE", "")
    if not policy_path:
        raise HTTPException(status_code=503, detail="Person authorization policy is not configured")
    try:
        policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=503, detail="Person authorization policy is not configured"
        ) from None
    if (
        not isinstance(policy, dict)
        or set(policy) != {"operators"}
        or not isinstance(policy["operators"], list)
    ):
        raise HTTPException(status_code=503, detail="Person authorization policy is invalid")
    issuer = principal.claims.get("iss")
    subject = principal.subject
    identities: set[tuple[str, str]] = set()
    matches = []
    for row in policy["operators"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"issuer", "subject", "permissions", "sources"}
            or not isinstance(row.get("issuer"), str)
            or not row["issuer"].startswith("https://")
            or not isinstance(row.get("subject"), str)
            or not row["subject"]
            or len(row["subject"]) > 255
            or not isinstance(row.get("permissions"), list)
            or any(
                not isinstance(item, str) or item not in _PERMISSIONS for item in row["permissions"]
            )
            or len(set(row["permissions"])) != len(row["permissions"])
            or not isinstance(row.get("sources"), list)
            or any(
                not isinstance(item, str) or len(item) > 64 or not _ALIAS.fullmatch(item)
                for item in row["sources"]
            )
            or len(set(row["sources"])) != len(row["sources"])
        ):
            raise HTTPException(status_code=503, detail="Person authorization policy is invalid")
        identity = (row["issuer"], row["subject"])
        if identity in identities:
            raise HTTPException(status_code=503, detail="Person authorization policy is invalid")
        identities.add(identity)
        if row["issuer"] == issuer and row["subject"] == subject:
            matches.append(row)
    if len(matches) != 1:
        actor_id = uuid5(NAMESPACE_URL, f"{issuer}\x00{subject}")
        _security_logger.warning(
            "authorization_denied actor_id=%s permission=persons.operator_policy", actor_id
        )
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    grant = matches[0]
    permissions, sources = grant["permissions"], grant["sources"]
    roles = frozenset(permissions) | frozenset(f"persons.source.{source}" for source in sources)
    return Principal(subject=principal.subject, username=None, roles=roles, claims=principal.claims)
