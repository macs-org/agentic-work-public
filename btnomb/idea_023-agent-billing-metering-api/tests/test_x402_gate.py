from fastapi.testclient import TestClient

from app.main import create_app


def create_agent_and_customer(client: TestClient, spend_limit_cents: int | None = None):
    agent = client.post("/agents", json={"name": "gate-agent", "plan": "starter"}).json()
    api_key = agent["api_key"]
    payload = {"customer_id": "cust_gate"}
    if spend_limit_cents is not None:
        payload["spend_limit_cents"] = spend_limit_cents
    response = client.post("/customers", headers={"X-API-Key": api_key}, json=payload)
    assert response.status_code == 201
    return api_key


def test_gate_returns_x402_payment_requirements_without_payment_header():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    api_key = create_agent_and_customer(client)

    response = client.post(
        "/gate",
        headers={"X-API-Key": api_key},
        json={"customer_id": "cust_gate", "resource": "/premium/tool", "amount_cents": 25},
    )

    assert response.status_code == 402
    body = response.json()
    assert body["x402Version"] == 1
    assert body["error"] == "X-PAYMENT header is required"
    requirement = body["accepts"][0]
    assert requirement["scheme"] == "exact"
    assert requirement["network"] == "base"
    assert requirement["maxAmountRequired"] == "250000"
    assert requirement["payTo"].startswith("0x")
    assert requirement["asset"] == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    assert requirement["extra"] == {"name": "USD Coin", "version": "2"}


def test_gate_accepts_payment_header_and_records_paid_access_event():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    api_key = create_agent_and_customer(client)

    response = client.post(
        "/gate",
        headers={"X-API-Key": api_key, "X-PAYMENT": "demo-payment-proof"},
        json={"customer_id": "cust_gate", "resource": "/premium/tool", "amount_cents": 25},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "paid"

    usage = client.get("/meter/usage?customer_id=cust_gate", headers={"X-API-Key": api_key})
    assert usage.status_code == 200
    assert usage.json()["events"] == 1
    assert usage.json()["total_cost_cents"] == 25


def test_gate_enforces_spending_limits_before_payment():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    api_key = create_agent_and_customer(client, spend_limit_cents=20)

    response = client.post(
        "/gate",
        headers={"X-API-Key": api_key, "X-PAYMENT": "demo-payment-proof"},
        json={"customer_id": "cust_gate", "resource": "/premium/tool", "amount_cents": 25},
    )

    assert response.status_code == 402
    assert response.json()["error"] == "spending_limit_exceeded"
