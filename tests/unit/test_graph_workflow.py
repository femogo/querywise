import asyncio
from typing import Any

from querywise.graph.state import FinalAnswerResponse, SQLGenerationResponse
from querywise.graph.workflow import build_text_to_sql_graph, should_retry


class FakeStructuredRunnable:
    """Deterministic async runnable returning queued Pydantic responses."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[Any] = []

    async def ainvoke(self, messages: Any) -> Any:
        self.calls.append(messages)
        if not self._responses:
            raise AssertionError("No more queued fake LLM responses.")
        return self._responses.pop(0)


class FakeChatModel:
    """Minimal chat model stub implementing with_structured_output."""

    def __init__(
        self,
        sql_responses: list[SQLGenerationResponse],
        answer_responses: list[FinalAnswerResponse],
    ) -> None:
        self.sql_runnable = FakeStructuredRunnable(sql_responses)
        self.answer_runnable = FakeStructuredRunnable(answer_responses)

    def with_structured_output(self, schema: Any) -> FakeStructuredRunnable:
        if schema is SQLGenerationResponse:
            return self.sql_runnable
        if schema is FinalAnswerResponse:
            return self.answer_runnable
        raise ValueError(f"Unexpected schema: {schema}")


class FakeMCPClient:
    """Deterministic MCP client stub simulating schema discovery and query execution."""

    def __init__(self, query_results: list[dict[str, Any]]) -> None:
        self._results = list(query_results)
        self.executed_sqls: list[str] = []

    async def get_full_schema(self) -> str:
        return "Table `products`:\n  - product_id (integer, NOT NULL)\n  - name (varchar, NOT NULL)"

    async def run_query(self, sql: str) -> dict[str, Any]:
        self.executed_sqls.append(sql)
        if not self._results:
            raise AssertionError("No more queued fake MCP query results.")
        return self._results.pop(0)


def test_should_retry_logic() -> None:
    assert should_retry(None, 0, 2) is False
    assert should_retry("column foo does not exist", 1, 2) is True
    assert should_retry("column foo does not exist", 2, 2) is False
    assert should_retry("Access to PII column tax_id is blocked", 1, 2) is False
    assert should_retry("System catalog pg_catalog is forbidden", 1, 2) is False


def test_graph_happy_path() -> None:
    llm = FakeChatModel(
        sql_responses=[
            SQLGenerationResponse(
                reasoning="Select product names from products table.",
                sql="SELECT name FROM products LIMIT 2;",
            )
        ],
        answer_responses=[
            FinalAnswerResponse(
                answer="Los productos son ProBook Ultra 14 y DevStation Pro 16.",
                assumptions=["Se consultaron productos activos."],
            )
        ],
    )
    mcp = FakeMCPClient(
        query_results=[
            {
                "columns": ["name"],
                "rows": [{"name": "ProBook Ultra 14"}, {"name": "DevStation Pro 16"}],
                "row_count": 2,
                "truncated": False,
            }
        ]
    )

    graph = build_text_to_sql_graph(llm=llm, mcp_client=mcp)
    state = asyncio.run(graph.ainvoke({"question": "Lista 2 productos"}))

    assert state["status"] == "success"
    assert state["retry_count"] == 0
    assert state["generated_sql"] == "SELECT name FROM products LIMIT 2"
    assert "ProBook Ultra 14" in state["final_answer"]


def test_graph_self_correction_after_sql_error() -> None:
    llm = FakeChatModel(
        sql_responses=[
            SQLGenerationResponse(
                reasoning="First attempt with wrong column.",
                sql="SELECT bad_col FROM products",
            ),
            SQLGenerationResponse(
                reasoning="Fixed column name using error feedback.",
                sql="SELECT name FROM products",
            ),
        ],
        answer_responses=[
            FinalAnswerResponse(
                answer="Consulta corregida con éxito.",
                assumptions=[],
            )
        ],
    )
    mcp = FakeMCPClient(
        query_results=[
            {"ok": False, "error": 'column "bad_col" does not exist'},
            {
                "columns": ["name"],
                "rows": [{"name": "ProBook Ultra 14"}],
                "row_count": 1,
                "truncated": False,
            },
        ]
    )

    graph = build_text_to_sql_graph(llm=llm, mcp_client=mcp)
    state = asyncio.run(graph.ainvoke({"question": "Dame los productos", "max_retries": 2}))

    assert state["status"] == "success"
    assert state["retry_count"] == 1
    assert len(state["sql_history"]) == 2
    assert "bad_col" in str(llm.sql_runnable.calls[1])


def test_graph_stops_immediately_on_pii_violation() -> None:
    llm = FakeChatModel(
        sql_responses=[
            SQLGenerationResponse(
                reasoning="Attempt to select tax_id.",
                sql="SELECT tax_id FROM customers",
            ),
        ],
        answer_responses=[],
    )
    mcp = FakeMCPClient(
        query_results=[
            {"ok": False, "error": "Blocked PII column: tax_id"},
        ]
    )

    graph = build_text_to_sql_graph(llm=llm, mcp_client=mcp)
    state = asyncio.run(graph.ainvoke({"question": "Dame los NIF de clientes", "max_retries": 2}))

    assert state["status"] == "failed"
    assert state["retry_count"] == 1
    assert len(llm.sql_runnable.calls) == 1