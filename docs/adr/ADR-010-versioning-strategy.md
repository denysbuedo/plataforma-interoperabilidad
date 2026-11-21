# ADR-010: Versionado y compatibilidad

## Context

La plataforma tendrá consumidores con ritmos de cambio distintos.

## Decision

Versionar contratos en Git; usar versión mayor en URL para APIs y campo de versión en eventos. Cambios compatibles no crean URL nueva.

## Consequences

Se requieren pruebas de compatibilidad, deprecación y coexistencia temporal.

## Alternatives

Versionar cada cambio crea proliferación; no versionar rompe consumidores.

