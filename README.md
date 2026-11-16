# querywise

Agente Text-to-SQL construido con **LangGraph**, **Model Context Protocol (MCP)** y **PostgreSQL**, diseñado con arquitectura **local-first** (Ollama) y **defensa en profundidad**.

## Arquitectura de seguridad (4 capas)
1. **Aislamiento mediante MCP (stdio):** El agente no posee drivers ni credenciales directas de base de datos; invoca herramientas expuestas por un servidor MCP aislado de solo lectura.
2. **Validacion sintactica AST (sqlglot):** Analisis estatico del arbol sintactico para permitir unicamente consultas SELECT de una sola sentencia, bloquear catalogos del sistema y columnas sensibles (PII), e inyectar LIMIT obligatorio.
3. **Minimo privilegio en PostgreSQL:** Conexion mediante un rol dedicado (querywise_ro) con permisos exclusivos de lectura sobre tablas de negocio autorizadas.
4. **Limites de recursos:** Validacion previa de coste con EXPLAIN y control de tiempo mediante statement_timeout.

## Ejecucion rapida
- Instalar dependencias: uv sync
- Ejecutar tests: uv run pytest -v
- Ejecutar linter: uv run ruff check .