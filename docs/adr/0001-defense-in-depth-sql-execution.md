# ADR 0001: Defensa en profundidad para la ejecución de SQL generado por LLM

## Estado
Aceptado

## Contexto
`querywise` traduce preguntas de negocio en lenguaje natural a consultas PostgreSQL utilizando un LLM local. Dado que los LLMs son probabilísticos y vulnerables a inyección de prompts (incluida la inyección indirecta escondida dentro de columnas de texto de la propia base de datos), nunca se debe confiar ciegamente en el SQL generado.

## Decisión
Aplicamos una tubería de defensa en profundidad de cuatro capas antes y durante la ejecución de cada consulta:
1. **Aislamiento mediante MCP (`stdio`):** El agente LangGraph no tiene drivers ni credenciales directas de base de datos. Se comunica exclusivamente con un servidor Model Context Protocol (MCP) dedicado y de solo lectura.
2. **Validación sintáctica AST (`sqlglot`):** Cada consulta generada se analiza como un Árbol de Sintaxis Abstracta (AST) en dialecto PostgreSQL. Solo se permiten consultas `SELECT` de una única sentencia; se rechazan DDL/DML, catálogos del sistema (`pg_catalog`, `information_schema`) y columnas sensibles (PII), y se inyecta un `LIMIT` obligatorio si no existe.
3. **Mínimo privilegio en base de datos:** El servidor MCP se conecta a PostgreSQL usando un rol dedicado (`querywise_ro`) que únicamente tiene permiso `SELECT` sobre las tablas de negocio autorizadas.
4. **Límites de recursos:** Las consultas se evalúan previamente con estimación de coste mediante `EXPLAIN` y están acotadas por `statement_timeout` a nivel de sesión en PostgreSQL.

## Consecuencias
- **Positivas:** Incluso si un atacante o una alucinación del modelo logra eludir el prompt o un caso límite del analizador sintáctico, los permisos de la base de datos y los timeouts impiden modificar datos, exfiltrar información o saturar el servidor.
- **Negativas:** Ligero aumento de latencia por consulta debido al análisis AST y a la comprobación previa con `EXPLAIN`, además de exigir mayor rigor sintáctico al modelo local.