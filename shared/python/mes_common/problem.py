from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: str
    correlation_id: str = Field(alias="correlationId")


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "unknown"))


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    problem = ProblemDetails(
        title="HTTP error",
        status=exc.status_code,
        detail=str(exc.detail),
        instance=request.url.path,
        code="HTTP_ERROR",
        correlation_id=_correlation_id(request),
    )
    headers = {}
    if exc.headers and "WWW-Authenticate" in exc.headers:
        headers["WWW-Authenticate"] = exc.headers["WWW-Authenticate"]
    return JSONResponse(
        problem.model_dump(by_alias=True), status_code=exc.status_code, headers=headers
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    problem = ProblemDetails(
        title="Request validation failed",
        status=422,
        detail="One or more request fields are invalid.",
        instance=request.url.path,
        code="VALIDATION_ERROR",
        correlation_id=_correlation_id(request),
        # Pydantic's error objects contain submitted values, which may be PII.
    )
    return JSONResponse(problem.model_dump(by_alias=True), status_code=422)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    problem = ProblemDetails(
        title="Internal server error",
        status=500,
        detail="The service could not process the request.",
        instance=request.url.path,
        code="INTERNAL_ERROR",
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(problem.model_dump(by_alias=True), status_code=500)
