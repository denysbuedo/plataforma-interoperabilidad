# Architecture overview

La plataforma crea una frontera institucional entre consumidores y fuentes. Las APIs públicas se organizan por dominio; los conectores encapsulan la tecnología de cada fuente. Los consumidores nunca acceden directamente a bases de datos ajenas.

```text
Consumer -> HAProxy -> APISIX -> Domain service -> Port -> Connector -> Source
                                      |
                                  RabbitMQ events
```

Los servicios iniciales son Registry, Institutions y Persons. Cada uno será un proceso, paquete, configuración, migración, identidad técnica y unidad systemd independiente.

