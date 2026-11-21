# Observability

Los servicios producen logs JSON, métricas Prometheus y trazas OpenTelemetry. Propagan `X-Correlation-ID` y W3C Trace Context sin registrar tokens, secretos ni datos personales completos.

Las señales mínimas cubren tasa, errores, duración, saturación, disponibilidad de fuentes, llamadas upstream, publicación/procesamiento de eventos, colas muertas y frescura del dato. Retención y cardinalidad se fijarán antes de producción.

