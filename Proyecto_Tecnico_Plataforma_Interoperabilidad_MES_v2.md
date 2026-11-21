# PROYECTO TÉCNICO

## Plataforma Institucional de Interoperabilidad y Servicios Digitales

**Arquitectura API-first y orientada a eventos para compartir información entre sistemas institucionales heterogéneos**

- Organismo: Ministerio de Educación Superior
- Versión: 2.0
- Fecha: octubre de 2026
- Despliegue objetivo: GNU/Linux Ubuntu Server LTS sobre máquinas virtuales
- Licenciamiento: exclusivamente software libre y estándares abiertos
- Contenedores: no se utilizarán Docker, Podman, Kubernetes, Helm ni plataformas equivalentes
- Enfoque: construcción desde cero e incorporación progresiva de sistemas

## Resumen ejecutivo

La institución dispone de numerosos sistemas desarrollados con tecnologías, modelos de datos y niveles de madurez diferentes. Algunos cuentan con APIs; otros solo permiten consultar bases de datos, ejecutar procesos locales o intercambiar archivos. Las integraciones directas entre aplicaciones y el acceso cruzado a bases de datos producen dependencias frágiles, duplicación de credenciales, poca trazabilidad y dificultades para sustituir o evolucionar los sistemas.

Este proyecto construirá desde cero una Plataforma Institucional de Interoperabilidad. La plataforma expondrá APIs y eventos organizados por dominios institucionales —por ejemplo, Instituciones, Personas, Estudiantes o Matrículas— y ocultará a los consumidores la ubicación y tecnología de las fuentes. Ningún consumidor accederá directamente a la base de datos de otro sistema.

Cuando un sistema fuente no disponga de backend, se utilizará un conector controlado: lectura mediante vistas y credenciales de mínimo privilegio, un agente local, una importación de archivos o captura de cambios cuando esté justificada. Estos mecanismos serán internos; nunca se convertirán en contratos públicos para los consumidores.

La solución utilizará software libre, protocolos abiertos y componentes reemplazables. Se desplegará directamente sobre máquinas virtuales GNU/Linux mediante paquetes, binarios verificados, entornos virtuales de Python, Ansible y unidades systemd. No dependerá de contenedores ni de productos privativos.

## 1. Propósito y problema

### 1.1 Propósito

Ofrecer una capa institucional segura, gobernada y observable para compartir información entre sistemas sin conexiones punto a punto ni acceso directo de consumidores a bases de datos ajenas.

### 1.2 Problemas que se resolverán

- Integraciones punto a punto y conocimiento de estructuras internas.
- Sistemas sin API o backend reutilizable.
- Identificadores incompatibles para una misma entidad.
- Autenticación y autorización heterogéneas.
- Ausencia de contratos y responsabilidades institucionales.
- Consultas periódicas innecesarias cuando un evento sería más eficiente.
- Baja trazabilidad de accesos, errores y transformaciones.
- Dependencia de productos o conocimientos individuales.

### 1.3 Principio de acceso

Un sistema consumidor utilizará una API institucional o se suscribirá a un evento institucional. No consultará directamente la base de datos de otro sistema.

Cuando la única interfaz de una fuente sea su base de datos, solo un conector administrado por la plataforma podrá acceder a vistas o procedimientos expresamente autorizados, con cuenta de solo lectura cuando la operación lo permita. Esta excepción técnica no autoriza acceso entre aplicaciones.

### 1.4 Construcción desde cero

La plataforma no reutilizará contratos, endpoints, código, modelos ni convenciones de la API anterior. La solución previa no será referencia arquitectónica ni fuente de requisitos. Los nuevos contratos surgirán de los casos de uso, del significado institucional del dato y de acuerdos con sus propietarios.

El inventario requerido será de sistemas, datos, propietarios y capacidades de integración; no será un inventario para copiar la API existente.

## 2. Objetivos y alcance

### 2.1 Objetivo general

Diseñar e implantar una plataforma que permita intercambiar información de forma segura, normalizada, desacoplada, trazable y gobernada entre aplicaciones institucionales heterogéneas.

### 2.2 Objetivos específicos

- Definir contratos públicos independientes de los productos que almacenan los datos.
- Establecer un punto controlado de entrada a las APIs institucionales.
- Incorporar sistemas con API, base de datos, agente local o archivos.
- Definir modelos canónicos mínimos por dominio.
- Mantener correspondencias entre IDs institucionales y externos.
- Centralizar identidad, scopes y políticas de acceso.
- Publicar eventos para cambios que interesen a varios consumidores.
- Mantener un catálogo de APIs, eventos, fuentes, propietarios y consumidores.
- Garantizar trazabilidad con correlation ID, métricas, trazas, logs y auditoría.
- Evitar dependencias obligatorias de tecnologías privativas.

### 2.3 Alcance inicial

El primer producto operativo incluirá la base arquitectónica, el catálogo de sistemas y capacidades, Registry API, el dominio Instituciones como vertical completo, el dominio Personas, conectores iniciales, contratos OpenAPI y AsyncAPI, identidad, gateway, mensajería, observabilidad, auditoría, pruebas y despliegue sobre máquinas virtuales.

No incluye la reescritura de los sistemas existentes, la conexión simultánea de todos ellos, un modelo canónico universal, analítica institucional completa ni acceso directo entre sus bases de datos.

## 3. Principios de arquitectura

- **Domain First:** APIs y eventos se organizan por conceptos institucionales.
- **Contract First:** OpenAPI, AsyncAPI y JSON Schema se diseñan y revisan antes de la implementación pública.
- **API First:** las capacidades reutilizables se ofrecen mediante interfaces documentadas.
- **Fuente gobernada:** cada atributo crítico tiene propietario y fuente autorizada.
- **Desacoplamiento:** consumidores y contratos no dependen del esquema de una fuente.
- **Puertos y adaptadores:** cada servicio de dominio depende de interfaces; los conectores implementan esas interfaces.
- **Servicios independientes:** no se construirá una única aplicación con todos los dominios.
- **Seguridad y privacidad por diseño:** denegación por defecto, mínimo privilegio y minimización de datos.
- **Observabilidad por diseño:** todas las operaciones importantes son correlacionables.
- **Compatibilidad hacia atrás:** los cambios incompatibles requieren una versión mayor y transición gobernada.
- **Idempotencia:** las escrituras y los consumidores de eventos toleran reintentos.
- **Fallos aislados:** la indisponibilidad de una fuente no debe derribar toda la plataforma.
- **Software libre y estándares abiertos:** no se aceptan dependencias obligatorias de licencias comerciales.
- **Despliegue sin contenedores:** todos los componentes deben poder operar directamente con systemd.

## 4. Arquitectura objetivo

```text
Aplicaciones, portales, BI y sistemas consumidores
                         |
                      HTTPS
                         v
                  HAProxy / TLS
                         |
                         v
             Apache APISIX API Gateway
                         |
       +-----------------+-----------------+
       |                 |                 |
 Registry API     Institution Service   Person Service
       |                 |                 |
       |          Puertos de dominio       |
       |                 |                 |
       +---------+-------+--------+--------+
                 |                |
           Conectores         PostgreSQL
      +----------+----------+  por servicio
      |          |          |
 API externa  Agente local  BD/vista/archivo

Servicios transversales: Keycloak, RabbitMQ, OpenTelemetry,
Prometheus, Loki, Grafana OSS y auditoría.
```

### 4.1 Límites de los servicios

Cada servicio poseerá su código, configuración, migraciones, esquema y credenciales. Compartir una instancia PostgreSQL no permitirá consultas directas entre esquemas. La integración entre dominios utilizará contratos HTTP o eventos.

El código compartido se limitará a capacidades técnicas estables: configuración, logging, correlation ID, autenticación, telemetría y sobre de eventos. No contendrá entidades ni reglas de negocio compartidas.

### 4.2 Flujo síncrono

Consumidor → HAProxy → APISIX → API de dominio → conector → fuente autorizada → respuesta canónica.

Se utilizará cuando el consumidor necesite una respuesta inmediata o la frescura del dato exija consultar la fuente.

### 4.3 Flujo asíncrono

Fuente o servicio → outbox → publicador → RabbitMQ → consumidores idempotentes.

Se utilizará para propagar cambios, alimentar réplicas de lectura y desacoplar procesos que no requieren respuesta inmediata.

### 4.4 Gateway y autenticación

Apache APISIX actuará como gateway abierto para routing, límites, validación OIDC, políticas y métricas. Keycloak emitirá tokens OAuth 2.0/OIDC. Los servicios validarán nuevamente claims críticos y scopes; el gateway no contendrá lógica de negocio.

## 5. Formas de incorporar sistemas

Cada sistema se clasificará mediante una ficha de capacidades y se elegirá el mecanismo menos invasivo que satisfaga seguridad, frescura y fiabilidad.

### 5.1 Conector HTTP

Preferido cuando la fuente dispone de una API mantenida. Incluirá timeout, pool de conexiones, reintentos limitados con backoff y jitter, circuit breaker, normalización de errores y métricas.

### 5.2 Agente local

Servicio ligero instalado junto al sistema fuente cuando no sea conveniente exponer su base de datos. El agente solo ofrecerá operaciones autorizadas, autenticación mutua, logs y health checks. No replicará reglas de negocio del dominio.

### 5.3 Conector de base de datos controlado

Último recurso para sistemas sin interfaz. Utilizará vistas o procedimientos estables, cuenta dedicada, mínimo privilegio, allowlist de red, TLS cuando esté soportado, límites de consulta y timeouts. Se prohíben escrituras directas salvo decisión arquitectónica y funcional explícita.

### 5.4 Intercambio de archivos

Para sistemas que solo exportan información se admitirán CSV, JSON o formatos acordados. La recepción tendrá área de cuarentena, checksum, validación de esquema, procesamiento idempotente, registro de lote y reporte de errores. Los archivos ofimáticos no serán contratos automáticos salvo necesidad documentada.

### 5.5 Captura de cambios

CDC o replicación lógica podrá incorporarse cuando el volumen o la latencia lo justifiquen. Requerirá una decisión específica, evaluación de impacto sobre la fuente y contrato de eventos. No será requisito del primer incremento.

### 5.6 Matriz de capacidades

Para cada sistema se documentará: propietario, responsable técnico, entidades, fuente de verdad, interfaz disponible, tecnología, autenticación, conectividad, volumen, frecuencia, latencia tolerada, calidad, restricciones, datos sensibles y mecanismo recomendado.

## 6. Datos, modelo canónico e identidad

### 6.1 Modelo canónico evolutivo

El modelo canónico se definirá por dominio y solo contendrá los atributos necesarios para los casos de uso aprobados. No se intentará un modelo universal desde el inicio.

### 6.2 Entidades iniciales

**Institution:** id UUID, code, name, short_name opcional, type, parent_id opcional, active, created_at y updated_at.

**Person:** id UUID, identification, first_name, middle_name opcional, first_surname, second_surname opcional, email opcional, phone opcional, institution_id opcional, active, created_at y updated_at.

Los nombres internos del código y los eventos serán ingleses; las descripciones funcionales y la documentación para usuarios podrán estar en español. Las URLs públicas usarán nombres en español o inglés según decisión institucional única registrada en ADR; no se mezclarán ambos estilos.

### 6.3 Correspondencia de identificadores

La plataforma usará UUID institucionales. Los IDs externos se guardarán en un registro con canonical_id, source_system, source_entity y source_id, con unicidad por fuente, entidad e ID. Los IDs de una fuente no serán identificadores públicos.

### 6.4 Propiedad y resolución de conflictos

Antes de publicar un dominio se definirá el propietario del dato, su System of Record, autoridad por atributo, reglas de validación, frescura y proceso de corrección. La plataforma no decidirá automáticamente qué valor gana cuando existan discrepancias.

### 6.5 Protección de datos

Se aplicarán minimización, clasificación, finalidad de uso, retención, trazabilidad, enmascaramiento en entornos no productivos y eliminación segura. Los logs y métricas no incluirán tokens, secretos ni datos personales completos.

## 7. Contratos institucionales

### 7.1 APIs

Los contratos OpenAPI 3.1 se almacenarán en el repositorio y se someterán a lint, revisión y pruebas de compatibilidad. La implementación FastAPI deberá ajustarse al contrato aprobado. El OpenAPI generado se comparará automáticamente con el contrato estable.

Rutas iniciales propuestas:

- `/v1/registry/systems`
- `/v1/registry/apis`
- `/v1/institutions`
- `/v1/persons`
- `/health`, `/ready` y `/metrics` como endpoints técnicos internos

### 7.2 Respuestas y errores

Las respuestas usarán un formato consistente con data, pagination cuando corresponda y meta.correlationId. Los errores usarán Problem Details para HTTP APIs (RFC 9457), con type, title, status, detail, instance, code y correlationId. No se expondrán stack traces.

### 7.3 Paginación y filtros

La primera versión utilizará paginación por cursor para colecciones con alto cambio y permitirá paginación por página únicamente donde el total exacto sea un requisito. Los límites máximos serán configurables y documentados.

### 7.4 Idempotencia

Las operaciones de creación que puedan reintentarse aceptarán `Idempotency-Key`. La plataforma conservará el resultado durante un período definido y rechazará la reutilización de la misma clave con un payload diferente.

### 7.5 Eventos

Los eventos se documentarán mediante AsyncAPI 3 y JSON Schema. Usarán nombres estables, por ejemplo `person.created`, `person.updated`, `institution.created` e `institution.updated`.

Sobre mínimo: eventId, eventType, occurredAt, source, correlationId, causationId opcional, subject, version, data y metadata de clasificación cuando proceda.

## 8. Fiabilidad y consistencia

- Transactional outbox para cambios de datos y publicación consistente.
- Publisher confirms y exchanges/colas durables.
- Reintentos con backoff y jitter solo para errores transitorios.
- Dead-letter queues con alarmas y procedimiento de reproceso.
- Registro `processed_events` o inbox equivalente para idempotencia.
- Ordenamiento únicamente por clave de entidad cuando sea necesario.
- Circuit breaker y presupuestos de timeout en llamadas a fuentes.
- Cache solo con política explícita de frescura e invalidación.
- Degradación documentada cuando una fuente esté indisponible.

La plataforma no prometerá transacciones distribuidas entre sistemas. Los procesos multisistema usarán consistencia eventual y compensaciones cuando corresponda.

## 9. Seguridad e identidad

Keycloak será el proveedor de identidad abierto. Se usarán OAuth 2.0/OIDC, Authorization Code con PKCE para usuarios y Client Credentials para servicios. No se implementará autenticación casera.

Scopes iniciales: `registry.read`, `registry.write`, `institutions.read`, `institutions.write`, `persons.read` y `persons.write`.

Controles mínimos:

- TLS en tránsito y certificados gestionados institucionalmente.
- Validación de issuer, audience, firma, expiración, not-before y scopes.
- Separación entre interfaces públicas y administrativas de Keycloak.
- Denegación por defecto y mínimo privilegio.
- CORS restrictivo, límites de tamaño, rate limiting y protección ante sobrecarga.
- Cuentas técnicas por servicio y por conector.
- Secretos fuera de Git, con archivos protegidos por systemd credentials o gestor abierto aprobado.
- SBOM, hashes y firmas de artefactos cuando estén disponibles.
- Escaneo de dependencias y secretos en CI.
- Registro auditable de accesos y cambios administrativos.

OpenBao podrá evaluarse como gestor de secretos libre cuando la complejidad operacional lo justifique; no será una dependencia obligatoria del primer incremento.

## 10. Observabilidad y auditoría

OpenTelemetry será la capa estándar de instrumentación y exportación. Los servicios emitirán métricas Prometheus, logs JSON y trazas distribuidas mediante OTLP hacia un OpenTelemetry Collector.

Todos los flujos aceptarán o generarán `X-Correlation-ID` y propagarán W3C Trace Context. Correlation ID y trace ID aparecerán en respuestas, errores, logs y eventos cuando corresponda.

Métricas mínimas: tasa, errores y duración HTTP; saturación; disponibilidad de fuentes; llamadas upstream; eventos publicados y fallidos; profundidad de colas; dead letters; latencia de procesamiento y frescura del dato.

Prometheus almacenará métricas; Loki centralizará logs y Grafana OSS mostrará paneles y alertas. Las retenciones, cardinalidad y datos permitidos se definirán antes de producción.

La auditoría registrará actor o cliente, operación, recurso, fecha, resultado, servicio, fuente y correlation ID sin guardar secretos ni payloads sensibles completos.

## 11. Stack tecnológico libre y actual

- Sistema operativo: Ubuntu Server LTS, con preferencia por la versión LTS homologada y soportada por todos los componentes.
- Automatización: Ansible Core y scripts shell POSIX revisables.
- Lenguaje: Python en una versión soportada por el proyecto y sus dependencias.
- APIs: FastAPI, Pydantic 2, Uvicorn, SQLAlchemy 2 y Alembic.
- Acceso PostgreSQL: psycopg 3; uso asíncrono solo cuando aporte valor medido.
- Gestión Python: `pyproject.toml`, uv para resolución/entornos y lockfile versionado.
- Calidad: Ruff, mypy, pytest, coverage y Bandit o herramienta equivalente abierta.
- Gateway: Apache APISIX con etcd, instalado directamente y administrado por systemd.
- Identidad: Keycloak con PostgreSQL dedicado.
- Mensajería: RabbitMQ.
- Datos: PostgreSQL, con esquemas o bases y roles separados por servicio.
- Contratos: OpenAPI 3.1, AsyncAPI 3 y JSON Schema.
- Telemetría: OpenTelemetry Collector, Prometheus, Loki y Grafana OSS.
- Proxy/TLS: HAProxy.
- CI: jobs portables ejecutables desde shell; Forgejo Actions o Woodpecker CI como opción institucional libre.
- Artefactos: repositorio institucional libre compatible con paquetes Python y ficheros firmados.

No se fijarán números de versión de larga duración dentro de este documento. Antes de cada instalación se aprobará una matriz de versiones soportadas, licencias, CVE conocidas y compatibilidad. Las dependencias del proyecto sí quedarán bloqueadas de forma reproducible.

## 12. Despliegue físico sin contenedores

Topología inicial recomendada, ajustable según capacidad:

- VM01: HAProxy y Apache APISIX.
- VM02: Keycloak.
- VM03: RabbitMQ.
- VM04: PostgreSQL.
- VM05: servicios de dominio, Registry API y conectores.
- VM06: OpenTelemetry Collector, Prometheus, Loki y Grafana OSS.

Cada proceso tendrá usuario no privilegiado, directorio de trabajo explícito, entorno virtual o runtime dedicado, EnvironmentFile protegido, hardening de systemd, límites de recursos, reinicio controlado y health checks.

Los paquetes y binarios se obtendrán de repositorios oficiales, se verificarán y se mantendrá un inventario. Se documentarán firewall, DNS, NTP, certificados, backups, restauración, actualizaciones, rollback y continuidad.

La alta disponibilidad no se asumirá por instalar múltiples nodos: se diseñará después de establecer RPO, RTO, SLA, capacidad y presupuesto operacional.

## 13. Gobierno

### 13.1 Registry institucional

Registrará sistemas, dominios, APIs, eventos, versiones, propietarios, responsables técnicos, fuentes, consumidores, scopes, estado, SLA/SLO y enlaces a contratos.

Estados: DRAFT, DEVELOPMENT, TESTING, ACTIVE, DEPRECATED y RETIRED.

### 13.2 Incorporación de una fuente

1. Identificar propietario y responsable técnico.
2. Definir significado, calidad, autoridad y clasificación del dato.
3. Completar la matriz de capacidades.
4. Elegir el mecanismo de conector y su modelo de amenazas.
5. Aprobar contratos y criterios de aceptación.
6. Implementar observabilidad, pruebas y runbook.
7. Registrar la fuente y habilitarla progresivamente.

### 13.3 Incorporación de un consumidor

1. Registrar aplicación, responsable y finalidad.
2. Autorizar scopes y atributos mínimos.
3. Entregar contrato y entorno de prueba.
4. Ejecutar pruebas de contrato y capacidad.
5. Activar credenciales separadas y monitorización.

## 14. Estrategia de implementación

### Milestone 0 — Decisiones y arquitectura base

Validar idioma de contratos, dominios iniciales, propietarios, fuentes, requisitos de frescura, clasificación de datos, SLO y topología. Crear arquitectura, ADR, normas de API/eventos y modelo de amenazas inicial.

### Milestone 1 — Repositorio y servicios mínimos

Crear monorepo, toolchain Python, CI, biblioteca transversal mínima y esqueletos independientes de Registry, Instituciones y Personas con health, ready, metrics, correlation ID, logs JSON y errores estándar.

### Milestone 2 — Inventario de sistemas y capacidades

Catalogar sistemas y datos mediante entrevistas y evidencia técnica. No analizar la API anterior para reutilizarla. Seleccionar una fuente y un consumidor para el piloto de Instituciones.

### Milestone 3 — Registry API

Implementar catálogo de sistemas, interfaces, APIs, eventos, propietarios y consumidores con contrato y migraciones.

### Milestone 4 — Instituciones extremo a extremo

Definir contrato canónico, implementar servicio y conector seleccionado, seguridad, gateway, auditoría, eventos y observabilidad. Demostrar que un consumidor obtiene información sin conocer ni acceder a la fuente.

### Milestone 5 — Personas

Incorporar el dominio con especial atención a privacidad, mappings, autoridad por atributo y eventos confiables.

### Milestone 6 — Conectores adicionales

Agregar plantillas para HTTP, agente local, lectura controlada e importación de archivos. Incorporar sistemas por prioridad institucional.

### Milestone 7 — Endurecimiento productivo

Completar automatización Ansible, systemd, TLS, backups, restauración, alertas, seguridad, pruebas de carga y runbooks.

### Milestone 8 — Adopción progresiva

Incorporar consumidores, medir uso, calidad y SLO, y ampliar dominios según valor. La retirada de integraciones antiguas será un proyecto de adopción, no una dependencia arquitectónica.

## 15. Entregables

- Arquitectura lógica, física, de seguridad, datos, integración y observabilidad.
- ADR y estándares institucionales.
- Repositorio reproducible y pipeline libre.
- Registry API y catálogo de sistemas/capacidades.
- APIs de Instituciones y Personas.
- Framework y conectores iniciales.
- Contratos OpenAPI, AsyncAPI y JSON Schema.
- Configuración de APISIX, Keycloak y RabbitMQ.
- Migraciones PostgreSQL y mappings.
- Telemetría, dashboards y alertas.
- Automatización Ansible, unidades systemd y guía operacional.
- Pruebas unitarias, integración, contrato, arquitectura, seguridad y E2E.
- Matriz de riesgos, runbooks y evidencias de aceptación.

## 16. Criterios de aceptación del primer vertical

- Un consumidor obtiene un token en Keycloak y accede mediante HAProxy y APISIX.
- El scope requerido se valida en gateway y servicio.
- El consumidor consulta Instituciones sin acceso ni conocimiento de la base fuente.
- El conector transforma datos al modelo canónico aprobado.
- La indisponibilidad de la fuente produce un error controlado y observable.
- Correlation ID y trace context recorren todos los componentes.
- Una modificación publica un evento mediante outbox y un consumidor lo procesa de forma idempotente.
- OpenAPI y AsyncAPI pasan lint y pruebas de contrato.
- Prometheus, Loki y Grafana OSS permiten diagnosticar el flujo.
- Los procesos arrancan con systemd en Ubuntu sin contenedores.
- Backup y restauración del estado propio se han probado.
- No existe dependencia obligatoria de software privativo.

## 17. Riesgos principales

- **Fuente de verdad no acordada:** detener el dominio hasta obtener decisión del propietario.
- **Acceso directo convertido en solución permanente:** encapsularlo en conector, limitar privilegios y registrar plan de mejora.
- **Nuevo monolito de integración:** servicios por dominio y pruebas automáticas de dependencias.
- **Modelo canónico excesivo:** diseñar por casos de uso aprobados.
- **Duplicación o pérdida de eventos:** outbox, confirms, inbox, DLQ y reconciliación.
- **Plataforma como punto único de fallo:** presupuestos de error, HA proporcional al SLO y pruebas de recuperación.
- **Crecimiento operacional:** automatización, runbooks, ownership y límites de plataforma.
- **Fuga de datos personales:** minimización, scopes, auditoría, enmascaramiento y revisión de seguridad.
- **Dependencia comercial encubierta:** revisión de licencias y prueba de todas las funciones con ediciones libres.
- **Componentes desactualizados:** matriz de compatibilidad, SBOM y ciclo de parches.

## 18. Decisiones pendientes antes del desarrollo funcional

- Idioma definitivo de URLs y nombres públicos.
- Propietarios de Instituciones y Personas.
- Fuente autorizada y autoridad por atributo.
- Primer sistema fuente y primer consumidor del piloto.
- Frescura, volúmenes, concurrencia y SLO esperados.
- Clasificación y retención de datos personales.
- Topología de entornos y requisitos de continuidad.
- Política institucional de certificados y secretos.
- Distribución GNU/Linux LTS homologada y matriz de versiones.

## 19. Resultado esperado

La institución dispondrá de contratos estables y gobernados que permitan compartir información sin dependencias directas entre sistemas. Las aplicaciones podrán evolucionar de manera independiente; las fuentes sin backend participarán mediante conectores controlados; y la incorporación de nuevos dominios seguirá un proceso repetible, seguro y observable.

El valor central de la plataforma no será centralizar toda la lógica o copiar todas las bases de datos. Será establecer una frontera institucional de contratos, identidad, gobierno, calidad y trazabilidad.

