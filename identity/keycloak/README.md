# Keycloak

La plataforma usa un realm dedicado `interoperabilidad`; nunca utiliza `master` para
aplicaciones. El recurso protegido tiene audiencia `mes-api`. Los roles son
`api-reader`, `api-writer`, `api-admin` y `notification-sender`; este último habilita el
envío de correo por el servicio de notificaciones.

Clientes:

- `api-swagger`: cliente público, Authorization Code, PKCE S256 y redirect URI
  `https://api.reduniv.edu.cu/docs/oauth2-redirect`.
- clientes de sistemas: confidenciales, Service Accounts y Client Credentials. Cada
  sistema recibe un cliente y un secreto independientes.

La API de registro expone `GET /api/v1/me` para comprobar la identidad del token. Las
métricas requieren `api-admin`; el endpoint de correo requiere `notification-sender`.
`/health` y `/ready` no requieren autenticación.

Al crear cada cliente de integración:

1. Deshabilitar Standard Flow y Direct Access Grants; habilitar Service Accounts y
   autenticación `client-secret`.
2. Añadir un mapper de audiencia OIDC con `included.client.audience=mes-api` y
   `access.token.claim=true`.
3. Asignar únicamente los roles necesarios al usuario de servicio del cliente.
4. Entregar el secreto al sistema consumidor por un canal seguro y no guardarlo en Git.

La clave pública activa del realm se obtiene con `kcadm.sh get keys -r
interoperabilidad` y se instala como `/etc/mes/oidc-rs256-public.pem` en cada VM API.
El endpoint de la API valida tokens con `RS256`, `iss` y `aud=mes-api`. No configurar
el URI JWKS interno HTTP como sustituto de la clave fijada.

Los secretos y exports que los contengan no se guardan en Git.

La verificación usa una copia local de la clave pública RS256 del realm, instalada en
`/etc/mes/oidc-rs256-public.pem` con acceso de solo lectura. Así no depende de bajar
claves por HTTP desde la red interna. `OIDC_ISSUER_URL` conserva el URL público y se
valida estrictamente contra el claim `iss`. Al rotar la clave activa RS256, hay que
instalar la nueva clave en las VMs API y reiniciar los servicios antes de emitir tokens
firmados con ella.
