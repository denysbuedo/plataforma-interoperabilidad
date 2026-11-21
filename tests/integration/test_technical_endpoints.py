import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

MODULES = [
    "mes_registry_api.main",
    "mes_institution_service.main",
    "mes_person_service.main",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_technical_endpoints(module_name: str) -> None:
    app: FastAPI = importlib.import_module(module_name).app
    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")
        metrics = client.get("/metrics")

    assert health.status_code == 200
    assert health.json() == {"status": "alive"}
    assert uuid_header_pattern(health.headers["X-Correlation-ID"])
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
    assert metrics.status_code == 401


def uuid_header_pattern(value: str) -> bool:
    from uuid import UUID

    return str(UUID(value)) == value
