# HAProxy

La configuración se añadirá al integrar APISIX. HAProxy terminará TLS y enviará tráfico al gateway; los servicios no se publicarán directamente.

# Ruta del servicio de notificaciones

Cuando IT autorice publicar el endpoint bajo `api.reduniv.edu.cu`, el frontend HTTPS
debe enrutar `/api/v1/notifications/` al backend interno `[IP_INTERNA]:8004`. El servicio
no debe exponerse por HTTP público ni permitir acceso directo desde Internet a 8004.
La API valida tokens y el rol `notification-sender` de Keycloak.

Ejemplo de reglas para integrar en el frontend/backend existentes (ajustar sus nombres
locales):

```haproxy
acl host_api hdr(host),lower -m str api.reduniv.edu.cu
acl path_notifications path_beg /api/v1/notifications/
use_backend mes_notification_service if host_api path_notifications

backend mes_notification_service
    mode http
    option httpchk
    http-check send meth GET uri /ready
    http-check expect status 200
    server notification01 [IP_INTERNA]:8004 check inter 5s fall 3 rise 2
```

