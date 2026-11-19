from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class SQLGenerationResponse(BaseModel):
    """Structured output returned by the LLM when generating or fixing a SQL query."""

    reasoning: str = Field(
        description=(
            "Brief step-by-step explanation of tables, joins, filters, and business rules used."
        )
    )
    sql: str = Field(
        description="A single valid read-only PostgreSQL SELECT statement without markdown fences."
    )


class FinalAnswerResponse(BaseModel):
    """Structured output returned by the LLM when summarizing SQL results for the user."""

    answer: str = Field(
        description="Clear, concise answer in Spanish grounded strictly in the returned rows."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Business rules or defaults applied (e.g., net revenue, excluded orders).",
    )


class AgentState(TypedDict, total=False):
    """Shared state passed across LangGraph nodes during a Text-to-SQL run."""

    question: str
    schema_context: str
    generated_sql: str
    sql_reasoning: str
    sql_history: list[str]
    retry_count: int
    max_retries: int
    error: str | None
    query_result: dict[str, Any] | None
    final_answer: str
    assumptions: list[str]
    status: Literal["success", "failed"]