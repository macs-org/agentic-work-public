from fastapi.testclient import TestClient

from app.main import create_app


def test_usage_persists_across_app_instances_with_same_database_url(tmp_path):
    db_path = tmp_path / "billing.db"
    database_url = f"sqlite:///{db_path}"

    first = TestClient(create_app(database_url=database_url))
    agent = first.post("/agents", json={"name": "persistent-agent", "plan": "starter"}).json()
    api_key = agent["api_key"]
    first.post("/customers", headers={"X-API-Key": api_key}, json={"customer_id": "cust_persist"})
    first.post(
        "/meter/event",
        headers={"X-API-Key": api_key},
        json={"customer_id": "cust_persist", "event_type": "request", "quantity": 3, "unit_price_cents": 40},
    )

    second = TestClient(create_app(database_url=database_url))
    usage = second.get("/meter/usage?customer_id=cust_persist", headers={"X-API-Key": api_key})

    assert usage.status_code == 200
    assert usage.json()["events"] == 1
    assert usage.json()["total_quantity"] == 3
    assert usage.json()["total_cost_cents"] == 120
