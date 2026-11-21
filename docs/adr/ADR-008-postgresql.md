# ADR-008: PostgreSQL

## Context

Se necesita almacenamiento transaccional libre y maduro.

## Decision

Usar PostgreSQL con ownership, roles y migraciones por servicio. No habrá consultas cruzadas entre dominios.

## Consequences

Una instancia puede compartirse inicialmente sin compartir ownership lógico.

## Alternatives

Una base común y productos privativos fueron rechazados por acoplamiento y licencia.

