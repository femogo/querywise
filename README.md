# querywise

Agente Text-to-SQL construido con **LangGraph**, **Model Context Protocol (MCP)**, **FastAPI** y **PostgreSQL**, diseñado con arquitectura **local-first** (Ollama `gemma4:e2b`) y **defensa en profundidad**.

## Arquitectura de seguridad (4 capas)
1. **Aislamiento mediante MCP (stdio):** El agente no posee drivers ni credenciales directas de base de datos; invoca herramientas expuestas por un servidor MCP aislado de solo lectura.
2. **Validación sintáctica AST (sqlglot):** Análisis estático para permitir únicamente consultas `SELECT` de una sola sentencia, bloquear catálogos del sistema y columnas PII (`tax_id`, `password_hash`, `secret_token_ref`), e inyectar `LIMIT` obligatorio.
3. **Mínimo privilegio en PostgreSQL:** Rol dedicado `querywise_ro` con acceso exclusivo a las 6 tablas de negocio autorizadas.
4. **Límites de recursos:** Validación previa con `EXPLAIN (FORMAT JSON)` y `statement_timeout`.

## Ejecución rápida
- Instalar dependencias: `uv sync`
- Ejecutar tests (42/42): `uv run pytest -v`
- Ejecutar linter: `uv run ruff check .`
- Consulta CLI: `uv run python -m querywise.api --question "¿Cuáles son los 3 productos más vendidos por ingresos netos?"`
- Servidor FastAPI: `uv run python -m querywise.api --serve --host 127.0.0.1 --port 8000`
- Benchmark automático: `uv run python -m querywise.eval.runner --suite all`
