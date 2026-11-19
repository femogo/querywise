import json
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _server_params() -> StdioServerParameters:
    """Build stdio launch parameters for the local QueryWise MCP server."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "querywise.mcp_server.server"],
    )


def _extract_tool_payload(result: Any) -> dict[str, Any]:
    """Extract and parse the JSON payload returned by an MCP CallToolResult."""
    if getattr(result, "structuredContent", None) and isinstance(result.structuredContent, dict):
        return result.structuredContent

    texts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            texts.append(text)

    raw = "\n".join(texts).strip()
    if not raw:
        return {"ok": False, "error": "Empty response from MCP tool."}

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        return {"ok": True, "data": parsed}
    except json.JSONDecodeError:
        # mcp 2.x expone is_error; versiones anteriores, isError
        is_error = getattr(result, "is_error", getattr(result, "isError", False))
        return {"ok": not bool(is_error), "raw": raw}


class QueryWiseMCPClient:
    """Async wrapper around the QueryWise stdio MCP server tools."""

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Invoke a single MCP tool over a fresh stdio session and return parsed JSON."""
        async with stdio_client(_server_params()) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments or {})
                return _extract_tool_payload(result)

    async def get_full_schema(self) -> str:
        """Discover all allowed tables and their columns formatted for the LLM prompt."""
        async with stdio_client(_server_params()) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tables_res = await session.call_tool("list_tables", {})
                tables_payload = _extract_tool_payload(tables_res)
                tables = tables_payload.get("tables", [])

                schema_blocks: list[str] = []
                for table_info in tables:
                    table_name = (
                        table_info["table_name"]
                        if isinstance(table_info, dict)
                        else str(table_info)
                    )
                    desc_res = await session.call_tool(
                        "describe_table", {"table_name": table_name}
                    )
                    desc_payload = _extract_tool_payload(desc_res)
                    columns = desc_payload.get("columns", [])

                    col_lines = []
                    for col in columns:
                        col_name = col.get("column_name", "")
                        data_type = col.get("data_type", "")
                        nullable = "NULL" if col.get("is_nullable") == "YES" else "NOT NULL"
                        col_lines.append(f"  - {col_name} ({data_type}, {nullable})")

                    schema_blocks.append(f"Table `{table_name}`:\n" + "\n".join(col_lines))

                return "\n\n".join(schema_blocks)

    async def run_query(self, sql: str) -> dict[str, Any]:
        """Execute a read-only SQL query through the guarded MCP run_query tool."""
        return await self.call_tool("run_query", {"sql": sql})