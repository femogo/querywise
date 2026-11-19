# Progreso del proyecto `querywise`

## Hito 0 — Cimientos, arquitectura y configuración (Completado)
- **Estructura `src` layout:** Paquete `src/querywise` dividido en módulos (`api`, `graph`, `mcp_server`, `security`, `semantic`) y suite de pruebas (`tests/unit`, `tests/integration`).
- **Gestión de entorno y dependencias:** Configurado con `uv`, Python 3.12+, `pydantic-settings`, `pytest` y `ruff`.
- **Seguridad inicial:** `.gitignore` blindado contra `.env` y bases de datos locales; credenciales separadas en `readonly_dsn` y `admin_dsn` dentro de `src/querywise/config.py`.
- **ADRs en español:** Documentadas las decisiones de defensa en profundidad (`0001`) y stack local-first de coste cero (`0002`) en `docs/adr/`.
- **Verificación:** 3 tests unitarios en verde (`pytest`) y linter limpio (`ruff`).

## Hito 1 — Base de datos PostgreSQL y servidor MCP de solo lectura (Completado)
- **PostgreSQL 16 en Docker (`docker-compose.yml`):** Contenedor reproducible `querywise-postgres` con volumen persistente y healthcheck activo.
- **Esquema y mínimo privilegio (`scripts/init_db.sql`):** 7 tablas del dominio de comercio electrónico con trampas realistas (estados `cancelled`/`refunded`, importes con/sin IVA, columnas PII como `password_hash` y `tax_id`, y tabla privada `internal_audit_logs`), más el rol `querywise_ro` con permiso exclusivo `SELECT` sobre 6 tablas autorizadas.
- **Poblado determinista (`scripts/seed_db.py`):** Carga reproducible con semilla `42` (5 categorías, 10 productos, 30 clientes, 120 pedidos, 231 líneas de pedido y 4 tickets de soporte, incluyendo un caso de *prompt injection* indirecto).
- **Servidor MCP (`src/querywise/mcp_server/server.py`):** Implementado con `MCPServer` (`mcp 2.x`) sobre transporte `stdio`, exponiendo 4 herramientas (`list_tables`, `describe_table`, `sample_rows`, `run_query`) usando `readonly_dsn`, validación estricta de identificadores, `statement_timeout` y `default_transaction_read_only=on`.
- **Verificación:** 8 tests en verde (3 unitarios + 5 de integración contra PostgreSQL real) y `ruff check .` limpio.

## Hito 2 — Guardrail SQL basado en AST (`sqlglot`) y estimación de coste `EXPLAIN` (Completado)
- **Validador sintáctico AST (`src/querywise/security/sql_guardrail.py`):** Inspección en dialecto `postgres` con `sqlglot` para permitir únicamente una sentencia `SELECT`, bloquear DDL/DML (`DELETE`, `DROP`, `UPDATE`, `INSERT`, `SELECT INTO`) y múltiples sentencias `;`, restringir acceso a tablas de negocio permitidas (`ALLOWED_TABLES`) y bloquear catálogos del sistema (`pg_catalog`, `information_schema`, `pg_*`).
- **Protección de datos sensibles (PII):** Bloqueo de `password_hash`, `tax_id` y `secret_token_ref` en cualquier nodo del AST, rechazo de comodines `*` sobre tablas con PII (`customers`) y filtrado automático de columnas PII en `sample_rows`.
- **Control de recursos (`EXPLAIN` + `LIMIT`):** Inyección o recorte automático de `LIMIT <= sql_max_rows` y validación previa del plan con `EXPLAIN (FORMAT JSON)` contra `sql_max_explain_cost` en `run_query` (`src/querywise/mcp_server/server.py`).
- **Verificación:** 27 tests en verde (22 unitarios + 5 de integración contra PostgreSQL real) y `ruff check .` limpio.

## Próximo paso: Hito 3 — Orquestación agéntica con LangGraph y Ollama
