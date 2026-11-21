# Physical architecture

Topología inicial recomendada:

- VM de entrada: HAProxy y Apache APISIX/etcd.
- VM de identidad: Keycloak.
- VM de mensajería: RabbitMQ.
- VM de datos: PostgreSQL.
- VM de aplicaciones: servicios y conectores.
- VM de observabilidad: OpenTelemetry Collector, Prometheus, Loki y Grafana OSS.

La consolidación es posible en desarrollo, sin eliminar la separación de usuarios, puertos, credenciales y directorios. Alta disponibilidad, capacidad y número final de máquinas dependen de SLO, RPO y RTO aún no acordados.

