# Agent Billing & Metering API

Drop-in usage metering, spending limits, x402 payment gating, plan checkout, and invoice generation for AI agents.

Built for BTNOMB bounty `idea_023`.

Reviewer evidence added during acceptance upgrade:

- `DEMO.md` — end-to-end local review workflow.
- `ACCEPTANCE_CHECKLIST.md` — bounty requirement mapping to endpoints/tests/files.
- `LIMITATIONS.md` — MVP vs production hardening notes.
- `demo/sample_session.json` — sanitized request/response examples.
- `demo/test-rerun-2026-05-08.txt` — rerun command log and public URL verification.

## Features

- FastAPI backend with OpenAPI docs at `/docs` and `/openapi.json`.
- SQLAlchemy persistence with SQLite for local/demo and Postgres-compatible `DATABASE_URL`.
- Per-agent API key auth via `X-API-Key`.
- Customer records with optional spend limits.
- Usage event metering by customer, event type, quantity, and unit price.
- Aggregated usage query.
- x402-compatible payment requirements for gated resources and paid plans.
- Paid gate access is recorded as usage so revenue dashboards and invoices include micropayments.
- Usage-based invoice generation.
- HTML dashboard with revenue/customer/event stats.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Open docs:

```text
http://127.0.0.1:8000/docs
```

## Database

Default:

```text
sqlite:///agent_billing.db
```

For Postgres, set `DATABASE_URL` in the deployment environment and instantiate with that URL, for example:

```text
postgresql+psycopg://user:pass@host:5432/agent_billing
```

The app uses SQLAlchemy models for:

- `agents`
- `customers`
- `meter_events`
- `invoices`

## API walkthrough

Create an agent:

```bash
curl -sS -X POST http://127.0.0.1:8000/agents \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo-agent","plan":"starter"}'
```

Create a customer:

```bash
curl -sS -X POST http://127.0.0.1:8000/customers \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust_1","spend_limit_cents":5000}'
```

Log usage:

```bash
curl -sS -X POST http://127.0.0.1:8000/meter/event \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust_1","event_type":"tokens","quantity":1250,"unit_price_cents":2}'
```

Query usage:

```bash
curl -sS 'http://127.0.0.1:8000/meter/usage?customer_id=cust_1' \
  -H "X-API-Key: $API_KEY"
```

Generate invoice:

```bash
curl -sS -X POST http://127.0.0.1:8000/invoice/generate \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust_1","period_start":"2026-05-01","period_end":"2026-05-31"}'
```

Use payment gate:

```bash
curl -i -X POST http://127.0.0.1:8000/gate \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust_1","resource":"/premium/tool","amount_cents":25}'
```

Unpaid requests return `402` with x402-style payment requirements:

```json
{
  "x402Version": 1,
  "accepts": [{
    "scheme": "exact",
    "network": "base",
    "maxAmountRequired": "250000",
    "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "extra": {"name": "USD Coin", "version": "2"}
  }]
}
```

Retry with `X-PAYMENT` after facilitator verification/payment collection:

```bash
curl -sS -X POST http://127.0.0.1:8000/gate \
  -H "X-API-Key: $API_KEY" \
  -H "X-PAYMENT: <payment-proof>" \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust_1","resource":"/premium/tool","amount_cents":25}'
```

## x402 notes

The API emits Base USDC payment requirements compatible with x402 exact-payment flows:

- network: `base`
- asset: Base USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- domain extra: `{ "name": "USD Coin", "version": "2" }`

Production deployments should wire `X-PAYMENT` to a facilitator verification step before treating a request as paid. The current demo accepts any `X-PAYMENT` header to keep the MVP runnable without facilitator credentials.

## Tests

```bash
.venv/bin/python -m pytest tests -q
```

Current result after acceptance-upgrade rerun (2026-05-08):

```text
9 passed in 1.95s
```

## Acceptance mapping

- Functional endpoints: implemented.
- Documentation/OpenAPI: `/docs`, `/openapi.json`, this README.
- Usage metering per agent/customer: implemented and tested.
- Invoice generation: implemented and tested.
- Spending limits: implemented and tested.
- Dashboard: implemented and tested.
- Plan billing: x402-compatible payment requirements via `/plans/checkout`.
- Postgres storage: SQLAlchemy-backed, `DATABASE_URL` compatible; SQLite tested locally.
- Base L2 x402: Base USDC requirements emitted; facilitator verification hook documented.
