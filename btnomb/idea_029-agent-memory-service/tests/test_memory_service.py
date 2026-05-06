from fastapi.testclient import TestClient

from app.main import create_app


def create_agent(client, name="memory-agent"):
    response = client.post("/agents", json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_memory_search_is_namespace_isolated_and_ranks_relevant_content():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    agent = create_agent(client)
    api_key = agent["api_key"]

    first = client.post(
        "/memory",
        headers={"X-API-Key": api_key},
        json={"namespace": "project-a", "content": "Python FastAPI billing metering invoices x402", "metadata": {"kind": "api"}},
    )
    assert first.status_code == 201
    second = client.post(
        "/memory",
        headers={"X-API-Key": api_key},
        json={"namespace": "project-a", "content": "Sourdough bread starter hydration feeding schedule"},
    )
    assert second.status_code == 201
    other_ns = client.post(
        "/memory",
        headers={"X-API-Key": api_key},
        json={"namespace": "project-b", "content": "FastAPI should not leak across namespaces"},
    )
    assert other_ns.status_code == 201

    search = client.get("/memory/search", headers={"X-API-Key": api_key}, params={"namespace": "project-a", "q": "FastAPI invoice API", "top_k": 2})

    assert search.status_code == 200
    results = search.json()["results"]
    assert results[0]["memory_id"] == first.json()["memory_id"]
    assert all(r["namespace"] == "project-a" for r in results)
    assert results[0]["score"] > results[1]["score"]


def test_delete_removes_memory_from_search_and_usage_is_metered():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    agent = create_agent(client)
    api_key = agent["api_key"]
    memory = client.post(
        "/memory",
        headers={"X-API-Key": api_key},
        json={"namespace": "default", "content": "delete me from vector search"},
    ).json()

    deleted = client.delete(f"/memory/{memory['memory_id']}", headers={"X-API-Key": api_key})
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    search = client.get("/memory/search", headers={"X-API-Key": api_key}, params={"q": "delete vector"})
    assert search.status_code == 200
    assert search.json()["results"] == []

    usage = client.get("/usage", headers={"X-API-Key": api_key})
    assert usage.status_code == 200
    assert usage.json()["stores"] == 1
    assert usage.json()["searches"] == 1
    assert usage.json()["deletes"] == 1


def test_dashboard_and_openapi_are_available_and_data_persists(tmp_path):
    db_path = tmp_path / "memory.db"
    database_url = f"sqlite:///{db_path}"
    first = TestClient(create_app(database_url=database_url))
    agent = create_agent(first)
    api_key = agent["api_key"]
    first.post("/memory", headers={"X-API-Key": api_key}, json={"namespace": "persist", "content": "persistent agent memory"})

    second = TestClient(create_app(database_url=database_url))
    search = second.get("/memory/search", headers={"X-API-Key": api_key}, params={"namespace": "persist", "q": "agent memory"})
    assert search.status_code == 200
    assert len(search.json()["results"]) == 1

    dashboard = second.get("/dashboard", headers={"X-API-Key": api_key})
    assert dashboard.status_code == 200
    assert "memory-agent" in dashboard.text
    assert "persistent agent memory" in dashboard.text

    docs = second.get("/openapi.json")
    assert docs.status_code == 200
    assert "/memory/search" in docs.json()["paths"]
