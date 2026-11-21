# Integration patterns

Orden preferido para incorporar una fuente:

1. API mantenida por la fuente.
2. Agente local con interfaz mínima y autenticada.
3. Vistas o procedimientos de base de datos con acceso controlado y preferentemente de solo lectura.
4. Lotes de archivos validados e idempotentes.
5. CDC únicamente mediante ADR y justificación de volumen o latencia.

Todos los conectores aplican timeout, presupuesto de reintentos, normalización de errores, correlation/trace context y métricas. La consistencia entre sistemas será eventual; no se prometen transacciones distribuidas.

