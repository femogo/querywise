import time
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from querywise.config import get_settings
from querywise.graph.workflow import build_text_to_sql_graph


class QueryRequest(BaseModel):
    """Input payload for natural-language analytics queries."""

    question: str = Field(..., min_length=3, description="Business question in natural language.")
    max_retries: int = Field(
        default=2, ge=0, le=5, description="Maximum SQL self-correction retries."
    )


class QueryResponse(BaseModel):
    """Structured execution trace and answer returned by QueryWise."""

    status: Literal["success", "failed"]
    question: str
    final_answer: str
    generated_sql: str | None = None
    sql_reasoning: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    retry_count: int = 0
    sql_history: list[str] = Field(default_factory=list)
    error: str | None = None
    latency_ms: float


def create_app(graph: Any | None = None) -> FastAPI:
    """Create the FastAPI application with an injectable LangGraph workflow."""
    settings = get_settings()
    compiled_graph = graph if graph is not None else build_text_to_sql_graph()

    app = FastAPI(
        title="QueryWise API",
        description=(
            "Local-first Text-to-SQL LangGraph agent with defense-in-depth and read-only MCP."
        ),
        version="0.1.0",
    )
    app.state.graph = compiled_graph

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "querywise",
            "database": settings.postgres_db,
            "sql_max_rows": settings.sql_max_rows,
            "ollama_model": settings.ollama_model,
        }

    @app.post("/query", response_model=QueryResponse)
    async def run_query(payload: QueryRequest) -> QueryResponse:
        start = time.perf_counter()
        final_state = await app.state.graph.ainvoke(
            {
                "question": payload.question,
                "max_retries": payload.max_retries,
            }
        )
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        query_result = final_state.get("query_result") or {}
        rows = query_result.get("rows", []) if isinstance(query_result, dict) else []

        return QueryResponse(
            status=final_state.get("status", "failed"),
            question=payload.question,
            final_answer=final_state.get("final_answer", ""),
            generated_sql=final_state.get("generated_sql"),
            sql_reasoning=final_state.get("sql_reasoning"),
            assumptions=final_state.get("assumptions", []),
            rows=rows,
            row_count=len(rows),
            retry_count=final_state.get("retry_count", 0),
            sql_history=final_state.get("sql_history", []),
            error=final_state.get("error"),
            latency_ms=elapsed_ms,
        )

    return app


app = create_app()
