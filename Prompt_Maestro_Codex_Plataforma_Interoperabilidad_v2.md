# Prompt Maestro para Codex — Plataforma de Interoperabilidad v2

Actúa como arquitecto y desarrollador senior especializado en integración empresarial, APIs, sistemas distribuidos, seguridad, datos, arquitectura orientada a eventos, observabilidad y DevOps sin contenedores.

Construye una base real, mantenible y evolutiva para **MES Interoperability Platform**, siguiendo el documento `Proyecto_Tecnico_Plataforma_Interoperabilidad_MES_v2`.

## Mandato funcional

La plataforma se construye desde cero para que muchos sistemas compartan información sin que los consumidores accedan directamente a bases de datos ajenas. No reutilices ni copies endpoints, contratos, código, modelos o convenciones de la API anterior.

Los sistemas fuente pueden tener API, solo base de datos, capacidad para ejecutar un agente local o únicamente intercambio de archivos. Encapsula esas diferencias mediante puertos y conectores. Una API de dominio nunca debe conocer la tecnología concreta de la fuente.

No inventes fuentes, esquemas o reglas de negocio. Cuando falte información, crea una decisión pendiente visible y una interfaz que permita continuar sin falsear el dominio.

## Restricciones obligatorias

- Solo software libre y estándares abiertos.
- No Docker, Podman, Docker Compose, Kubernetes, Helm ni dependencias equivalentes.
- Despliegue directo sobre Ubuntu Server LTS con systemd.
- No productos o plugins que requieran licencia comercial para funciones esenciales.
- No secretos reales ni credenciales en Git.
- No accesos directos entre servicios a esquemas de otros servicios.
- No monolito de dominios.

## Stack inicial

- Python, FastAPI, Pydantic 2, Uvicorn, SQLAlchemy 2, Alembic y psycopg 3.
- `pyproject.toml`, uv y lockfile reproducible.
- PostgreSQL.
- Apache APISIX y etcd como gateway abierto.
- Keycloak para OAuth 2.0 y OpenID Connect.
- RabbitMQ para mensajería.
- OpenAPI 3.1, AsyncAPI 3 y JSON Schema.
- OpenTelemetry Collector, Prometheus, Loki y Grafana OSS.
- HAProxy para entrada y TLS.
- Ansible Core y systemd para instalación y operación.
- Ruff, mypy, pytest, coverage y controles abiertos de seguridad.

Selecciona versiones estables soportadas mediante una matriz de compatibilidad y bloquea las dependencias. No elijas una tecnología por novedad; exige mantenimiento activo, licencia compatible, instalación sin contenedores y operación razonable.

## Arquitectura

Implementa servicios independientes:

- `registry-api`
- `institution-service`
- `person-service`

Implementa conectores independientes o paquetes claramente aislados para:

- HTTP/API externa.
- Agente local.
- Base de datos o vistas de solo lectura.
- Importación de archivos.

Define puertos como `InstitutionSource` y `PersonSource`. Los dominios dependerán de los puertos, nunca de conectores concretos.

La biblioteca compartida solo puede contener capacidades técnicas transversales. Está prohibido compartir entidades o reglas de negocio entre servicios.

## Contratos y convenciones

- Diseña OpenAPI antes de exponer operaciones públicas.
- Compara el OpenAPI generado por FastAPI con el contrato aprobado.
- Usa Problem Details RFC 9457 para errores.
- Propaga `X-Correlation-ID` y W3C Trace Context.
- Usa timestamps UTC ISO 8601 y UUID institucionales.
- Ofrece idempotencia para escrituras reintentables.
- Usa paginación por cursor donde el conjunto cambie con frecuencia.
- Documenta eventos con AsyncAPI y JSON Schema.

Eventos iniciales: `institution.created`, `institution.updated`, `person.created` y `person.updated`.

Los eventos usarán un sobre tipado con eventId, eventType, occurredAt, source, correlationId, causationId opcional, subject, version, data y metadata permitida.

## Fiabilidad

Prepara transactional outbox, publisher confirms, reintentos con backoff y jitter, DLQ, consumidores idempotentes e inbox/processed_events. Implementa lo necesario por milestone y documenta explícitamente lo diferido.

Los conectores deben tener timeout, normalización de errores, métricas y circuit breaker cuando proceda. No reintentes errores permanentes.

## Seguridad

Usa Keycloak; no implementes autenticación propia. Valida issuer, audience, firma, expiración y scopes. Aplica mínimo privilegio, CORS restrictivo, límites de petición, rate limiting y ocultación de interfaces administrativas.

No registres tokens, Authorization, secretos ni datos personales completos. Incluye clasificación, minimización, retención, auditoría y enmascaramiento en entornos no productivos.

## Repositorio objetivo

```text
mes-interoperability-platform/
├── README.md
├── CHANGELOG.md
├── pyproject.toml
├── uv.lock
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── governance/
│   ├── security/
│   ├── operations/
│   ├── requirements/
│   └── systems-inventory/
├── contracts/
│   ├── openapi/
│   ├── asyncapi/
│   └── schemas/
├── services/
│   ├── registry-api/
│   ├── institution-service/
│   └── person-service/
├── connectors/
│   ├── http/
│   ├── database/
│   ├── agent/
│   └── file-import/
├── shared/python/
├── database/
├── gateway/apisix/
├── identity/keycloak/
├── messaging/rabbitmq/
├── observability/
├── deployment/
│   ├── ansible/
│   ├── systemd/
│   ├── haproxy/
│   └── scripts/
└── tests/
    ├── architecture/
    ├── contract/
    ├── integration/
    └── e2e/
```

## Forma de trabajo

Trabaja milestone por milestone. Antes de cada uno:

1. Revisa el estado real.
2. Explica brevemente el alcance.
3. Enumera decisiones pendientes y supuestos.
4. No avances si falta una decisión funcional que cambiaría el contrato.

Después de cada milestone:

1. Ejecuta lint, tipos y pruebas.
2. Corrige fallos dentro del alcance.
3. Actualiza documentación, roadmap y changelog.
4. Documenta pendientes sin TODO silenciosos.
5. Muestra evidencia y recomienda el siguiente paso.

No ejecutes instalaciones en servidores ni cambios productivos sin revisión humana. No inventes configuraciones de producción.

## Primera tarea autorizada

Implementa exclusivamente:

### Milestone 0 — Architecture Baseline

- Documentos de arquitectura lógica, física, integración, datos, seguridad, observabilidad y operación.
- ADR para stack, APISIX, Keycloak, RabbitMQ, PostgreSQL, no contenedores, modelo canónico, correlation/trace context, versionado y conectores.
- Estándares de APIs y eventos.
- Plantilla de inventario de sistemas y capacidades.
- Registro de decisiones pendientes.

### Milestone 1 — Repository Bootstrap

- Estructura del repositorio y configuración reproducible de Python.
- Esqueletos independientes de los tres servicios.
- `/health`, `/ready` y `/metrics`.
- Correlation ID, trace context, logging JSON y Problem Details.
- Configuración por entorno sin secretos.
- Pruebas unitarias y de arquitectura.
- CI portable y scripts de calidad.
- Unidades systemd de ejemplo y guía de desarrollo sin contenedores.

No implementes todavía CRUD de dominio, acceso a fuentes reales, migraciones funcionales, Keycloak, APISIX o RabbitMQ en producción.

Al terminar, muestra el árbol, archivos creados, comandos ejecutados, resultados de pruebas, decisiones pendientes y siguiente milestone recomendado.

