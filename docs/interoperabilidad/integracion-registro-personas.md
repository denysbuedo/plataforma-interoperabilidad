# Integración local del Registro de Personas

Estado: desarrollo local comprobable, **sin publicación institucional**. Personas es
una capacidad de esta plataforma cuya implementación vive en el repositorio independiente
`registro-personas`. Se reutiliza ese servicio; el `person-service` de la plataforma
solo sirve la UI/proxy y no duplica su modelo ni consulta sus tablas. ADR-012 aprueba
el flujo de operador PER-002, no la publicación productiva ni cambios de Keycloak.

El correo existente sigue operativo y utilizado por varias aplicaciones, según el
responsable. Este cambio no modifica ni prueba contra su endpoint real. El futuro
aprovisionamiento LDAP será una capacidad central separada publicada por la plataforma,
con autorización/auditoría y destino por política; no forma parte de esta implementación.
Persona, vínculo digital y solicitud de cuenta son operaciones distintas.

## Arranque verificable

Preparar Python 3.12 y dependencias del repositorio Personas siguiendo su README.
Desde la raíz de la plataforma (su propio Python puede ser 3.12 o 3.13):

```powershell
.venv/Scripts/python.exe tools/run_persons.py --service-root 'D:/TRABAJO/Desarrollo/registro-personas' --check
.venv/Scripts/python.exe tools/run_persons.py --service-root 'D:/TRABAJO/Desarrollo/registro-personas'
```

En Ubuntu: `.venv/bin/python tools/run_persons.py --service-root /ruta/registro-personas`.
Con Make: `make run-persons PERSONS_ROOT=/ruta/registro-personas`.
Ctrl+C detiene el proceso local. No se instala ningún paquete, no se migra BD y no
se cambia/reinicia ninguna unidad systemd existente.

Para iniciar ambos procesos con una configuración institucional autorizada,
el proxy/UI de plataforma se ejecuta en una terminal y Personas en otra:

```powershell
# Terminal 1, plataforma; completar emisor y claves con los valores institucionales autorizados.
$env:OIDC_ISSUER_URL = '<emisor HTTPS institucional asignado>'
$env:OIDC_AUDIENCE = 'mes-api'
$env:OIDC_PUBLIC_KEY_FILE = '<ruta local a clave pública OIDC>'
$env:PERSONS_OIDC_ISSUER_URL = '<mismo emisor HTTPS institucional>'
$env:PERSONS_OIDC_CLIENT_ID = 'interoperabilidad-admin'
$env:PERSONS_OIDC_REDIRECT_URI = 'http://127.0.0.1:8003/admin/personas'
$env:PERSONS_AUTHORIZATION_POLICY_FILE = '<ruta local protegida a política de operadores>'
$env:PERSONS_DELEGATION_ISSUER = '<emisor HTTPS único de delegación de la plataforma>'
$env:PERSONS_DELEGATION_AUDIENCE = 'registro-personas'
$env:PERSONS_DELEGATION_KEY_ID = 'per002-key-1'
$env:PERSONS_DELEGATION_PRIVATE_KEY_FILE = '<ruta local protegida a clave privada RS256>'
.venv/Scripts/python.exe -m uvicorn mes_person_service.main:app --app-dir services/person-service/src --host 127.0.0.1 --port 8003 --no-access-log

# Terminal 2, Registro; DB y clave pública deben pertenecer al entorno autorizado.
$env:REGISTRY_DATABASE_URL = 'postgresql+psycopg://per001_local@127.0.0.1:55438/per001_dev'
$env:REGISTRY_DELEGATION_ISSUER = '<mismo emisor HTTPS de delegación de plataforma>'
$env:REGISTRY_DELEGATION_AUDIENCE = 'registro-personas'
$env:REGISTRY_DELEGATION_KEY_ID = 'per002-key-1'
$env:REGISTRY_DELEGATION_PUBLIC_KEY_FILE = 'C:\ruta\local\delegation-public.pem'
D:\TRABAJO\Desarrollo\registro-personas\.venv\Scripts\python.exe -m registro_personas --port 8013
```

El URL local autorizado provisional es `http://127.0.0.1:8003/admin/personas`.
La plataforma se sirve en el puerto 8003 y procesa en esa misma ruta el callback
OIDC (`code`/`state`), intercambia el código con PKCE y limpia la query antes de
mostrar el módulo. El puerto 8003 no corresponde al Registro: este escucha en
8013. El responsable informa el hostname `persona.reduniv.edu.cu` para la API de
Personas en `[IP_INTERNA]:8003`; ese puerto es del backend y no forma parte de la
URL pública. La URL pública es `https://persona.reduniv.edu.cu`. `/ready` responde
200 y `/` devuelve 404 de la aplicación. Esa evidencia no confirma qué aplicación sirve allí ni que
`/admin/personas` esté publicada. La callback institucional candidata es
`https://persona.reduniv.edu.cu/admin/personas`, solo si se confirma que ese host
sirve la interfaz/proxy de la plataforma en esa ruta. La callback se configura
explícitamente y no se construye desde `Host` del navegador. HTTP solo se acepta
para loopback local; el entorno institucional requiere HTTPS y URI exacta. El emisor HTTPS
de Keycloak sigue pendiente; no iniciar login institucional hasta confirmar la ruta,
el emisor y la configuración del cliente.

El lanzador comprueba identidad del proyecto, metadata Python 3.12 de su virtualenv
y coincidencia SHA-256 de los contratos. `--check` solo lee archivos; la prueba HTTP
posterior comprueba que la instalación puede ejecutar el servicio realmente.
El proceso usa el Python/paquete de Personas, no importa otros servicios ni comparte
su base. Elimina destinos BD/OIDC PostgreSQL y variables de inyección Python heredadas.
La plataforma ocupa `8003`; para evitar el puerto duplicado el servicio externo queda
en `127.0.0.1:8013`. El lanzador retira la configuración OIDC/DB del entorno hijo;
por ello las rutas privadas siguen cerradas en la prueba de composición.

Desde la ficha de una persona consultable, el módulo permite asociar otra referencia
de origen. La operación exige `persons.read`, `persons.review`, `persons.link` y
`persons.source.<alias>` para la nueva fuente; Personas valida los permisos de nuevo,
conserva la procedencia y audita creación o repetición. Si la referencia ya pertenece
a otra persona, responde 409 y registra un caso pendiente sin reasignar ni fusionar.

| Dirección local por defecto | Resultado |
|---|---|
| `http://127.0.0.1:8003/admin/personas` | Interfaz administrativa de la plataforma |
| `http://127.0.0.1:8003/docs` | API/documentación de la plataforma |
| `http://127.0.0.1:8013/docs` | API/documentación del servicio independiente |
| `/health/live` | 200: proceso vivo |
| `/health/ready` | 503: todavía no listo para operaciones privadas |
| `/v1/personas` y demás operaciones privadas | 503 antes de consultar BD |

El arranque autónomo de Personas mantiene el puerto 8000 por defecto. El servidor
del contrato es un ejemplo; el lanzador usa 8013. No arrancar dos procesos sobre el
mismo puerto. La UI realiza Authorization Code + PKCE. El backend valida el access
token OIDC y emite por operación un JWT RS256 delegado con audiencia
`registro-personas`, permisos y fuentes mínimas, `sub`/`actor_iss` del operador y
TTL de 60 segundos (máximo 120). Para vincular referencias exige `persons.link` y
delega `persons.references.link`, independiente del vínculo de cuentas. Registro
valida ese JWT con la clave pública configurada; el bearer OIDC no se reenvía.
No hay reglas nuevas HAProxy/APISIX ni cambios en el gateway.

## Contrato coordinado y prueba de composición

`contracts/openapi/person-service.yaml` es copia exacta del contrato provisional del
servicio. `contracts/openapi/persons-operator-api.yaml` documenta las rutas privadas
de operador en la plataforma. `services/person-service/external-service.json` registra implementación,
estado DRAFT, fingerprint y comprobaciones técnicas. El OpenAPI oficial del repositorio
de gobierno no cambia. Ante cambio del contrato: coordinar servicio/consumidores,
actualizar la copia y su fingerprint juntos; una diferencia impide el arranque local.
No modificar solo el hash para ocultar una discrepancia.

```powershell
.venv/Scripts/python.exe -m tools.check_persons_integration --service-root 'D:/TRABAJO/Desarrollo/registro-personas'
.venv/Scripts/python.exe -m pytest -o addopts= -p no:cacheprovider tests/unit/test_persons_launcher.py -q
```

La prueba integral operador→plataforma→Registro con token RSA ficticio y PostgreSQL
local se ejecuta desde `registro-personas` con `PER002_PLATFORM_ROOT` y
`REGISTRY_TEST_DATABASE_URL` apuntando a la base aislada `per001_test` (ver su README).
No llama al IdP ni sale a la red.

La prueba de composición arranca el servicio externo en puerto loopback efímero, comprueba
liveness/OpenAPI 200, readiness y operaciones privadas 503 incluso con un
Bearer ficticio, verifica que los logs no reflejan el marcador de referencia y
termina el hijo. Ignora proxies y rechaza redirecciones: no contacta IAM, SMTP, LDAP
ni bases. No envía correo ni prueba credenciales reales.

## Pendientes y reversión

Para login real falta configurar en Keycloak el cliente institucional
`interoperabilidad-admin` con Authorization Code + PKCE S256, cuentas LDAP
existentes, sin client credentials, y callback local exacta
`http://127.0.0.1:8003/admin/personas`. No se ha modificado Keycloak. Se informó
`persona.reduniv.edu.cu` como host de API Personas, pero `/ready`=200 y `/`=404 no
confirman que `/admin/personas` llegue al proxy de la plataforma. Validar con el
propietario de ese despliegue antes de usar la callback candidata
`https://persona.reduniv.edu.cu/admin/personas`. Los permisos (`persons.read`, `persons.register`, `persons.review`,
`persons.link` y `persons.source.<alias>`) provienen de política propia de la
plataforma ligada a `iss`/`sub`, no de roles OIDC; `api-reader/api-writer` tampoco
conceden acceso. La política externa se configura con
`PERSONS_AUTHORIZATION_POLICY_FILE`; sin ella la plataforma deniega. También se
configura por entorno la clave pública OIDC para la plataforma, clave privada de
delegación y su clave pública en Registro, además de una base local. La vinculación de cuentas,
verificación de titularidad y publicación productiva quedan fuera. No habilitar
Service Accounts/Client Credentials para solventar el flujo operador.

Rollback local: detener el proceso iniciado por el lanzador; restaurar en una revisión
coordinada el contrato de bootstrap y el comando de desarrollo si se descarta esta
integración. No hay datos migrados ni configuración institucional que revertir. Los
archivos y unidades previos del correo permanecen intactos.

## Resultado de esta sesión (2026-11-19)

- Registro de Personas: 46 pruebas aprobadas con PostgreSQL local ficticio; migración
  y reversión cubiertas. Clúster de pruebas detenido al terminar.
- Plataforma: 25 pruebas aprobadas con configuración OIDC/SMTP sintética; regresión
  de correo con dobles, sin envíos reales. Un aviso de deprecación Starlette/httpx en
  cada suite, sin pruebas fallidas ni omitidas en las ejecuciones finales.
- Preflight y comprobación HTTP externa correctos; el hijo efímero se terminó.
- Ruff correcto sobre archivos Python modificados; formato comprobado en Personas.
- SHA-256 sin diferencias en los seis archivos protegidos de correo, seguridad/app
  compartidos y unidades systemd existentes. Contratos origen/espejo idénticos.
- Sin instalación/despliegue, publicación remota, cambios al gobierno ni conexiones
  institucionales. Las decisiones de publicación y autenticación siguen pendientes.
