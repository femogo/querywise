# Progreso del proyecto `querywise`

## Hito 0 - Cimientos, arquitectura y configuracion (Completado - `7593d02`)
- Estructura `src` layout, gestion con `uv`, Pydantic `Settings` y ADRs `0001`/`0002`.
- 3 tests unitarios en verde y `ruff` limpio.

## Hito 1 - Base de datos PostgreSQL y servidor MCP de solo lectura (Completado - `de99d7d`)
- PostgreSQL 16 en Docker (`docker-compose.yml`) y esquema con minimo privilegio (`scripts/init_db.sql`, rol `querywise_ro`).
- Carga determinista con semilla 42 (`scripts/seed_db.py`): 5 categorias, 10 productos, 30 clientes, 120 pedidos, 231 lineas y 4 tickets.
- Servidor MCP por `stdio` con 4 herramientas de solo lectura (`src/querywise/mcp_server/server.py`).
- 8 tests en verde (3 unitarios + 5 de integracion) y `ruff check` limpio.

## Hito 2 - Guardrail SQL basado en AST con `sqlglot` (Completado - `10aeb00`)
- Validador sintactico AST (`src/querywise/security/sql_guardrail.py`): solo `SELECT` de 1 sentencia, allowlist de tablas, bloqueo de PII, inyeccion de `LIMIT` y limite de coste con `EXPLAIN`.
- 27 tests en verde y `ruff check` limpio.

## Hito 3 - Grafo Text-to-SQL en LangGraph con autocorreccion (Completado - `0f3adc8`)
- Glosario de negocio inicial y frontera anti-inyeccion (`src/querywise/semantic/business_glossary.py`).
- Cliente MCP asincrono por `stdio` (`src/querywise/graph/mcp_client.py`).
- Estado tipado y esquemas Pydantic (`src/querywise/graph/state.py`).
- Grafo LangGraph (`src/querywise/graph/workflow.py`) conectado a Ollama local (`gemma4:e2b`) con bucle de autocorreccion acotado y corte inmediato ante errores de seguridad (`should_retry`).
- 31 tests en verde (27 anteriores + 4 del grafo) y `ruff check` limpio.

## Proximo paso: Hito 4 - Capa semantica (catalogo de metricas y ejemplos verificados)
- Expandir `src/querywise/semantic/` con un catalogo estructurado de metricas de negocio y recuperacion por similitud de ejemplos SQL verificados (few-shot) para consultas ambiguas o con multiples joins.