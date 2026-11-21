import asyncio
import json
import logging
from datetime import UTC, datetime
from io import StringIO
from uuid import UUID, uuid4

from fastapi import Request
from mes_common.events import EventEnvelope
from mes_common.logging import JsonFormatter
from mes_common.middleware import _valid_correlation_id
from mes_common.problem import http_exception_handler
from mes_common.settings import Settings
from pydantic import BaseModel
from starlette.exceptions import HTTPException


def test_invalid_correlation_id_is_replaced_with_uuid() -> None:
    assert UUID(_valid_correlation_id("not-a-uuid"))


def test_valid_correlation_id_is_preserved() -> None:
    value = "6f19a833-d625-4400-9477-fb65cc75805e"
    assert _valid_correlation_id(value) == value


def test_json_formatter_produces_machine_readable_log() -> None:
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test-json")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.info("completed", extra={"correlation_id": "abc"})
    payload = json.loads(output.getvalue())
    assert payload["message"] == "completed"
    assert payload["correlation_id"] == "abc"


class ExampleData(BaseModel):
    value: str


def test_event_envelope_uses_public_aliases() -> None:
    event_id = uuid4()
    correlation_id = uuid4()
    envelope = EventEnvelope[ExampleData](
        event_id=event_id,
        event_type="institution.created",
        occurred_at=datetime.now(UTC),
        source="institution-service",
        correlation_id=correlation_id,
        subject="institution/123",
        data=ExampleData(value="ok"),
    )

    public = envelope.model_dump(by_alias=True, mode="json")
    assert public["eventId"] == str(event_id)
    assert public["correlationId"] == str(correlation_id)
    assert public["eventType"] == "institution.created"


def test_settings_have_safe_defaults() -> None:
    settings = Settings(service_name="test-service", _env_file=None)
    assert settings.environment == "development"
    assert settings.log_level == "INFO"


def test_problem_details_use_rfc_shape_and_correlation_id() -> None:
    scope = {"type": "http", "method": "GET", "path": "/missing", "headers": []}
    request = Request(scope)
    request.state.correlation_id = "test-correlation"
    response = asyncio.run(
        http_exception_handler(request, HTTPException(status_code=404, detail="Missing"))
    )
    payload = json.loads(bytes(response.body).decode())
    assert response.status_code == 404
    assert payload["status"] == 404
    assert payload["correlationId"] == "test-correlation"
