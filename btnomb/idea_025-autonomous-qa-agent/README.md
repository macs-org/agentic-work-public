# Autonomous QA Agent

Compact FastAPI MVP for BTNOMB `idea_025`: a service that continuously runs structured QA suites against AI agent endpoints, stores run history, detects regressions/drift, and exposes alerts plus a dashboard.

## Features

- FastAPI backend with OpenAPI docs at `/docs`.
- SQLAlchemy persistence with SQLite by default; `DATABASE_URL` can point at Postgres for deployment.
- Per-agent API key auth via `X-API-Key`.
- YAML or JSON test suite definitions.
- Assertions: `exact`, `contains`, `regex`, and lightweight deterministic `similarity`.
- Manual runs: `POST /suites/{suite_id}/run`.
- Scheduled run representation: `GET /schedules`; compact tick runner: `POST /scheduler/tick`.
- On-deploy trigger endpoint: `POST /webhooks/deploy/{suite_id}`.
- Regression alerts when a previously passing case fails.
- Drift alerts when semantic similarity drops by the suite `drift_threshold`.
- Alert delivery records for dashboard/internal, email via SMTP env vars, and webhook POSTs.
- Detailed run reports with per-case output, assertions, diff, pass rate, and trend summary.
- HTML dashboard at `/dashboard`.
- x402-compatible paid plan checkout response at `POST /plans/checkout`.
- Dockerfile, Docker Compose, Render blueprint, and `.env.example` included; no secrets committed.
- Production health/readiness endpoints: `/healthz` and `/readyz`.
- Stdlib production smoke test: `scripts/production_smoke_test.py` validates a live local or hosted deployment end-to-end.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Open the API docs:

```text
http://127.0.0.1:8000/docs
```

## Production deployment and verification

Counter-response upgrade, 2026-05-09: the package now includes live-deployment readiness materials and a smoke-test verifier.

```bash
# Run as a deployable service from the packaged artifact
docker compose up --build

# Verify a live local or hosted deployment
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/readyz
AUTONOMOUS_QA_BASE_URL=http://127.0.0.1:8000 python3 scripts/production_smoke_test.py
```

Deployment/production files:

- `DEPLOYMENT.md` — Docker/Render/Railway/Fly deployment instructions and verification checklist.
- `docker-compose.yml` — one-command Docker deployment with persistent SQLite volume and `/readyz` health check.
- `render.yaml` — hosted Render blueprint metadata with `/readyz` health check.
- `.env.example` — production environment variable template; keeps database/SMTP secrets out of source.
- `scripts/production_smoke_test.py` — stdlib smoke test for `/healthz`, `/readyz`, agent registration, suite creation, manual run, schedules, summary, x402 checkout, and dashboard.
- `samples/production-smoke-output.json` — captured smoke-test result against a live uvicorn process.

## Database

Default local database:

```text
sqlite:///autonomous_qa.db
```

Use Postgres-compatible SQLAlchemy URLs in production:

```bash
export DATABASE_URL='postgresql+psycopg://user:pass@host:5432/autonomous_qa'
```

## API walkthrough

Create an agent and keep the returned API key:

```bash
curl -sS -X POST http://127.0.0.1:8000/agents \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo-owner","plan":"starter"}'
```

Create a suite from YAML:

```bash
curl -sS -X POST http://127.0.0.1:8000/suites \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "definition": "name: Demo QA Suite\nschedule:\n  interval: daily\nalerts:\n  emails:\n    - qa@example.com\ncases:\n  - id: greeting\n    input: Say hello\n    expected: hello world\n    mock_response: hello world\n    assertions:\n      - type: exact\n        value: hello world\n  - id: ticket\n    input: Return ticket number\n    expected: TICKET-123\n    mock_response: Created ticket TICKET-123 successfully.\n    assertions:\n      - type: regex\n        pattern: 'TICKET-[0-9]+'\n"
}
JSON
```

Run it manually:

```bash
curl -sS -X POST http://127.0.0.1:8000/suites/$SUITE_ID/run \
  -H "X-API-Key: $API_KEY"
```

View run history and reports:

```bash
curl -sS http://127.0.0.1:8000/runs -H "X-API-Key: $API_KEY"
curl -sS http://127.0.0.1:8000/runs/$RUN_ID -H "X-API-Key: $API_KEY"
curl -sS http://127.0.0.1:8000/reports/summary -H "X-API-Key: $API_KEY"
```

Check schedules and trigger due scheduled runs:

```bash
curl -sS http://127.0.0.1:8000/schedules -H "X-API-Key: $API_KEY"
curl -sS -X POST http://127.0.0.1:8000/scheduler/tick -H "X-API-Key: $API_KEY"
```

Trigger from CI/CD after deploy:

```bash
curl -sS -X POST http://127.0.0.1:8000/webhooks/deploy/$SUITE_ID \
  -H "X-API-Key: $API_KEY"
```

Open dashboard:

```text
GET /dashboard with X-API-Key header
```

Request x402-compatible payment requirements for a paid plan:

```bash
curl -i -X POST http://127.0.0.1:8000/plans/checkout \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"plan":"pro"}'
```

## Test suite definition format

Suites can be JSON objects or YAML strings. Minimal shape:

```yaml
name: Production Agent QA
endpoint: https://your-agent.example/run
method: POST
schedule:
  interval: hourly
alerts:
  emails:
    - qa@example.com
  webhooks:
    - https://hooks.example/qa-regression
drift_threshold: 0.15
cases:
  - id: refund_policy
    input: Explain the refund policy
    expected: Refunds are processed within five business days
    payload:
      prompt: Explain the refund policy
    assertions:
      - type: contains
        value: refunds
      - type: similarity
        value: Refunds are processed within five business days
        threshold: 0.75
  - id: ticket_format
    input: Create a support ticket
    expected: TICKET-123
    assertions:
      - type: regex
        pattern: "TICKET-[0-9]+"
```

For local demos/tests, use `mock_response` or `mock_responses` per case. Production suites should set `endpoint` and optional per-case `payload`, `headers`, or `method`.

## Alert delivery

Email uses standard SMTP environment variables:

```bash
export SMTP_HOST=smtp.example.com
export SMTP_PORT=587
export SMTP_TLS=true
export SMTP_USERNAME=...
export SMTP_PASSWORD=...
export SMTP_FROM=qa-agent@example.com
```

If SMTP is not configured, email alerts are safely captured in the database with status `captured:no_smtp_configured`. Non-HTTP webhook targets are captured with `captured:non_http_webhook`, which keeps the MVP self-contained for demos and tests.

## Docker

```bash
docker build -t autonomous-qa-agent .
docker run -p 8000:8000 -e DATABASE_URL=sqlite:///autonomous_qa.db autonomous-qa-agent
```

## Tests

Use `PYTHONPATH=.` as requested:

```bash
PYTHONPATH=. python3 -m pytest tests -q
```

Expected current result:

```text
.......                                                                  [100%]
7 passed in 1.03s
```

Captured reviewer verification from 2026-05-09 is in `samples/test-output.txt`.

## Reviewer evidence pack

- `DEMO.md` — step-by-step install, test, local API, scheduler, dashboard, regression, and x402 checkout walkthrough.
- `ACCEPTANCE_CHECKLIST.md` — bounty requirement mapping to endpoints, code, tests, and evidence files.
- `LIMITATIONS.md` — MVP scope and production-hardening notes.
- `samples/demo_suite.yaml` — reviewer-friendly YAML suite definition.
- `samples/01_create_agent_response.json` through `samples/07_regression_evidence.json` — sanitized request/response artifacts generated with FastAPI TestClient and in-memory SQLite.
- `samples/production-smoke-output.json` — live local uvicorn production-smoke verification of health, readiness, API flow, x402, and dashboard.
- `samples/test-output.txt` — current pytest output.

## Acceptance mapping

- Test suite config parsed and executed: YAML/JSON parsing plus assertion execution implemented and tested.
- Live deploy verification: `/healthz` and `/readyz` implemented/tested, Docker Compose health check provided, Render blueprint included, and stdlib smoke test captured in `samples/production-smoke-output.json`.
- Scheduled runs: schedule representation plus `/scheduler/tick` due runner implemented and tested.
- Regression detection: previously passing case failing creates alerts, implemented and tested.
- Detailed reports: `/runs/{run_id}`, output diffs, pass rate, and `/reports/summary` trends.
- Alerts: email, webhook, and dashboard/internal capture implemented; no secrets required.
- Dashboard: `/dashboard` shows suite overview and recent run history.
- Payment integration: x402-compatible plan checkout requirements implemented.
- HTTP/REST targets: endpoint calls use `httpx`; mocks keep local tests deterministic.
