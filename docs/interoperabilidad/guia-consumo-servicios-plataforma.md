# Comunicado técnico: consumo de servicios de la Plataforma de Interoperabilidad

**Dirigido a:** equipos técnicos responsables de aplicaciones institucionales  
**Emite:** Equipo de Interoperabilidad  
**Propósito:** establecer el procedimiento para integrar una aplicación con un servicio publicado por la Plataforma, con autenticación OAuth2, transporte HTTPS y configuración de red validada.

Cada aplicación debe completar estos pasos antes de habilitar llamadas reales. Los nombres de cliente, roles, contratos y límites se confirman con los responsables del servicio; no se deben deducir de los ejemplos de este documento.

## Paso 1. Identificar el servicio y acordar el contrato

Antes de configurar la aplicación, el equipo consumidor debe solicitar al Equipo de Interoperabilidad:

- URL base y ruta exacta del servicio.
- Especificación OpenAPI vigente o contrato de solicitud/respuesta.
- Método HTTP, encabezados requeridos, tipos y límites del cuerpo.
- Esquema de autenticación, audiencia y rol requerido.
- Errores, límites de frecuencia, reintentos, idempotencia y comportamiento ante timeout.
- Ambiente habilitado y procedimiento de prueba controlada.

Definir también quién es el responsable funcional de los datos, qué información se enviará y si contiene datos personales o sensibles. No enviar información real hasta obtener la autorización funcional correspondiente.

## Paso 2. Solicitar el cliente técnico a Identidad

El equipo de la aplicación coordina con Identidad la creación o validación de un cliente técnico en el realm `interoperabilidad`, usando OAuth 2.0 Client Credentials.

Identidad debe confirmar por un canal seguro:

- `client_id` exacto.
- Secreto del cliente.
- Cuenta de servicio habilitada.
- Audiencia `mes-api`.
- Rol específico requerido por el servicio.
- Confirmación de que Authorization Code, Implicit y Direct Access Grants están deshabilitados para ese cliente.

El token URL institucional es:

```text
https://identidad.reduniv.edu.cu/realms/interoperabilidad/protocol/openid-connect/token
```

No se debe reutilizar el cliente técnico de otra aplicación. Cada sistema tendrá su propio cliente y secreto para poder revocar o rotar sus credenciales de forma independiente. La contraseña SMTP no se entrega a las aplicaciones consumidoras.

## Paso 3. Solicitar y validar conectividad con TI

Las aplicaciones alojadas en nuestra infraestructura deben acceder a Keycloak y a la API institucional por HTTPS mediante el HAProxy interno `[IP_INTERNA]:443`, conservando los nombres DNS originales:

- `identidad.reduniv.edu.cu`, para obtener tokens.
- `api.reduniv.edu.cu`, para consumir los servicios.

Este procedimiento configura conexiones salientes iniciadas por la aplicación. **No es un cambio del vhost de HAProxy.** La aplicación no debe conectarse directamente a la VM del servicio ni al puerto backend `8004`; el acceso al backend de notificaciones está limitado a HAProxy (`[IP_INTERNA]`). TI debe validar la ruta desde cada VM consumidora.

## Paso 4. Configurar resolución de nombres

Se prefiere la resolución institucional DNS. Si TI indica utilizar `/etc/hosts` en la VM de la aplicación:

1. Revisar las entradas existentes de `identidad.reduniv.edu.cu` y `api.reduniv.edu.cu`; resolver cualquier mapeo contradictorio antes de editar.
2. Crear y verificar una copia de `/etc/hosts` antes de modificarlo.
3. Añadir una sola entrada coherente:

   ```text
   [IP_INTERNA] identidad.reduniv.edu.cu api.reduniv.edu.cu
   ```

4. Comprobar la resolución:

   ```bash
   getent hosts identidad.reduniv.edu.cu api.reduniv.edu.cu
   ```

No sustituir las URL HTTPS por direcciones IP: los nombres originales permiten validar el certificado TLS correcto.

## Paso 5. Excluir estos destinos del proxy en la aplicación

Si el cliente HTTP de la aplicación utiliza proxy de salida, añadir ambos nombres a `NO_PROXY` y `no_proxy`, conservando las exclusiones existentes:

```text
identidad.reduniv.edu.cu,api.reduniv.edu.cu
```

No borrar otras exclusiones ni deshabilitar globalmente el proxy. Aplicar la configuración al proceso que realmente realiza las llamadas —por ejemplo, PHP-FPM o un worker—, no solo a la terminal del administrador. Recargar o reiniciar de forma controlada el proceso si resulta necesario y verificar que heredó la configuración.

## Paso 6. Comprobar conectividad y TLS

Después de configurar resolución y proxy, ejecutar desde la VM las siguientes comprobaciones sin forzar resolución ni exclusión con parámetros de `curl`:

```bash
curl --connect-timeout 5 --max-time 15 \
  https://identidad.reduniv.edu.cu/realms/interoperabilidad/.well-known/openid-configuration

curl --connect-timeout 5 --max-time 15 \
  https://api.reduniv.edu.cu/ready
```

La primera debe devolver el documento de descubrimiento OIDC del realm `interoperabilidad`; la segunda debe devolver el estado de disponibilidad del API, normalmente `{"status":"ready"}`. Estos comandos conservan la validación TLS predeterminada. No usar opciones como `--insecure` o `-k`.

Repetir la verificación desde el cliente HTTP y el proceso real de la aplicación, porque una prueba desde la terminal no demuestra que PHP-FPM o los workers tengan la misma configuración. `/ready` confirma disponibilidad, pero no prueba autenticación ni envía notificaciones.
## Paso 7. Obtener y validar el token

Solicitar el token mediante `POST` al token URL, con `Content-Type: application/x-www-form-urlencoded` y estos campos:

```text
grant_type=client_credentials
client_id=<client_id asignado>
client_secret=<secreto entregado por Identidad>
```

El cliente debe usar el token como portador en las llamadas al API:

```http
Authorization: Bearer <access_token>
```

Antes de probar el servicio, confirmar de forma segura que el token incluye la audiencia `mes-api` y el rol requerido. No imprimir el token completo, no pegarlo en chats o tickets y no incluirlo en logs. La API valida firma, emisor, audiencia, expiración y roles.

## Paso 8. Probar el contrato sin habilitar aún el envío general

Usar la operación de comprobación documentada por el servicio, si existe. Para SGU, la comprobación indicada es:

```bash
php bin/console app:interop:notifications:check
```

La comprobación debe verificar, como mínimo, conectividad HTTPS, token válido, audiencia correcta y rol requerido. No debe mostrar ni registrar secretos o tokens.

Para una prueba funcional que produzca efectos (por ejemplo, enviar correo), usar un único destinatario de prueba autorizado y acordado con el responsable del servicio. Un healthcheck o un token válido no reemplazan esta prueba.

## Paso 9. Habilitar producción mediante una activación controlada

Mantener deshabilitada la función de integración mediante la bandera de la aplicación mientras falla cualquier verificación. En SGU, la bandera es:

```text
INTEROP_NOTIFICATIONS_ENABLED=0
```

Solo después de que conectividad, TLS, token, audiencia, rol y contrato sean correctos:

1. Coordinar una única operación funcional controlada.
2. Confirmar el código HTTP y el resultado en el sistema receptor.
3. Activar la bandera de producción conforme al procedimiento del equipo de la aplicación.
4. Comprobar que el cambio fue aplicado al proceso real que ejecuta las notificaciones.

Para el endpoint de correo, `202` y `accepted_by_relay` significan que el relay SMTP aceptó el mensaje; no garantizan su entrega final al buzón.

## Paso 10. Manejar errores, reintentos y registros

Cada consumidor debe seguir el contrato del servicio. No asumir que existe idempotencia o que los reintentos son seguros.

Para el endpoint actual de correo:

- No hay `Idempotency-Key`, deduplicación, `Retry-After` ni reintentos automáticos en la plataforma.
- Repetir una solicitud puede enviar un segundo correo.
- Ante timeout, `500` o `502`, el resultado puede ser ambiguo. No repetir automáticamente; coordinar la verificación antes de un nuevo envío.
- Ante `401`, corregir token/expiración; ante `403`, corregir roles; ante `422`, corregir el cuerpo; ante `503`, esperar a que se resuelva la causa operativa.

Los logs de la aplicación deben incluir estado HTTP y correlación para diagnóstico, nunca secretos, tokens ni datos sensibles del cuerpo. No registrar encabezados `Authorization`.

## Paso 11. Documentar y mantener la integración

El equipo consumidor documentará internamente:

- Servicio y versión del contrato consumido.
- `client_id` (nunca el secreto), audiencia y rol concedido.
- URL/realm usados y responsables técnicos.
- Regla de red aplicada, resolución DNS o entrada `/etc/hosts` y proxy configurado.
- Fecha y resultado de la prueba controlada.
- Bandera de activación y procedimiento de deshabilitación.

Rotar el secreto con Identidad cuando corresponda y actualizarlo en el almacén seguro de la aplicación. Si la integración deja de usarse, deshabilitarla y solicitar la revocación del cliente o sus roles.

## Lista de cierre

- [ ] Contrato y ambiente confirmados con Interoperabilidad.
- [ ] Cliente técnico propio creado por Identidad; audiencia y rol verificados.
- [ ] Secretos almacenados de forma segura y ausentes de logs/repositorios.
- [ ] Red, resolución y proxy validados desde la VM.
- [ ] TLS validado con nombres HTTPS, sin desactivar certificados.
- [ ] Verificación desde el proceso real de la aplicación satisfactoria.
- [ ] Prueba funcional única coordinada y resultado confirmado.
- [ ] Activación productiva autorizada y procedimiento de rollback documentado.


