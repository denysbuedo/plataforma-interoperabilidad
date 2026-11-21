# Event-driven architecture

RabbitMQ utilizará un exchange topic durable `mes.events`. Los eventos iniciales son `institution.created`, `institution.updated`, `person.created` y `person.updated`.

La fiabilidad se basará en transactional outbox, publisher confirms, DLQ, backoff con jitter e inbox de consumidores. AsyncAPI y JSON Schema son los contratos. `eventId` identifica la entrega lógica; `correlationId` relaciona el flujo y `causationId` expresa causalidad.

