# ADR-001: API y Contract First

## Context

Los consumidores no deben depender de implementaciones ni fuentes.

## Decision

OpenAPI 3.1, AsyncAPI 3 y JSON Schema serán contratos versionados. La implementación se validará contra ellos.

## Consequences

Las revisiones funcionales ocurren antes del código público y CI detecta incompatibilidades.

## Alternatives

Generar documentación únicamente desde el código; rechazado porque facilita cambios accidentales.

