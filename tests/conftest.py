from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    app: FastAPI = request.getfixturevalue("app")
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
