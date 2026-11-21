# ADR-007: Despliegue sin contenedores

## Context

La infraestructura objetivo utiliza máquinas virtuales Ubuntu y software libre directo.

## Decision

No usar Docker, Podman, Kubernetes ni Helm. Usar Ansible, entornos virtuales y systemd.

## Consequences

El proyecto debe gestionar paquetes, usuarios, aislamiento, puertos, hardening y rollback explícitamente.

## Alternatives

Contenedores y orquestadores quedan fuera por decisión institucional.

