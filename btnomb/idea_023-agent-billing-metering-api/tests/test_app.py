from fastapi.testclient import TestClient

from app.main import create_app


def test_meter_event_records_usage_and_usage_query_aggregates_by_customer():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))

    agent_resp = client.post("/agents", json={"name": "research-agent", "plan": "starter"})
    assert agent_resp.status_code == 201
    agent = agent_resp.json()
    api_key = agent["api_key"]

    customer_resp = client.post(
        "/customers",
        headers={"X-API-Key": api_key},
        json={"customer_id": "cust_1", "spend_limit_cents": 5000},
    )
    assert customer_resp.status_code == 201

    event_resp = client.post(
        "/meter/event",
        headers={"X-API-Key": api_key},
        json={"customer_id": "cust_1", "event_type": "tokens", "quantity": 1250, "unit_price_cents": 2},
    )
    assert event_resp.status_code == 201
    assert event_resp.json()["cost_cents"] == 2500

    usage_resp = client.get("/meter/usage?customer_id=cust_1", headers={"X-API-Key": api_key})
    assert usage_resp.status_code == 200
    usage = usage_resp.json()
    assert usage["agent_id"] == agent["agent_id"]
    assert usage["customer_id"] == "cust_1"
    assert usage["total_quantity"] == 1250
    assert usage["total_cost_cents"] == 2500
    assert usage["events"] == 1


def test_spending_limit_blocks_meter_events_that_exceed_customer_limit():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    agent = client.post("/agents", json={"name": "limit-agent", "plan": "starter"}).json()
    api_key = agent["api_key"]
    client.post(
        "/customers",
        headers={"X-API-Key": api_key},
        json={"customer_id": "cust_limit", "spend_limit_cents": 100},
    )

    response = client.post(
        "/meter/event",
        headers={"X-API-Key": api_key},
        json={"customer_id": "cust_limit", "event_type": "request", "quantity": 2, "unit_price_cents": 75},
    )

    assert response.status_code == 402
    body = response.json()
    assert body["error"] == "spending_limit_exceeded"
    assert body["current_spend_cents"] == 0
    assert body["attempted_cost_cents"] == 150


def test_gate_returns_x402_payment_requirements_when_unpaid_and_allows_paid_request():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    agent = client.post("/agents", json={"name": "gate-agent", "plan": "starter"}).json()
    api_key = agent["api_key"]
    client.post(
        "/customers",
        headers={"X-API-Key": api_key},
        json={"customer_id": "cust_gate", "spend_limit_cents": 1000},
    )

    unpaid = client.post(
        "/gate",
        headers={"X-API-Key": api_key},
        json={"customer_id": "cust_gate", "resource": "/premium/tool", "amount_cents": 25},
    )
    assert unpaid.status_code == 402
    challenge = unpaid.json()
    assert challenge["x402Version"] == 1
    assert challenge["accepts"][0]["network"] == "base"
    assert challenge["accepts"][0]["asset"] == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    assert challenge["accepts"][0]["maxAmountRequired"] == "250000"

    paid = client.post(
        "/gate",
        headers={"X-API-Key": api_key, "X-PAYMENT": "demo-paid"},
        json={"customer_id": "cust_gate", "resource": "/premium/tool", "amount_cents": 25},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"


def test_invoice_generation_summarizes_usage_and_dashboard_renders():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    agent = client.post("/agents", json={"name": "invoice-agent", "plan": "pro"}).json()
    api_key = agent["api_key"]
    client.post("/customers", headers={"X-API-Key": api_key}, json={"customer_id": "cust_inv"})
    client.post(
        "/meter/event",
        headers={"X-API-Key": api_key},
        json={"customer_id": "cust_inv", "event_type": "tokens", "quantity": 100, "unit_price_cents": 3},
    )

    invoice_resp = client.post(
        "/invoice/generate",
        headers={"X-API-Key": api_key},
        json={"customer_id": "cust_inv", "period_start": "2026-05-01", "period_end": "2026-05-31"},
    )
    assert invoice_resp.status_code == 201
    invoice = invoice_resp.json()
    assert invoice["customer_id"] == "cust_inv"
    assert invoice["total_cents"] == 300
    assert invoice["line_items"][0]["event_type"] == "tokens"

    dashboard = client.get("/dashboard", headers={"X-API-Key": api_key})
    assert dashboard.status_code == 200
    assert "invoice-agent" in dashboard.text
    assert "cust_inv" in dashboard.text
    assert "$3.00" in dashboard.text


def test_openapi_docs_and_plan_checkout_are_available():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    agent = client.post("/agents", json={"name": "billing-agent", "plan": "free"}).json()
    api_key = agent["api_key"]

    docs = client.get("/openapi.json")
    assert docs.status_code == 200
    assert "/meter/event" in docs.json()["paths"]

    checkout = client.post("/plans/checkout", headers={"X-API-Key": api_key}, json={"plan": "pro"})
    assert checkout.status_code == 402
    body = checkout.json()
    assert body["description"] == "Upgrade agent billing plan to pro"
    assert body["accepts"][0]["maxAmountRequired"] == "99000000"
