from typing import Any

from fastapi.testclient import TestClient

from querywise.api.app import create_app


class _FakeGraph:
    def __init__(self, final_state: dict[str, Any]) -> None:
        self._final_state = final_state
        self.last_input: dict[str, Any] | None = None

    async def ainvoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_input = payload
        return self._final_state


def test_health_endpoint_returns_service_metadata() -> None:
    app = create_app(graph=_FakeGraph({}))
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "querywise"
    assert "ollama_model" in body


def test_query_endpoint_returns_structured_trace_on_success() -> None:
    fake_graph = _FakeGraph(
        {
            "status": "success",
            "final_answer": "El ingreso neto total es 150000.0.",
            "generated_sql": "SELECT SUM(subtotal_amount) AS net_rev FROM orders LIMIT 1",
            "sql_reasoning": "Sum net subtotal_amount excluding cancelled orders.",
            "assumptions": ["Excludes cancelled and refunded orders."],
            "query_result": {"rows": [{"net_rev": 150000.0}]},
            "retry_count": 0,
            "sql_history": ["SELECT SUM(subtotal_amount) AS net_rev FROM orders LIMIT 1"],
            "error": None,
        }
    )
    client = TestClient(create_app(graph=fake_graph))

    response = client.post(
        "/query",
        json={"question": "¿Cuál es el ingreso neto total?", "max_retries": 1},
    )
    assert response.status_code == 200
    assert fake_graph.last_input == {
        "question": "¿Cuál es el ingreso neto total?",
        "max_retries": 1,
    }

    data = response.json()
    assert data["status"] == "success"
    assert data["row_count"] == 1
    assert data["rows"] == [{"net_rev": 150000.0}]
    assert data["assumptions"] == ["Excludes cancelled and refunded orders."]
    assert data["latency_ms"] >= 0


def test_query_endpoint_validates_short_question() -> None:
    client = TestClient(create_app(graph=_FakeGraph({})))
    response = client.post("/query", json={"question": "hi"})
    assert response.status_code == 422
