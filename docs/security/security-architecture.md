# Security architecture

Keycloak proporciona OAuth 2.0/OIDC. APISIX aplica controles de entrada y cada servicio vuelve a validar claims críticos. Se usa Authorization Code con PKCE para usuarios y Client Credentials para servicios.

Controles mínimos: denegación por defecto, scopes, TLS, mínimo privilegio, cuentas separadas, límites de petición, rate limiting, CORS restrictivo, secretos fuera de Git, interfaces administrativas aisladas, auditoría y datos minimizados.

Antes del primer dominio se elaborará un modelo de amenazas y clasificación de datos. Los entornos no productivos no recibirán copias de datos personales sin enmascaramiento aprobado.

