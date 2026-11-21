# ADR-003: Keycloak para identidad

## Context

La institución necesita OAuth 2.0/OIDC, scopes y cuentas técnicas.

## Decision

Usar Keycloak con PostgreSQL dedicado y separar endpoints administrativos.

## Consequences

Requiere operación Java, TLS, backups y alta disponibilidad proporcional al SLO.

## Alternatives

Autenticación propia rechazada por riesgo; servicios comerciales rechazados por dependencia privativa.

