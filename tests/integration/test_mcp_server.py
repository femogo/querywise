import json

import pytest

from querywise.config import get_settings
from querywise.mcp_server.server import describe_table, list_tables, run_query, sample_rows
from querywise.security.sql_guardrail import SQLGuardrailError


def test_list_tables_returns_only_allowed_business_tables() -> None:
    payload = json.loads(list_tables())
    tables = payload["tables"]
    assert "orders" in tables
    assert "customers" in tables
    assert "internal_audit_logs" not in tables


def test_describe_table_returns_schema_and_blocks_audit_logs() -> None:
    payload = json.loads(describe_table("orders"))
    col_names = {col["column_name"] for col in payload["columns"]}
    assert {"order_id", "customer_id", "status", "total_amount"} <= col_names

    with pytest.raises(ValueError, match="Tabla no permitida"):
        describe_table("internal_audit_logs")


def test_sample_rows_strips_pii_columns_from_customers() -> None:
    payload = json.loads(sample_rows("customers", limit=3))
    assert payload["row_count"] == 3
    for row in payload["rows"]:
        assert "email" in row
        assert "password_hash" not in row
        assert "tax_id" not in row


def test_run_query_executes_valid_select_and_blocks_pii_and_writes() -> None:
    ok_payload = json.loads(
        run_query("SELECT status, COUNT(*) AS total FROM orders GROUP BY status ORDER BY status")
    )
    assert ok_payload["row_count"] >= 1

    with pytest.raises(SQLGuardrailError):
        run_query("SELECT * FROM customers")

    with pytest.raises(SQLGuardrailError):
        run_query("DELETE FROM orders")


def test_run_query_rejects_queries_exceeding_explain_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SQL_MAX_EXPLAIN_COST", "0.01")
    get_settings.cache_clear()
    try:
        with pytest.raises(SQLGuardrailError, match="coste estimado"):
            run_query(
                "SELECT o.order_id, c.full_name "
                "FROM orders o JOIN customers c ON o.customer_id = c.customer_id"
            )
    finally:
        monkeypatch.delenv("SQL_MAX_EXPLAIN_COST", raising=False)
        get_settings.cache_clear()
