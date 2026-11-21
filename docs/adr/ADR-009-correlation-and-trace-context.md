# ADR-009: Correlation ID y Trace Context

## Context

Los flujos atraviesan gateway, servicios, conectores y eventos.

## Decision

Propagar `X-Correlation-ID` UUID y W3C Trace Context. Correlation ID identifica el flujo funcional y trace ID la traza técnica.

## Consequences

Middleware, clientes y publicadores deben preservar ambos valores sin aceptar entradas ilimitadas.

## Alternatives

Usar solo IDs de log locales impide diagnóstico extremo a extremo.

