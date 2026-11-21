# ADR-011: Conectores para fuentes heterogéneas

## Context

No todos los sistemas poseen backend o API.

## Decision

Definir puertos por dominio e implementaciones HTTP, agente, lectura controlada o archivo. Los consumidores nunca ven el mecanismo.

## Consequences

Cada conector tiene credenciales, timeout, métricas y pruebas. El acceso a BD es una excepción encapsulada, no una integración pública.

## Alternatives

Exigir APIs a todas las fuentes impediría incorporar sistemas actuales; permitir acceso directo perpetuaría el problema.

