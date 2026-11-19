from __future__ import annotations

import functools
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from psycopg import sql as pg_sql
from psycopg.rows import dict_row

from querywise.config import get_settings
from querywise.security.sql_guardrail import (
    ALLOWED_TABLES,
    BLOCKED_COLUMNS,
    SQLGuardrailError,
    validate_and_rewrite_sql,
)

mcp = MCPServer("querywise-readonly-postgres")

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _tool(fn: Any) -> Any:
    """Registra fn como herramienta MCP y devuelve al cliente el motivo de los errores previstos.

    Desde mcp 2.x, una excepcion que no sea ToolError llega al cliente solo como
    "Error executing tool <nombre>", sin el texto del guardrail o de PostgreSQL que
    necesita el bucle de autocorreccion. La funcion original queda intacta para los tests.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except (ValueError, psycopg.Error) as exc:
            raise ToolError(str(exc)) from exc

    mcp.add_tool(wrapper)
    return fn


def _serialize_value(value: Any) -> Any:
    """Convierte tipos nativos de PostgreSQL a valores serializables en JSON."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _validate_identifier(name: str) -> str:
    """Valida que un nombre de tabla sea un identificador SQL seguro y permitido."""
    cleaned = name.strip()
    if not _IDENTIFIER_RE.match(cleaned):
        raise ValueError(f"Identificador SQL no valido: {name!r}")
    if cleaned.lower() not in ALLOWED_TABLES:
        raise ValueError(f"Tabla no permitida: {cleaned!r}")
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


def _check_explain_cost(
    cur: psycopg.Cursor[dict[str, Any]], safe_sql: str, max_cost: float
) -> float:
    """Ejecuta EXPLAIN (FORMAT JSON) y verifica que el coste total no supere el umbral."""
    cur.execute(f"EXPLAIN (FORMAT JSON) {safe_sql}")
    row = cur.fetchone()
    if not row or "QUERY PLAN" not in row:
        raise SQLGuardrailError("No se pudo obtener el plan de ejecucion EXPLAIN.")

    plan_payload = row["QUERY PLAN"]
    if isinstance(plan_payload, str):
        plan_payload = json.loads(plan_payload)

    total_cost = float(plan_payload[0]["Plan"]["Total Cost"])
    if total_cost > max_cost:
        raise SQLGuardrailError(
            f"El coste estimado de la consulta ({total_cost:.2f}) supera el maximo permitido "
            f"({max_cost:.2f})."
        )
    return total_cost


@_tool
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
            tables = [
                row["table_name"]
                for row in cur.fetchall()
                if row["table_name"].lower() in ALLOWED_TABLES
            ]
    return json.dumps({"tables": tables}, ensure_ascii=False)


@_tool
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


@_tool
def sample_rows(table_name: str, limit: int = 5) -> str:
    """Devuelve una muestra acotada de filas (entre 1 y 10) excluyendo columnas PII."""
    safe_table = _validate_identifier(table_name)
    safe_limit = max(1, min(int(limit), 10))
    col_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position;
    """
    with _get_readonly_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(col_query, (safe_table,))
            safe_cols = [
                row["column_name"]
                for row in cur.fetchall()
                if row["column_name"].lower() not in BLOCKED_COLUMNS
            ]
            if not safe_cols:
                raise ValueError(f"No hay columnas seguras disponibles en {safe_table}")

            cols_ident = pg_sql.SQL(", ").join(pg_sql.Identifier(c) for c in safe_cols)
            stmt = pg_sql.SQL("SELECT {} FROM {} LIMIT %s;").format(
                cols_ident, pg_sql.Identifier(safe_table)
            )
            cur.execute(stmt, (safe_limit,))
            rows = [{k: _serialize_value(v) for k, v in row.items()} for row in cur.fetchall()]
    return json.dumps(
        {"table": safe_table, "row_count": len(rows), "rows": rows}, ensure_ascii=False
    )


@_tool
def run_query(sql: str) -> str:
    """Valida el AST, verifica el coste EXPLAIN y ejecuta una consulta SELECT segura."""
    settings = get_settings()
    safe_sql = validate_and_rewrite_sql(sql, max_rows=settings.sql_max_rows)

    with _get_readonly_connection() as conn:
        with conn.cursor() as cur:
            _check_explain_cost(cur, safe_sql, settings.sql_max_explain_cost)
            cur.execute(safe_sql)
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
