# Progreso del proyecto `querywise`

## Hito 0 — Cimientos, arquitectura y configuración (Completado)
- **Estructura `src` layout:** Paquete `src/querywise` dividido en módulos (`api`, `graph`, `mcp_server`, `security`, `semantic`) y suite de pruebas (`tests/unit`, `tests/integration`).
- **Gestión de entorno y dependencias:** Configurado con `uv`, Python 3.12+, `pydantic-settings`, `pytest` y `ruff`.
- **Seguridad inicial:** `.gitignore` blindado contra `.env` y bases de datos locales; credenciales separadas en `readonly_dsn` y `admin_dsn` dentro de `src/querywise/config.py`.
- **ADRs en español:** Documentadas las decisiones de defensa en profundidad (`0001`) y stack local-first de coste cero (`0002`) en `docs/adr/`.
- **Verificación:** 3 tests unitarios en verde (`pytest`) y linter limpio (`ruff`).

## Próximo paso: Hito 1 — Base de datos PostgreSQL y servidor MCP de solo lectura