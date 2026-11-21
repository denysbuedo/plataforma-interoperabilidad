from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from mes_common.logging import configure_logging
from mes_common.middleware import CorrelationAndAccessLogMiddleware
from mes_common.problem import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from mes_common.security import require_any_role
from mes_common.settings import get_settings

ReadinessCheck = Callable[[], Awaitable[bool]]


def create_service_app(
    *,
    title: str,
    service_name: str,
    version: str = "0.1.0",
    readiness: ReadinessCheck | None = None,
) -> FastAPI:
    configure_logging()
    settings = get_settings(service_name)
    app = FastAPI(
        title=title,
        version=version,
        swagger_ui_init_oauth={
            "clientId": settings.oidc_swagger_client_id,
            "usePkceWithAuthorizationCodeGrant": True,
        },
    )
    app.state.service_name = service_name
    app.add_middleware(CorrelationAndAccessLogMiddleware)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/health", tags=["technical"])
    async def health() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/ready", tags=["technical"])
    async def ready() -> Response:
        is_ready = True if readiness is None else await readiness()
        status_code = 200 if is_ready else 503
        return Response(
            content='{"status":"ready"}' if is_ready else '{"status":"not_ready"}',
            status_code=status_code,
            media_type="application/json",
        )

    @app.get(
        "/metrics",
        tags=["technical"],
        dependencies=[Depends(require_any_role("api-admin"))],
    )
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
