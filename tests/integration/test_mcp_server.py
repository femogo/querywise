import json

import psycopg
import pytest

from querywise.mcp_server.server import describe_table, list_tables, run_query, sample_rows


def test_list_tables_hides_internal_audit_logs() -> None:
    """Comprueba que list_tables muestra solo las 6 tablas permitidas a querywise_ro."""
    payload = json.loads(list_tables())
    assert payload["tables"] == [
        "categories",
        "customers",
        "order_items",
        "orders",
        "products",
        "support_tickets",
    ]


def test_describe_and_sample_rows_products() -> None:
    """Comprueba que describe_table y sample_rows devuelven metadatos y filas acotadas."""
    schema_payload = json.loads(describe_table("products"))
    col_names = [col["column_name"] for col in schema_payload["columns"]]
    assert "sku" in col_names
    assert "unit_cost" in col_names

    sample_payload = json.loads(sample_rows("products", limit=3))
    assert sample_payload["table"] == "products"
    assert sample_payload["row_count"] == 3
    assert len(sample_payload["rows"]) == 3


def test_run_query_returns_deterministic_order_count() -> None:
    """Comprueba que run_query ejecuta SELECT y devuelve el total determinista de pedidos."""
    result = json.loads(run_query("SELECT COUNT(*) AS total_orders FROM orders;"))
    assert result["columns"] == ["total_orders"]
    assert result["rows"] == [{"total_orders": 120}]
    assert result["truncated"] is False


def test_readonly_role_blocks_write_and_private_table() -> None:
    """Comprueba que PostgreSQL rechaza fisicamente escrituras y lectura de tablas privadas."""
    with pytest.raises(psycopg.Error):
        run_query("DELETE FROM orders WHERE order_id = 1;")

    with pytest.raises(psycopg.Error):
        run_query("SELECT * FROM internal_audit_logs;")


def test_sample_rows_rejects_invalid_identifier_and_private_table() -> None:
    """Comprueba que sample_rows rechaza identificadores maliciosos y tablas sin permiso."""
    with pytest.raises(ValueError):
        sample_rows("products; DROP TABLE orders;")

    with pytest.raises(psycopg.Error):
        sample_rows("internal_audit_logs")

    capped = json.loads(sample_rows("products", limit=50))
    assert capped["row_count"] == 10
    assert len(capped["rows"]) == 10
