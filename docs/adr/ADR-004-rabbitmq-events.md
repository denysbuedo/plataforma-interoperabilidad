# ADR-004: RabbitMQ para eventos

## Context

Los cambios deben propagarse sin acoplar productores y consumidores.

## Decision

Usar RabbitMQ con topic exchange, outbox, confirms, DLQ e idempotencia.

## Consequences

Los consumidores aceptan duplicados y consistencia eventual.

## Alternatives

Solo HTTP síncrono no cubre fan-out ni tolerancia temporal; Kafka añade una complejidad no justificada inicialmente.

