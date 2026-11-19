import asyncio

from querywise.graph.state import FinalAnswerResponse, SQLGenerationResponse
from querywise.graph.workflow import build_text_to_sql_graph
from querywise.semantic import (
    DEFAULT_VERIFIED_QUERIES,
    build_semantic_context,
    retrieve_relevant_metrics,
    retrieve_verified_queries,
)


def test_retrieve_metrics_accent_insensitive_margin_and_aov() -> None:
    metrics = retrieve_relevant_metrics("Cual es el margen bruto y ticket medio por categoria?")
    metric_ids = [m.metric_id for m in metrics]
    assert "gross_margin" in metric_ids
    assert "average_order_value" in metric_ids


def test_retrieve_metrics_fallback_on_unrelated_question() -> None:
    metrics = retrieve_relevant_metrics("xyz completamente desconocido")
    metric_ids = [m.metric_id for m in metrics]
    assert metric_ids == ["net_revenue", "valid_order_count"]


def test_retrieve_verified_queries_similarity_and_no_pii() -> None:
    queries = retrieve_verified_queries("Mejores clientes VIP por facturacion neta", top_k=2)
    assert len(queries) >= 1
    assert queries[0].query_id == "top_customers_by_spend"

    forbidden_pii = ("email", "tax_id", "password_hash", "secret_token_ref")
    for verified in DEFAULT_VERIFIED_QUERIES:
        lowered_sql = verified.sql.lower()
        assert lowered_sql.startswith("select ")
        for col in forbidden_pii:
            assert col not in lowered_sql


def test_build_semantic_context_combines_all_sections() -> None:
    context = build_semantic_context(
        "Evolucion mensual de ingresos netos", top_k_metrics=2, top_k_examples=1
    )
    assert "### BUSINESS GLOSSARY & DOMAIN RULES (MANDATORY)" in context
    assert "### DATA TRUST BOUNDARY" in context
    assert "### RELEVANT CANONICAL METRICS" in context
    assert "### VERIFIED SQL EXAMPLES (FEW-SHOT REFERENCE)" in context
    assert "DATE_TRUNC('month', o.created_at)" in context


class _FakeStructuredRunnable:
    def __init__(self, schema_cls, captured_prompts: list[str]) -> None:
        self._schema_cls = schema_cls
        self._captured_prompts = captured_prompts

    async def ainvoke(self, messages):
        self._captured_prompts.append(messages[0].content)
        if self._schema_cls is SQLGenerationResponse:
            return SQLGenerationResponse(
                reasoning="Use canonical margin query.",
                sql="SELECT c.name, 100.0 AS gross_profit FROM categories c LIMIT 5",
            )
        return FinalAnswerResponse(
            answer="El margen bruto de prueba es 100.0.",
            assumptions=["Excluye pedidos cancelados y devueltos."],
        )


class _FakeChatModel:
    def __init__(self) -> None:
        self.captured_prompts: list[str] = []

    def with_structured_output(self, schema_cls):
        return _FakeStructuredRunnable(schema_cls, self.captured_prompts)


class _FakeMCPClient:
    async def get_full_schema(self) -> str:
        return "Table categories(category_id, name, department, target_margin_pct)"

    async def run_query(self, sql: str) -> dict:
        return {
            "ok": True,
            "executed_sql": sql,
            "rows": [{"name": "Laptops", "gross_profit": 100.0}],
        }


def test_workflow_injects_dynamic_semantic_context_into_prompt() -> None:
    fake_llm = _FakeChatModel()
    graph = build_text_to_sql_graph(llm=fake_llm, mcp_client=_FakeMCPClient())

    result = asyncio.run(
        graph.ainvoke(
            {"question": "¿Cuál es el margen bruto y margen porcentual real por categoría?"}
        )
    )

    assert result["status"] == "success"
    assert len(fake_llm.captured_prompts) == 2
    sql_system_prompt = fake_llm.captured_prompts[0]
    assert "gross_margin" in sql_system_prompt
    assert "target_margin_pct" in sql_system_prompt
