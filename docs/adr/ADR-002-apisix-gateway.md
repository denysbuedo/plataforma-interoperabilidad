# ADR-002: Apache APISIX como gateway

## Context

Se necesita routing, OIDC, límites y observabilidad sin funciones comerciales obligatorias.

## Decision

Usar Apache APISIX y etcd, previa prueba de instalación directa y compatibilidad.

## Consequences

Se incorpora operación de APISIX/etcd; la lógica de negocio permanece fuera del gateway.

## Alternatives

Kong fue descartado para evitar depender de plugins comerciales en capacidades esenciales. HAProxy solo no cubre todo el gobierno requerido.

