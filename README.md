# MES Interoperability Platform

Plataforma institucional para compartir información entre sistemas heterogéneos mediante APIs y eventos, sin acceso directo entre las bases de datos de los consumidores y los sistemas fuente.

## Estado

El servicio de notificaciones por correo está operativo y lo consumen varias aplicaciones,
según confirmación del responsable institucional. Esta integración local no modifica
su código, contrato, autenticación ni despliegue y no envía correos de prueba reales.

`registry-api` mantiene el catálogo futuro de sistemas/APIs/consumidores, distinto del
Registro de Personas. `institution-service` conserva su bootstrap técnico. La capacidad
Personas se incorpora para desarrollo local desde el repositorio independiente
`registro-personas`: modelo/migraciones y lógica funcional probados; las operaciones
privadas permanecen bloqueadas por falta de autenticación/autorización institucional
aprobadas. No hay rutas nuevas de gateway ni aprovisionamiento LDAP.

## Principios

- Contratos institucionales independientes de los sistemas fuente.
- Servicios separados por dominio; no monolito distribuido.
- Puertos y adaptadores para HTTP, agentes, bases de datos y archivos.
- Software libre, estándares abiertos y despliegue sin contenedores.
- Seguridad, privacidad y observabilidad desde el diseño.

## Requisitos

- Python 3.12 o 3.13 para la plataforma; Python 3.12 en el entorno propio de Personas.
- `uv` recomendado, o `venv` y `pip`.
- Personas requiere PostgreSQL para persistencia y migraciones en su repositorio propio;
  su vista local bloqueada puede arrancar sin base. RabbitMQ sigue pendiente para eventos.

## Preparación

Con `uv`:

```bash
uv sync --all-extras
```

Sin `uv`:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

En PowerShell, la activación es `.venv\Scripts\Activate.ps1`.

## Ejecución

```bash
python -m uvicorn mes_registry_api.main:app --app-dir services/registry-api/src --port 8001
python -m uvicorn mes_institution_service.main:app --app-dir services/institution-service/src --port 8002
python tools/run_persons.py --service-root /ruta/al/repositorio/registro-personas
```

Swagger UI queda disponible en `/docs` y el contrato generado en `/openapi.json`.

La plataforma sirve la interfaz Personas en `127.0.0.1:8003`; el Registro independiente
escucha en `127.0.0.1:8013` y desactiva el access log. Su `/health/live` devuelve 200,
mientras `/health/ready` y operaciones privadas devuelven 503. El bootstrap anterior `mes_person_service` y las unidades
systemd existentes quedan intactos como legado; no arrancarlos junto al servicio
externo en el mismo puerto. La integración local no instala/reinicia servicios.
Pasos verificables en [integración de Personas](docs/interoperabilidad/integracion-registro-personas.md).

## Calidad

```bash
python -m ruff check .
python -m mypy shared/python services
python -m pytest
```

## Estructura

- `contracts/`: contratos OpenAPI, AsyncAPI y esquemas.
- `docs/`: arquitectura, ADR, gobierno, seguridad y operación.
- `services/`: procesos desplegables independientes.
- `shared/python/`: capacidades técnicas, nunca reglas de dominio.
- `connectors/`: futuros adaptadores a sistemas fuente.
- `deployment/`: Ansible, systemd, HAProxy y scripts revisables.
- `gateway/`, `identity/`, `messaging/`, `observability/`: configuración futura de componentes libres.

## Próximo milestone

Completar el inventario y primer vertical de Instituciones; para Personas, acordar
autenticación compatible con ADR-0002, permisos por recurso y contrato antes de
publicarlo. El correo existente sigue funcionando bajo su operación actual; este
trabajo no habilita Client Credentials ni cuentas de servicio nuevas.

