from typing import Annotated

from fastapi import Depends
from mes_common.app import create_service_app
from mes_common.security import Principal, require_any_role

app = create_service_app(title="MES Registry API", service_name="registry-api")
ApiPrincipal = Annotated[
    Principal,
    Depends(require_any_role("api-reader", "api-writer", "api-admin")),
]


@app.get("/api/v1/me", tags=["security"])
async def current_identity(
    principal: ApiPrincipal,
) -> dict[str, object]:
    """Return the validated identity; useful as an OAuth2 integration smoke test."""
    return {
        "subject": principal.subject,
        "username": principal.username,
        "roles": sorted(principal.roles),
    }
