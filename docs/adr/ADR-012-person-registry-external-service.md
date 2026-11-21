# ADR-012: Registro de Personas como servicio independiente de la plataforma

- **Estado:** APROBADO para el flujo de operador PER-002 descrito en esta decisión; publicación productiva, M2M y los pendientes institucionales no quedan aprobados por extensión.
- **Fecha:** 2026-11-19; actualización acotada PER-002: 2026-11-20.
- **Decisor:** orquestador humano / responsables de Personas e Interoperabilidad.
- **Referencias:** PER-001 y ADR-0002 del repositorio de gobierno; ADR-006 y ADR-008 de esta plataforma.

## Contexto

La plataforma reserva `person-service`, pero su implementación actual contiene solo
endpoints técnicos y el contrato anterior no tenía operaciones de dominio. El MVP
`registro-personas`, creado en un repositorio Git independiente, implementa UUID
institucional, referencias únicas de origen, vínculos de cuentas, procedencia y
persistencia PostgreSQL con migraciones y pruebas.

El orquestador confirmó en esta sesión que el servicio de correo de la plataforma
funciona y lo consumen varias aplicaciones. Este antecedente es una confirmación
del responsable, no una prueba productiva ejecutada en este trabajo. Incorporar
Personas no requiere cambiar, sustituir ni interrumpir ese servicio.

## Decisión

1. Cubrir la capacidad de Personas de la plataforma con `registro-personas`, sin
   desarrollar un segundo registro institucional ni replicar su lógica en el
   esqueleto `services/person-service`.
2. Conservar repositorios, proceso, entorno Python y ownership de persistencia
   independientes. La integración de ejecución local inicia el servicio mediante
   su intérprete y `python -m registro_personas --port 8013`, limitado a loopback.
   En la composición PER-002, `person-service` de la plataforma conserva el puerto
   8003 para el proxy y la interfaz de operador, y llama al servicio independiente
   en `127.0.0.1:8013`; ambos procesos tienen puertos distintos.
   No importar código de otros servicios ni consultar sus bases de datos.
3. Mantener las rutas actuales `/v1/personas` y `/v1/referencias/resolver` del MVP.
   PER-002 incorpora una superficie de operador en la plataforma bajo
   `/api/v1/personas`; su adaptador HTTP llama a esas rutas del servicio mediante
   loopback, sin importar su código ni consultar su base. El contrato específico
   de operador se mantiene separado del espejo del servicio. Esta decisión no
   publica rutas del gateway ni autoriza endpoints productivos.
4. Mantener `contracts/openapi/person-service.yaml` como espejo exacto del contrato
   provisional de `registro-personas/docs/openapi.yaml`, con comprobación de hash
   para detectar divergencias. No modificar unilateralmente ninguna copia: primero
   coordinar cambios en el servicio y después actualizar el espejo y su referencia.
5. Conservar denegación predeterminada cuando falte configuración o autorización.
   PER-002 autentica al operador con OIDC interactivo Authorization Code + PKCE.
   Tras validar firma, emisor, audiencia, vigencia e identidad OIDC, la plataforma
   emite por operación una autorización delegada RS256, de audiencia exclusiva
   `registro-personas`, con permisos/fuentes acotados, `sub` y `actor_iss` del
   operador, `jti` y vida máxima de 120 segundos (60 por defecto). Registro valida
   firma y claims con clave pública fijada/configurada. El bearer OIDC original no
   se reenvía. No se usan `client_credentials`, cuentas técnicas locales nuevas,
   ni cabeceras de actor/permisos como identidad confiable.
6. La plataforma valida la identidad OIDC (`iss`/`sub`) y obtiene los permisos
   funcionales de una política propia, externa al repositorio y mantenida por la
   aplicación; no consume roles funcionales de Keycloak. Esa política asigna
   `persons.read` para lectura, `persons.register` para registro controlado,
   `persons.review` para revisión, `persons.link` para vincular referencias y
   `persons.source.<alias>` para cada origen permitido. `persons.review` no confiere
   por sí solo creación, acceso global ni reasignación de personas. Los roles
   genéricos `api-reader`, `api-writer` y `api-admin` no sustituyen estos permisos.
   Validar operación, sistema de origen y recurso en ambos servicios; filtrar
   listado y conteo antes de paginar. Sin rol de fuente no hay acceso a fuentes.
7. Limitar PER-002 a registro, consulta y resolución por referencia exacta según
   el contrato coordinado. Se incluyen referencias de una persona filtradas por
   fuente autorizada y la lista de metadatos opacos de colisiones pendientes con
   `persons.review`, restringida a `source_reference_collision`. Esa lista no
   divulga referencias, sujetos ni personas existentes, y no habilita resolución.
   Las colisiones siguen requiriendo revisión sin fusión ni reasignación automática.
   No exponer vinculación de cuentas, aprovisionamiento LDAP, contribuciones
   genéricas ni un verificador de titularidad improvisado.
8. Mantener `contracts/openapi/persons-operator-api.yaml` como contrato de la
   superficie de operador. Las rutas `/api/v1/personas`, su detalle, referencias y
   revisión son de la plataforma; su correspondencia con las rutas `/v1` se declara
   en el contrato y no cambia el ownership ni exige un cambio del gateway.

El contrato del servicio conserva su servidor de desarrollo `127.0.0.1:8000`;
la composición local PER-002 utiliza 8003 para la plataforma y 8013 para
`registro-personas`. Esta separación evita la colisión entre los dos procesos;
no altera rutas ni configura un despliegue o endpoint institucional. El contrato
sigue siendo provisional:
su incorporación a esta carpeta no lo declara ACTIVE ni ratifica el borrador de
Personas del repositorio de gobierno.

## Límites de seguridad y ownership pendientes

La autenticación M2M de Personas sigue pendiente de aprobación. La autorización
aprobada aquí se limita al flujo humano interactivo y a los roles/orígenes anteriores;
no constituye autorización general de integración entre aplicaciones autónomas.
No se aplica automáticamente el procedimiento existente de Client Credentials y
Service Accounts de otros servicios: ADR-0002 exige comprobar su impacto sobre
usuarios técnicos locales. No se habilitan clientes, cuentas, secretos, grants ni
flujos nuevos en Keycloak.

Crear una Persona no crea una cuenta LDAP. El futuro aprovisionamiento se publicará,
si se aprueba su diseño, como una capacidad central autorizada de la plataforma,
separada del registro. Solo ese componente autorizado podría escribir en LDAP;
las aplicaciones consumirían su API. Este ADR no define ni implementa ese endpoint,
no ratifica su contrato y no autoriza ninguna escritura, provisión o importación.

Antes de publicación institucional deben decidirse: propietario funcional/técnico
de Personas, gobierno de `person_id`, permisos por recurso y origen, verificador
confiable de titularidad para una futura vinculación de cuentas, configuración
institucional del flujo interactivo aprobado, retención, roles mínimos de BD,
contrato revisado, despliegue y rollback. La separación de dominios de ADR-0001 de
gobierno continúa propuesta y no se presenta aquí como ratificada.

## Consecuencias

- Una sola implementación del Registro de Personas, con trazabilidad al contrato
  y pruebas del MVP; no nace una segunda plataforma de interoperabilidad.
- El catálogo/runtime local puede identificar la capacidad sin darla por publicada.
- La base de Personas no se comparte con Notificaciones ni con otros servicios.
- No se exige instalar dependencias de Personas en el entorno de Notificaciones.
- El esqueleto histórico y las unidades de producción no se sustituyen ni se
  activan automáticamente. La activación futura requiere un encargo específico.
- La interfaz de operador es un consumidor/adaptador de la plataforma; Personas
  conserva su ownership, transacciones, referencias, idempotencia y persistencia.
  No se duplican perfiles, permisos de negocio ni catálogos en la plataforma.

## Validación y reversión de esta preparación

Comprobar igualdad byte a byte/hash del espejo, arranque de la implementación
externa correcta y aislamiento loopback. Sin configuración aprobada deben rechazarse
las operaciones privadas antes de conectar a persistencia. Las pruebas del flujo
PER-002 usan tokens firmados ficticios y adaptadores locales: comprobar validación
independiente, roles de operación/fuente, no divulgación y conflictos. No enviar
correos ni consultar Keycloak, LDAP, gateway o producción durante estas pruebas.

La reversión local consiste en volver a usar el comando de bootstrap anterior y
retirar la referencia al servicio externo. No requiere eliminar Personas, modificar
datos ni intervenir Notificaciones. El rollback de un despliegue institucional
futuro deberá diseñarse y probarse por separado.

## Alternativas consideradas

- Duplicar el Registro de Personas dentro de la plataforma: descartado como
  propuesta por riesgo de divergencia de identificadores, vínculos y correcciones.
- Copiar el código o importar directamente un servicio desde otro: no conserva
  independencia de despliegue y dependencias.
- Exponer una segunda implementación del dominio en la plataforma: descartado.
  PER-002 sí justifica un adaptador de operador con contrato propio para su interfaz,
  pero mantiene todo el dominio y persistencia en `registro-personas`.
- Activar M2M existente por conveniencia: incompatible con el bloqueo de revisión
  arquitectónica vigente para Personas.
