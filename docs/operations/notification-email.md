# Servicio de notificaciones por correo

El primer canal de notificaciones es el correo institucional del MES. El servicio
separado `notification-service` ofrece:

```http
POST /api/v1/notifications/email
Authorization: Bearer <token>
Content-Type: application/json
```

Ejemplo:

```json
{
  "recipient": "persona@institucion.edu.cu",
  "subject": "Aviso del sistema",
  "text_body": "El trámite fue actualizado.",
  "html_body": "<p>El trámite fue actualizado.</p>"
}
```

El cliente debe tener el rol de Keycloak `notification-sender`. El endpoint acepta un
destinatario por solicitud y limita asunto y cuerpos. No se registran el destinatario,
el asunto ni el contenido en los logs. `202 accepted_by_relay` significa que el relay
SMTP aceptó el mensaje; no confirma entrega final en el buzón.

El envío es síncrono durante esta primera etapa, con un timeout acotado. Si el volumen
crece o se requieren reintentos durables y consulta de estados, se incorporará una cola
de mensajes y persistencia de entregas.

## Relay SMTP

- Destino de red: `[IP_INTERNA]:25`.
- STARTTLS obligatorio; no se usa TLS implícito/puerto 465.
- Identidad TLS: `correo.mes.gob.cu`, validada contra el certificado del relay.
- La cuenta y la contraseña se cargan desde `/etc/mes/notification-service.env`, con
  permisos `0640`, propiedad `root:mes-notifications`; no se guardan en Git.
- Las credenciales SMTP nunca se envían a los sistemas consumidores.

Variables requeridas: `SMTP_HOST`, `SMTP_PORT`, `SMTP_TLS_SERVER_NAME`, `SMTP_USER`,
`SMTP_PASSWORD` y `EMAIL_FROM`. `SMTP_STARTTLS` y
`SMTP_TLS_REJECT_UNAUTHORIZED` deben permanecer en `true`.
