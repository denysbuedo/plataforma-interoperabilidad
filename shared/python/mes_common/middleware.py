import logging
import time
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("mes.http")


def _valid_correlation_id(value: str | None) -> str:
    if value is None:
        return str(uuid4())
    try:
        return str(UUID(value))
    except ValueError:
        return str(uuid4())


class CorrelationAndAccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = _valid_correlation_id(request.headers.get("X-Correlation-ID"))
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        response.headers["X-Correlation-ID"] = correlation_id
        route = request.scope.get("route")
        # Route templates avoid recording person_id, account IDs, or other path values.
        safe_path = getattr(route, "path", "<unmatched>")
        logger.info(
            "request_completed",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": safe_path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
