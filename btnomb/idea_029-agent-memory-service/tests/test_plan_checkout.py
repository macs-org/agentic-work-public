from fastapi.testclient import TestClient

from app.main import create_app


def test_plan_checkout_returns_x402_requirements_for_paid_plan():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    agent = client.post("/agents", json={"name": "memory-agent"}).json()

    response = client.post(
        "/plans/checkout",
        headers={"X-API-Key": agent["api_key"]},
        json={"plan": "starter"},
    )

    assert response.status_code == 402
    body = response.json()
    assert body["x402Version"] == 1
    assert body["description"] == "Upgrade memory service plan to starter"
    requirement = body["accepts"][0]
    assert requirement["scheme"] == "exact"
    assert requirement["network"] == "base"
    assert requirement["maxAmountRequired"] == "19000000"
    assert requirement["asset"] == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    assert requirement["extra"] == {"name": "USD Coin", "version": "2"}


def test_free_plan_checkout_is_rejected():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    agent = client.post("/agents", json={"name": "memory-agent"}).json()

    response = client.post(
        "/plans/checkout",
        headers={"X-API-Key": agent["api_key"]},
        json={"plan": "free"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_paid_plan"
