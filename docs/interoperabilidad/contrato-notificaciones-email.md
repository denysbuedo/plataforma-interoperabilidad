# Contrato de notificaciones por correo

**Estado:** contrato definitivo del servicio, contrastado con la implementación  
**Fecha de revisión:** 2026-10-26  
**Ruta pública:** `POST https://api.reduniv.edu.cu/api/v1/notifications/email`  
**Versión de ruta:** `/api/v1`  
**Versión declarada del servicio:** `0.1.0`

Este documento describe el comportamiento implementado en `notification-service`. Las limitaciones identificadas se marcan como tales y no deben interpretarse como controles ya aplicados.

## Autenticación

Obtener un token de Keycloak usando OAuth 2.0 Client Credentials:

```text
POST https://identidad.reduniv.edu.cu/realms/interoperabilidad/protocol/openid-connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
client_id=passbolt
client_secret=<secreto entregado por Identidad>
```

El token debe tener audiencia `mes-api` y rol `notification-sender`. En la llamada al servicio:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

El secreto solo se conserva en el gestor seguro de configuración de la aplicación. Nunca se envía al servicio de correo ni se escribe en logs.

## Solicitud JSON

Se admite un destinatario por solicitud. `recipient`, `subject` y `text_body` son obligatorios. `html_body` es opcional y puede omitirse o ser `null`.

| Campo | Tipo | Requerido | Restricción implementada |
|---|---|---:|---|
| `recipient` | string | Sí | Debe tener formato de dirección de correo válido (`EmailStr`). |
| `subject` | string | Sí | Entre 1 y 200 caracteres. |
| `text_body` | string | Sí | Entre 1 y 20 000 caracteres. |
| `html_body` | string o `null` | No | Máximo 50 000 caracteres. Si se proporciona, se añade como alternativa HTML junto al cuerpo texto. |

No hay campos implementados para `cc`, `bcc`, remitente, adjuntos ni plantillas. El remitente se toma de la configuración del servicio (`EMAIL_FROM`). Por defecto, los campos JSON adicionales se ignoran; los clientes deben enviar únicamente los campos documentados.

Ejemplo:

```http
POST /api/v1/notifications/email HTTP/1.1
Host: api.reduniv.edu.cu
Authorization: Bearer <access_token>
Content-Type: application/json
X-Correlation-ID: 2c385f21-8f2a-4f7c-94b6-a9652242616f

{
  "recipient": "persona@example.org",
  "subject": "Aviso del sistema",
  "text_body": "El trámite fue actualizado.",
  "html_body": "<p>El trámite fue actualizado.</p>"
}
```

El encabezado `X-Correlation-ID` es opcional. Debe contener un UUID; si falta o no es válido, el servicio genera uno. La respuesta incluye el identificador usado en `X-Correlation-ID`.

## Respuesta exitosa

El servicio realiza la entrega al relay SMTP de forma síncrona. Si el relay acepta el mensaje, responde:

```http
HTTP/1.1 202 Accepted
Content-Type: application/json
X-Correlation-ID: 2c385f21-8f2a-4f7c-94b6-a9652242616f

{"status":"accepted_by_relay"}
```

`202` confirma la aceptación del mensaje por el relay SMTP; **no confirma que llegó al buzón del destinatario**. No existe actualmente una consulta posterior del estado de entrega.

## Errores

Los errores usan `application/json` con esta estructura común:

```json
{
  "type": "about:blank",
  "title": "HTTP error",
  "status": 403,
  "detail": "Insufficient permissions",
  "instance": "/api/v1/notifications/email",
  "code": "HTTP_ERROR",
  "correlationId": "2c385f21-8f2a-4f7c-94b6-a9652242616f"
}
```

| HTTP | `code` | Cuándo ocurre / acción del cliente |
|---:|---|---|
| `401` | `HTTP_ERROR` | Token ausente, inválido, vencido o con issuer/audience incorrectos. Obtener un token válido; no reintentar la misma petición sin corregir autenticación. Incluye `WWW-Authenticate: Bearer`. |
| `403` | `HTTP_ERROR` | Token válido sin el rol `notification-sender`. Solicitar que Identidad corrija el rol; no reintentar automáticamente. |
| `405` | `HTTP_ERROR` | Método no soportado. El endpoint requiere `POST`; `OPTIONS` devuelve `405`. |
| `422` | `VALIDATION_ERROR` | JSON o campos inválidos. El cuerpo incluye `errors` con detalles de validación. Corregir la petición antes de volver a enviarla. |
| `502` | `HTTP_ERROR` | El relay SMTP no aceptó el mensaje o falló la conexión/protocolo. El resultado puede ser ambiguo si el relay aceptó el correo pero se perdió la respuesta; no reintentar automáticamente porque puede duplicarlo. |
| `503` | `HTTP_ERROR` | Configuración SMTP incompleta o no segura. Requiere intervención operativa; no reintentar hasta resolverla. |
| `500` | `INTERNAL_ERROR` | Error inesperado del servicio. El resultado de envío puede ser ambiguo; no reintentar automáticamente sin conciliación. |

Los errores HTTP usan `title: "HTTP error"`, `code: "HTTP_ERROR"` y `detail` específico. Los errores de validación usan `title: "Request validation failed"`, `code: "VALIDATION_ERROR"`, `detail: "One or more request fields are invalid."` y la propiedad `errors`. Los errores inesperados usan `title: "Internal server error"`, `code: "INTERNAL_ERROR"` y un mensaje genérico. Todos incluyen `instance`, `status`, `type` y `correlationId`.

**Nota de seguridad pendiente:** el manejador actual construye `errors` a partir de los errores originales de validación; Pydantic puede incluir el valor de entrada en esos detalles. Eviten enviar contenido sensible y no interpreten `errors` como garantía de que los valores inválidos quedan redactados. Debe corregirse antes de considerar cerrado el diseño de errores para producción.

## Política de destinatarios y contenido

Controles aplicados por el endpoint:

- Una dirección destinataria por solicitud; formato de correo validado.
- Remitente fijo en la configuración del servicio; el consumidor no puede elegirlo.
- Sin `cc`, `bcc`, archivos adjuntos ni plantillas.
- Asunto y cuerpos limitados según la tabla anterior.
- No se escriben destinatario, asunto ni cuerpos en los logs de acceso del servicio. Se registra método, ruta, estado, duración e identificador de correlación. El error SMTP se registra por tipo, sin texto del mensaje.
- El relay SMTP institucional aplica sus propias políticas, que pueden rechazar direcciones o contenido.

Limitación: **el servicio no aplica una lista permitida/bloqueada de dominios ni una política de destinatarios externos**. La implementación acepta cualquier dirección sintácticamente válida y delega la aceptación al relay. Hasta que el responsable funcional/seguridad defina y aplique la política institucional correspondiente, los clientes solo deben usar destinatarios autorizados para notificaciones institucionales y no incluir datos sensibles innecesarios. No se ha definido retención de mensajes por parte del servicio; este no persiste una cola ni un historial de entregas.

## Reintentos, límites e idempotencia

- El envío es síncrono mediante SMTP, con timeout configurado de 10 segundos.
- No existe cola durable ni reintento automático del servicio.
- No se aplica limitación de frecuencia o concurrencia en el endpoint; tampoco se devuelve `429` ni `Retry-After` desde esta operación.
- No se soporta `Idempotency-Key` ni mecanismo de deduplicación. Repetir un `POST` puede enviar otro correo.
- No hay endpoint de consulta de estado.
- Ante timeout, `502` o `500`, el resultado puede ser ambiguo. No reintentar automáticamente. Verificar con el responsable del sistema y el relay antes de repetir.
- `401`, `403`, `422` y `503` requieren corregir la causa antes de una nueva solicitud. La API no prescribe reintentos automáticos.

## Ejemplo de error de validación

```json
{
  "type": "about:blank",
  "title": "Request validation failed",
  "status": 422,
  "detail": "One or more request fields are invalid.",
  "instance": "/api/v1/notifications/email",
  "code": "VALIDATION_ERROR",
  "correlationId": "2c385f21-8f2a-4f7c-94b6-a9652242616f",
  "errors": [
    {
      "type": "string_too_short",
      "loc": ["body", "subject"],
      "msg": "String should have at least 1 character",
      "input": ""
    }
  ]
}
```

La forma concreta de cada elemento en `errors` depende del tipo de validación Pydantic; los consumidores deben apoyarse en `status` y `code`, no en el texto interno de cada elemento.

## Estado de habilitación

El endpoint está publicado detrás de HAProxy y protegido con OAuth2; el relay SMTP recibió una prueba de autenticación, pero no se ha enviado un correo real de extremo a extremo. La aplicación debe hacer primero una prueba controlada con destinatario autorizado.

La publicación del endpoint **no significa que estén implementados** límites por cliente, deduplicación, reintentos seguros, consulta de entrega ni restricción de dominios. Si esos controles son requisitos para habilitar el envío general, deben implementarse antes de ampliar el uso.

## Referencias internas

- Implementación: `services/notification-service/src/mes_notification_service/main.py`
- Transporte SMTP: `shared/python/mes_common/mail.py`
- Formato de errores: `shared/python/mes_common/problem.py`
- Registro de solicitudes: `shared/python/mes_common/middleware.py`


