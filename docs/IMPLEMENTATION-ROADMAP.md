# Implementation roadmap

| Milestone | Estado | Resultado verificable |
|---|---|---|
| 0. Architecture baseline | Completado | Arquitectura, ADR, seguridad, gobierno y decisiones pendientes documentadas |
| 1. Repository bootstrap | Completado | Tres procesos FastAPI con endpoints técnicos y pruebas |
| 2. Systems inventory | Siguiente | Fuentes, capacidades y primer piloto acordados |
| 3. Registry API | Pendiente | Catálogo funcional de sistemas, APIs y consumidores |
| 4. Institutions vertical | Pendiente | Primer flujo real fuente-plataforma-consumidor |
| 5. Persons | MVP externo integrado para desarrollo local; publicación bloqueada | `registro-personas` independiente, contrato coordinado y arranque local; autenticación institucional/eventos pendientes |
| 6. Additional connectors | Pendiente | Patrones HTTP, agente, BD y archivos probados |
| 7. Production hardening | Pendiente | Instalación, seguridad, continuidad y SLO verificados |
| 8. Progressive adoption | Pendiente | Incorporación gobernada de sistemas y consumidores |

Nuevos flujos requieren propietario, fuente autorizada, atributos, frescura y consumidor
acordados. El MVP Personas cuenta con encargo PER-001 y stack aprobados; su integración
local no ratifica ownership definitivo ni habilita publicación o provisión LDAP.

El correo institucional ya está operativo y es consumido por varias aplicaciones,
según confirmación del responsable. Su código/contrato/despliegue no se cambian en esta
integración. La coexistencia propuesta se registra en ADR-012 (PROPUESTO).

