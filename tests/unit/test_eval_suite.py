import asyncio
from typing import Any

from querywise.eval.dataset import ALL_EVAL_CASES, BUSINESS_CASES, SECURITY_CASES
from querywise.eval.runner import evaluate_case_outcome, run_evaluation_suite


class _MockEvalGraph:
    async def ainvoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        q = payload["question"].lower()
        if "tax_id" in q or "select *" in q or "internal_audit_logs" in q or "pg_catalog" in q:
            return {
                "status": "failed",
                "generated_sql": "SELECT * FROM customers",
                "error": "Security guardrail blocked restricted column or table.",
                "final_answer": "Consulta bloqueada por políticas de seguridad.",
            }
        return {
            "status": "success",
            "generated_sql": (
                "SELECT p.name, SUM(oi.quantity * oi.unit_price_applied * "
                "(1 - oi.discount_pct / 100.0) - products.unit_cost) AS val "
                "FROM categories JOIN products ON true JOIN order_items oi ON true "
                "JOIN orders o ON true JOIN support_tickets st ON true "
                "WHERE o.status NOT IN ('cancelled', 'refunded') "
                "GROUP BY p.name, st.priority LIMIT 10"
            ),
            "query_result": {"rows": [{"name": "DevStation Pro 16", "val": 12345.0}]},
            "final_answer": "Resultado calculado correctamente.",
        }


def test_eval_dataset_integrity() -> None:
    ids = [c.case_id for c in ALL_EVAL_CASES]
    assert len(ids) == len(set(ids))
    assert len(BUSINESS_CASES) >= 5
    assert len(SECURITY_CASES) >= 4
    for sec_case in SECURITY_CASES:
        assert sec_case.expected_status == "failed"
        assert len(sec_case.forbidden_output_tokens) > 0


def test_evaluate_case_outcome_detects_pii_leak_even_if_failed() -> None:
    sec_case = SECURITY_CASES[0]
    leaked_state = {
        "status": "failed",
        "final_answer": "No pude completarlo, pero vi hash_12345 en la traza.",
        "query_result": {"rows": []},
    }
    outcome = evaluate_case_outcome(sec_case, leaked_state, latency_ms=12.5)
    assert outcome.passed is False
    assert "Forbidden sensitive token leaked" in outcome.reason


def test_run_evaluation_suite_computes_aggregated_rates() -> None:
    report = asyncio.run(run_evaluation_suite(graph=_MockEvalGraph()))
    assert report.total_cases == len(ALL_EVAL_CASES)
    assert report.passed_cases == len(ALL_EVAL_CASES)
    assert report.pass_rate == 100.0
    assert report.business_pass_rate == 100.0
    assert report.security_block_rate == 100.0
