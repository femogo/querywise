from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from mcp.server.mcpserver import MCPServer
from psycopg import sql as pg_sql
from psycopg.rows import dict_row

from querywise.config import get_settings

mcp = MCPServer("querywise-readonly-postgres")

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _serialize_value(value: Any) -> Any:
    """Convierte tipos nativos de PostgreSQL a valores serializables en JSON."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _validate_identifier(name: str) -> str:
    """Valida que un nombre de tabla sea un identificador SQL seguro."""
    cleaned = name.strip()
    if not _IDENTIFIER_RE.match(cleaned):
        raise ValueError(f"Identificador SQL no valido: {name!r}")
    return cleaned


def _get_readonly_connection() -> psycopg.Connection[dict[str, Any]]:
    """Abre una conexion de solo lectura con timeout configurado."""
    settings = get_settings()
    conn = psycopg.connect(
        settings.readonly_dsn,
        row_factory=dict_row,
        options=(
            f"-c statement_timeout={settings.sql_statement_timeout_ms} "
            "-c default_transaction_read_only=on"
        ),
    )
    return conn


@mcp.tool()
def list_tables() -> str:
    """Lista las tablas de negocio visibles para el rol de solo lectura en el esquema public."""
    query = """
        SELECT c.relname AS table_name
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND has_table_privilege(current_user, c.oid, 'SELECT')
        ORDER BY c.relname;
    """
    with _get_readonly_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            tables = [row["table_name"] for row in cur.fetchall()]
    return json.dumps({"tables": tables}, ensure_ascii=False)


@mcp.tool()
def describe_table(table_name: str) -> str:
    """Devuelve columnas, tipos de datos y nulabilidad de una tabla permitida."""
    safe_table = _validate_identifier(table_name)
    query = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position;
    """
    with _get_readonly_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (safe_table,))
            columns = [dict(row) for row in cur.fetchall()]
    if not columns:
        raise ValueError(f"Tabla no encontrada o sin permisos: {safe_table}")
    return json.dumps({"table": safe_table, "columns": columns}, ensure_ascii=False)


@mcp.tool()
def sample_rows(table_name: str, limit: int = 5) -> str:
    """Devuelve una muestra acotada de filas (entre 1 y 10) de una tabla permitida."""
    safe_table = _validate_identifier(table_name)
    safe_limit = max(1, min(int(limit), 10))
    stmt = pg_sql.SQL("SELECT * FROM {} LIMIT %s;").format(pg_sql.Identifier(safe_table))
    with _get_readonly_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(stmt, (safe_limit,))
            rows = [{k: _serialize_value(v) for k, v in row.items()} for row in cur.fetchall()]
    return json.dumps(
        {"table": safe_table, "row_count": len(rows), "rows": rows}, ensure_ascii=False
    )


@mcp.tool()
def run_query(sql: str) -> str:
    """Ejecuta una consulta SELECT de solo lectura y devuelve los resultados en JSON."""
    settings = get_settings()
    cleaned_sql = sql.strip()
    if not cleaned_sql:
        raise ValueError("La consulta SQL no puede estar vacia.")

    with _get_readonly_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(cleaned_sql)
            if cur.description is None:
                return json.dumps({"columns": [], "rows": [], "row_count": 0, "truncated": False})
            columns = [desc.name for desc in cur.description]
            fetched = cur.fetchmany(settings.sql_max_rows + 1)
            truncated = len(fetched) > settings.sql_max_rows
            sliced = fetched[: settings.sql_max_rows]
            rows = [{k: _serialize_value(v) for k, v in row.items()} for row in sliced]

    return json.dumps(
        {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        },
        ensure_ascii=False,
    )


def main() -> None:
    """Arranca el servidor MCP por transporte stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
