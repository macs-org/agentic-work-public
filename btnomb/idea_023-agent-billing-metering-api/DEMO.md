# Reviewer Demo — Agent Billing & Metering API

Bounty: `idea_023` — Agent Billing & Metering API

This demo shows the submitted FastAPI MVP running locally with in-memory SQLite. It does not require any private credentials, real wallet keys, or live x402 facilitator access.

## 1. Install and run tests

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-06_btnomb-agent-billing-metering-api/work/agent_billing_api
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pytest tests -q
```

Verified on 2026-05-08:

```text
.........                                                                [100%]
9 passed in 1.95s
```

## 2. Start the API

```bash
./.venv/bin/uvicorn app.main:app --reload
```

OpenAPI docs:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

## 3. End-to-end API flow

Create an agent and save its generated API key:

```bash
curl -sS -X POST http://127.0.0.1:8000/agents \
  -H 'Content-Type: application/json' \
  -d '{"name":"reviewer-demo-agent","plan":"starter"}'
```

Create a customer with a spend limit:

```bash
curl -sS -X POST http://127.0.0.1:8000/customers \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust_demo","spend_limit_cents":5000}'
```

Record usage:

```bash
curl -sS -X POST http://127.0.0.1:8000/meter/event \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust_demo","event_type":"tokens","quantity":1250,"unit_price_cents":2}'
```

Expected result includes `cost_cents: 2500`.

Query usage:

```bash
curl -sS 'http://127.0.0.1:8000/meter/usage?customer_id=cust_demo' \
  -H "X-API-Key: $API_KEY"
```

Expected aggregate after the usage event:

```json
{"events":1,"total_quantity":1250,"total_cost_cents":2500}
```

Call a gated resource without payment:

```bash
curl -i -X POST http://127.0.0.1:8000/gate \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust_demo","resource":"/premium/tool","amount_cents":25}'
```

Expected result: HTTP 402 with x402-style Base USDC payment requirements.

Retry after facilitator/payment verification using an `X-PAYMENT` proof placeholder:

```bash
curl -sS -X POST http://127.0.0.1:8000/gate \
  -H "X-API-Key: $API_KEY" \
  -H "X-PAYMENT: demo-payment-proof" \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust_demo","resource":"/premium/tool","amount_cents":25}'
```

Expected result includes `status: paid`; the paid gate access is also written as a metered event so it appears in usage and invoices.

Generate an invoice:

```bash
curl -sS -X POST http://127.0.0.1:8000/invoice/generate \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust_demo","period_start":"2026-05-01","period_end":"2026-05-31"}'
```

Open the dashboard:

```text
http://127.0.0.1:8000/dashboard
```

Pass `X-API-Key` when calling the dashboard from scripts/tests.

## 4. Sample artifacts

See `demo/sample_session.json` for redacted request/response samples generated from the app with `FastAPI TestClient` and `sqlite:///:memory:`.

## 5. Why this meets the bounty

The deliverable is a real drop-in billing layer: agents get API keys, customers can be metered, spend limits prevent overage, x402-compatible payment requirements gate paid endpoints/plans, usage persists through SQLAlchemy, invoices summarize billing, and `/dashboard` exposes reviewer-visible billing state.
