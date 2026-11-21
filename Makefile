.PHONY: install test lint format typecheck run-registry run-institutions run-persons

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

lint:
	python -m ruff check .

format:
	python -m ruff format .

typecheck:
	python -m mypy shared/python services

run-registry:
	python -m uvicorn mes_registry_api.main:app --app-dir services/registry-api/src --port 8001

run-institutions:
	python -m uvicorn mes_institution_service.main:app --app-dir services/institution-service/src --port 8002

run-persons:
	python tools/run_persons.py --service-root "$(PERSONS_ROOT)"

