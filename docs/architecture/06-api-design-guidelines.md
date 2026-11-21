# API design guidelines

- OpenAPI 3.1 versionado antes del endpoint público.
- Recursos y sustantivos; no nombres de productos fuente.
- JSON UTF-8, timestamps UTC ISO 8601 y UUID.
- Problem Details RFC 9457 para errores.
- `X-Correlation-ID` y W3C Trace Context.
- Paginación por cursor para colecciones cambiantes.
- `Idempotency-Key` para creaciones reintentables.
- Cambios incompatibles requieren nueva versión mayor.
- Endpoints técnicos no se publican a consumidores mediante el gateway.

