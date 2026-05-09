# Reviewer Demo — Autonomous QA Agent

Bounty: `idea_025` — Autonomous QA Agent, continuously tests AI agent pipelines against a spec and reports regressions.

This demo shows the submitted FastAPI MVP running locally with in-memory SQLite or a local SQLite file. It does not require private credentials, real wallet keys, external model access, SMTP, or a live x402 facilitator.

## 1. Install and run tests

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-06_btnomb-autonomous-qa-agent/work/autonomous_qa_agent
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=. ./.venv/bin/python -m pytest tests -q
```

Verified on 2026-05-09:

```text
.......                                                                  [100%]
7 passed in 1.03s
```

Captured output is also in `samples/test-output.txt`.

## 2. Start the API

```bash
./.venv/bin/uvicorn app.main:app --reload
```

OpenAPI docs:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

Production liveness/readiness checks added for live deployments:

```bash
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/readyz
```

## 2a. Production smoke verification

The reviewer can run the same verifier against local Docker, local uvicorn, or a hosted Render/Railway/Fly URL:

```bash
AUTONOMOUS_QA_BASE_URL=http://127.0.0.1:8000 python3 scripts/production_smoke_test.py
# or
AUTONOMOUS_QA_BASE_URL=https://your-live-service.example python3 scripts/production_smoke_test.py
```

The verifier checks `/healthz`, `/readyz`, agent registration, YAML suite creation, manual run, schedules, reports, Base USDC x402 checkout, and dashboard HTML. Captured output from 2026-05-09 is in `samples/production-smoke-output.json`.

## 3. End-to-end reviewer flow

Create an agent and save the generated API key:

```bash
curl -sS -X POST http://127.0.0.1:8000/agents \
  -H 'Content-Type: application/json' \
  -d '{"name":"reviewer-demo-agent","plan":"starter"}'
```

Create a YAML-defined QA suite:

```bash
curl -sS -X POST http://127.0.0.1:8000/suites \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "definition": "name: Demo Agent Release QA\nschedule:\n  interval: hourly\nalerts:\n  emails:\n    - qa-owner@example.com\n  webhooks:\n    - capture-only\ndrift_threshold: 0.2\ncases:\n  - id: greeting_contract\n    input: Say hello to a new user\n    expected: hello world\n    mock_response: hello world\n    assertions:\n      - type: exact\n        value: hello world\n  - id: support_ticket_format\n    input: Create a support ticket for a failed payment\n    expected: TICKET-123\n    mock_response: Created support ticket TICKET-123 for failed payment.\n    assertions:\n      - type: regex\n        pattern: 'TICKET-[0-9]+'\n  - id: refund_semantics\n    input: Explain refund policy\n    expected: Refunds are processed within five business days\n    mock_response: Refunds are usually handled in five business days.\n    assertions:\n      - type: similarity\n        value: Refunds are processed within five business days\n        threshold: 0.25\n"
}
JSON
```

Run the suite manually:

```bash
curl -sS -X POST http://127.0.0.1:8000/suites/$SUITE_ID/run \
  -H "X-API-Key: $API_KEY"
```

Expected result includes:

```json
{
  "status": "passed",
  "total": 3,
  "passed": 3,
  "failed": 0,
  "pass_rate": 1.0
}
```

Check schedule state and trigger due scheduled runs:

```bash
curl -sS http://127.0.0.1:8000/schedules -H "X-API-Key: $API_KEY"
curl -sS -X POST http://127.0.0.1:8000/scheduler/tick -H "X-API-Key: $API_KEY"
```

Trigger the same checks from a CI/CD deploy hook:

```bash
curl -sS -X POST http://127.0.0.1:8000/webhooks/deploy/$SUITE_ID \
  -H "X-API-Key: $API_KEY"
```

Open the dashboard from a browser or scripted test:

```text
GET /dashboard with X-API-Key header
```

Request paid-plan x402-style payment requirements:

```bash
curl -i -X POST http://127.0.0.1:8000/plans/checkout \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"plan":"pro"}'
```

Expected result: HTTP 402 with Base USDC x402 requirement fields, including `x402Version`, `accepts`, `network: base`, and `asset: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`.

## 4. Regression evidence

The app stores prior case outcomes, then creates alerts when a previously passing case fails. See `samples/07_regression_evidence.json` for an in-memory TestClient run where:

- first run status is `passed`;
- second run status is `failed`;
- `regression_count` is `1`;
- the result includes a unified diff;
- `/alerts` includes a captured dashboard/email alert record.

## 5. Sample artifacts

Generated from the app with `FastAPI TestClient` and `sqlite:///:memory:`:

- `samples/demo_suite.yaml` — reviewer-friendly suite definition.
- `samples/01_create_agent_response.json` — redacted agent/API-key creation response.
- `samples/02_create_suite_response.json` — normalized suite response.
- `samples/03_manual_run_response.json` — passing run with per-case assertion evidence.
- `samples/04_schedules_response.json` — schedule/due status.
- `samples/05_summary_response.json` — report summary/trend response.
- `samples/06_x402_checkout_response.json` — x402-style 402 payment requirements for the pro plan.
- `samples/07_regression_evidence.json` — failure/regression/alert evidence.
- `samples/production-smoke-output.json` — production smoke output from a live local uvicorn deployment.
- `samples/test-output.txt` — current pytest output.

## 6. Why this meets the bounty

The deliverable is a working autonomous QA service: users register agents, define YAML/JSON QA suites, run them manually, trigger them from deploy hooks, schedule recurring checks, compare actual outputs against exact/contains/regex/similarity assertions, persist run history, detect regressions and semantic drift, capture alerts, view an HTML dashboard, and expose x402-style paid-plan checkout requirements.