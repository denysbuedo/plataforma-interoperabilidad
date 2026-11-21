# Logical architecture

Cada servicio se divide conceptualmente en dominio, aplicación, puertos e infraestructura. El dominio no importa FastAPI, SQLAlchemy, RabbitMQ ni implementaciones de conectores. FastAPI pertenece a la capa de entrada; PostgreSQL y conectores pertenecen a infraestructura.

La biblioteca `mes_common` contiene únicamente capacidades técnicas. Los servicios no pueden importar otros servicios. La regla se verifica en `tests/architecture`.

