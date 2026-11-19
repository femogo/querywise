import pytest

from querywise.security.sql_guardrail import SQLGuardrailError, validate_and_rewrite_sql


def test_valid_select_injects_default_limit() -> None:
    rewritten = validate_and_rewrite_sql("SELECT order_id, status FROM orders", max_rows=25)
    assert "LIMIT 25" in rewritten


def test_valid_select_clamps_excessive_limit() -> None:
    rewritten = validate_and_rewrite_sql("SELECT order_id FROM orders LIMIT 5000", max_rows=100)
    assert "LIMIT 100" in rewritten
    assert "5000" not in rewritten


def test_valid_select_preserves_smaller_limit() -> None:
    rewritten = validate_and_rewrite_sql("SELECT order_id FROM orders LIMIT 10", max_rows=100)
    assert "LIMIT 10" in rewritten


def test_valid_cte_query_is_allowed() -> None:
    sql = """
    WITH completed_orders AS (
        SELECT order_id, total_amount FROM orders WHERE status = 'delivered'
    )
    SELECT * FROM completed_orders
    """
    rewritten = validate_and_rewrite_sql(sql, max_rows=50)
    assert "LIMIT 50" in rewritten


@pytest.mark.parametrize(
    "malicious_sql",
    [
        "DELETE FROM orders",
        "DROP TABLE orders",
        "UPDATE orders SET status = 'cancelled'",
        "INSERT INTO categories (name) VALUES ('hack')",
        "SELECT * INTO evil_copy FROM orders",
        "SELECT 1; DROP TABLE orders;",
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM information_schema.columns",
        "SELECT * FROM pg_user",
        "SELECT * FROM internal_audit_logs",
        "SELECT * FROM unknown_table",
        "SELECT * FROM customers",
        "SELECT c.* FROM customers c",
        "SELECT customer_id, password_hash FROM customers",
        "SELECT customer_id FROM customers WHERE tax_id = 'B12345678'",
    ],
)
def test_blocks_unsafe_or_pii_queries(malicious_sql: str) -> None:
    with pytest.raises(SQLGuardrailError):
        validate_and_rewrite_sql(malicious_sql, max_rows=100)
