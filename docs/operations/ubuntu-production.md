# Ubuntu production deployment

Esta guía es una base, no un procedimiento productivo aprobado.

1. Homologar Ubuntu Server LTS y matriz de versiones.
2. Crear usuarios no privilegiados y directorios bajo `/opt/mes` y `/etc/mes`.
3. Instalar Python desde repositorios aprobados y crear un entorno virtual por servicio.
4. Instalar artefactos desde un repositorio institucional con hashes verificados.
5. Guardar configuración no secreta en EnvironmentFile con permisos restringidos.
6. Instalar unidades systemd, ejecutar `daemon-reload` y validar hardening.
7. Publicar servicios solo en la red interna; HAProxy/APISIX son la entrada.
8. Configurar firewall, TLS, DNS, NTP, backups, métricas y logs.
9. Probar health, readiness, rollback y restauración antes de habilitar tráfico.

No se ejecutarán instalaciones automáticas sin revisión humana.

