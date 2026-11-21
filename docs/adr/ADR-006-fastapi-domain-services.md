# ADR-006: FastAPI para servicios de dominio

## Context

Se requieren APIs tipadas, OpenAPI, validación y conectores rápidos de construir.

## Decision

Usar FastAPI y Pydantic 2 como capa HTTP. El dominio no dependerá del framework. La decisión se revisará con evidencia del primer vertical.

## Consequences

Se exige Python tipado, Ruff, mypy, pruebas y disciplina async. Un servicio podrá reimplementarse sin cambiar su contrato.

## Alternatives

Go ofrece operación y rendimiento excelentes, pero se prioriza la productividad actual. Java y .NET no fueron preferidos por el patrocinador.

