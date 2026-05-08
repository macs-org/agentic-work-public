# Acceptance Checklist — BTNOMB idea_023

Bounty: Agent Billing & Metering API — Drop-in usage tracking and x402 micropayments for any AI agent

## Requirement mapping

- [x] `POST /meter/event` logs usage events.
  - Code: `app/main.py`, `meter_event`
  - Tests: `tests/test_app.py::test_meter_event_records_usage_and_usage_query_aggregates_by_customer`

- [x] `GET /meter/usage` returns usage summaries.
  - Code: `app/main.py`, `meter_usage`
  - Tests: `tests/test_app.py`, `tests/test_persistence.py`

- [x] `POST /gate` returns x402-compatible payment requirements when unpaid.
  - Code: `app/main.py`, `gate`, `x402_requirements`
  - Tests: `tests/test_x402_gate.py::test_gate_returns_x402_payment_requirements_without_payment_header`

- [x] `POST /gate` accepts paid access and records micropayment usage.
  - Code: `app/main.py`, `gate`
  - Tests: `tests/test_x402_gate.py::test_gate_accepts_payment_header_and_records_paid_access_event`

- [x] Per-agent API keys protect customer, usage, invoice, gate, plan, and dashboard routes.
  - Code: `app/main.py`, `current_agent`
  - Tests: authenticated calls throughout `tests/`

- [x] Spending limits block over-limit usage/gate attempts with HTTP 402.
  - Code: `app/main.py`, spend-limit checks in `meter_event` and `gate`
  - Tests: `tests/test_app.py::test_spending_limit_blocks_meter_events_that_exceed_customer_limit`, `tests/test_x402_gate.py::test_gate_enforces_spending_limits_before_payment`

- [x] Invoice generation summarizes usage by event type and total cost.
  - Code: `app/main.py`, `invoice`
  - Tests: `tests/test_app.py::test_invoice_generation_summarizes_usage_and_dashboard_renders`

- [x] Plan checkout emits x402 requirements for paid plan upgrades.
  - Code: `app/main.py`, `plan_checkout`
  - Tests: `tests/test_app.py::test_openapi_docs_and_plan_checkout_are_available`

- [x] Dashboard renders agent billing state.
  - Code: `app/main.py`, `dashboard`
  - Tests: `tests/test_app.py::test_invoice_generation_summarizes_usage_and_dashboard_renders`

- [x] SQLAlchemy persistence supports SQLite locally and `DATABASE_URL` for deployed DBs.
  - Code: `app/main.py`, `make_session_factory`
  - Tests: `tests/test_persistence.py::test_usage_persists_across_app_instances_with_same_database_url`

- [x] OpenAPI docs are available.
  - Code: `FastAPI(...)` app metadata in `app/main.py`
  - Tests: `tests/test_app.py::test_openapi_docs_and_plan_checkout_are_available`

- [x] Reviewer documentation and sample evidence are included.
  - Files: `README.md`, `DEMO.md`, `ACCEPTANCE_CHECKLIST.md`, `LIMITATIONS.md`, `demo/sample_session.json`

## Verification rerun

Command:

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-06_btnomb-agent-billing-metering-api/work/agent_billing_api
./.venv/bin/python -m pytest tests -q
```

Result on 2026-05-08:

```text
.........                                                                [100%]
9 passed in 1.95s
```

## Public URL check

Public artifact URL verified reachable without auth on 2026-05-08:

```text
https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_023-agent-billing-metering-api
HTTP 200
content_type=text/html; charset=utf-8
```

The older private PR URL in local notes returned HTTP 404 without auth and should not be used as the reviewer-facing artifact.
