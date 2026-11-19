import argparse
import asyncio
import json

import uvicorn

from querywise.graph.workflow import build_text_to_sql_graph


async def _ask_once(question: str, max_retries: int) -> None:
    graph = build_text_to_sql_graph()
    result = await graph.ainvoke({"question": question, "max_retries": max_retries})
    output = {
        "status": result.get("status"),
        "question": question,
        "generated_sql": result.get("generated_sql"),
        "assumptions": result.get("assumptions", []),
        "final_answer": result.get("final_answer"),
        "retry_count": result.get("retry_count", 0),
        "error": result.get("error"),
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="QueryWise CLI & HTTP server entrypoint")
    parser.add_argument(
        "--question", "-q", type=str, help="Run a single natural-language question."
    )
    parser.add_argument(
        "--max-retries", type=int, default=2, help="Max SQL self-correction retries."
    )
    parser.add_argument(
        "--serve", action="store_true", help="Start the FastAPI server with Uvicorn."
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for HTTP server.")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP server.")
    args = parser.parse_args()

    if args.serve or not args.question:
        uvicorn.run("querywise.api.app:app", host=args.host, port=args.port, reload=False)
    else:
        asyncio.run(_ask_once(args.question, args.max_retries))


if __name__ == "__main__":
    main()
