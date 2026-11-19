# QueryWise — Project Progress

## Completed Milestones
- **Hito 0 (7593d02):** Project skeleton with uv, Pydantic Settings, Ruff/Pytest, and ADRs.
- **Hito 1 (de99d7d):** PostgreSQL 16 Docker service, deterministic seed dataset, least-privilege querywise_ro role, and read-only MCP stdio server.
- **Hito 2 (10aeb00):** AST SQL guardrail with sqlglot, table allowlist, PII column blocking, forced LIMIT, EXPLAIN cost cap, and statement_timeout.
- **Hito 3:** LangGraph Text-to-SQL orchestration connected to local Ollama (gemma4:e2b) via Pydantic structured outputs and isolated QueryWiseMCPClient (stdio).
- **Hito 4 (e1d8ce0):** Semantic layer (business glossary, metrics catalog, verified SQL retriever) with accent-insensitive similarity matching.
- **Hito 5 (completed):** FastAPI REST service (GET /health, POST /query), CLI entrypoint, automated evaluation suite (business + security/prompt-injection), 42 passing tests, and final documentation.
