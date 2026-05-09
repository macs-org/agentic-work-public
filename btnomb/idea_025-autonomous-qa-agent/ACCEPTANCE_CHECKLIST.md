# Acceptance Checklist — idea_025 Autonomous QA Agent

Public submission URL: https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_025-autonomous-qa-agent

## Bounty requirement mapping

- [x] Autonomous QA agent service
  - FastAPI app in `app/main.py` exposes agent registration, suite management, manual runs, deploy webhook runs, scheduler ticks, reports, alerts, dashboard, and plan checkout.
  - Tests: `tests/test_autonomous_qa_agent.py` covers agent creation, protected endpoints, suite runs, scheduler, deploy webhook, reports, dashboard, and checkout.

- [x] Continuously tests AI agent pipelines against a spec
  - Suite definitions support YAML strings or JSON objects via `load_config()` / `normalize_definition()`.
  - Specs include suite name, endpoint/method, interval, alert channels, drift threshold, and cases.
  - Cases support prompt/input, expected output, endpoint override, payload/headers/method override, deterministic mocks for demos/tests, and assertion lists.

- [x] Multiple assertion types
  - `exact`, `contains`, `regex`, and `similarity` assertions are implemented in `evaluate_assertions()`.
  - `samples/03_manual_run_response.json` shows all demo cases passing with per-case assertion evidence.

- [x] Manual and scheduled execution
  - Manual: `POST /suites/{suite_id}/run`.
  - Scheduled representation: `GET /schedules`.
  - Scheduler tick: `POST /scheduler/tick` runs due suites.
  - CI/CD deploy hook: `POST /webhooks/deploy/{suite_id}`.
  - Tests: `test_scheduler_tick_runs_due_suite_and_schedule_endpoint_represents_history()` and `test_dashboard_reports_deploy_webhook_and_x402_plan_checkout()`.

- [x] Regression and drift reporting
  - Previously passing cases that fail create `regression` alerts and include a unified diff.
  - Similarity-score drops beyond `drift_threshold` create `drift` alerts.
  - Tests: `test_regression_detection_creates_dashboard_alert_when_previously_passing_case_fails()` and `test_drift_detection_alerts_when_semantic_similarity_drops()`.
  - Evidence: `samples/07_regression_evidence.json`.

- [x] Run history and detailed reports
  - SQLAlchemy models persist agents, suites, runs, case results, and alerts.
  - Endpoints: `GET /runs`, `GET /runs/{run_id}`, and `GET /reports/summary`.
  - Evidence: `samples/03_manual_run_response.json` and `samples/05_summary_response.json`.

- [x] Alerting
  - Dashboard/internal alerts are captured in the database.
  - Email alerts use SMTP environment variables when configured; otherwise they are safely captured as `captured:no_smtp_configured`.
  - Webhook alerts post to HTTP(S) endpoints when configured; non-HTTP demo targets are captured as `captured:non_http_webhook`.

- [x] Reviewer-visible dashboard
  - `GET /dashboard` renders suite/run/alert overview HTML.
  - Test verifies the dashboard includes expected title and suite names.

- [x] API security
  - Protected endpoints require `X-API-Key`.
  - Test: `test_api_key_auth_required_for_protected_endpoints()`.

- [x] x402-compatible paid plan surface
  - `POST /plans/checkout` returns HTTP 402 with x402-style Base USDC payment requirements.
  - Evidence: `samples/06_x402_checkout_response.json`.

- [x] Deployment package
  - `Dockerfile`, `docker-compose.yml`, `render.yaml`, `.env.example`, `requirements.txt`, `README.md`, tests, and reviewer evidence are included.
  - No secrets are committed; sample API keys are redacted or generated in-memory.

- [x] Live deployment and production verification evidence
  - `GET /healthz` returns liveness metadata for hosted load balancers and uptime checks.
  - `GET /readyz` verifies database readiness with a SQL probe.
  - `docker-compose.yml` includes a `/readyz` health check and persistent data volume.
  - `render.yaml` includes hosted blueprint metadata with `/readyz` health check path.
  - `scripts/production_smoke_test.py` verifies a live URL end-to-end using only Python stdlib.
  - Evidence: `samples/production-smoke-output.json` captured from a live local uvicorn process.

## Current verification

Command:

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-06_btnomb-autonomous-qa-agent/work/autonomous_qa_agent
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests -q -p no:cacheprovider
AUTONOMOUS_QA_BASE_URL=http://127.0.0.1:8015 python3 scripts/production_smoke_test.py
```

Result on 2026-05-09:

```text
.......                                                                  [100%]
7 passed in 1.03s
```

Smoke test result: `samples/production-smoke-output.json` has `ok: true` with 9/9 checks passing against a live local uvicorn process.

## Guardrails

- [x] No project wallet private key or internal ledger/state file included.
- [x] No external model/API credentials required for tests or demo.
- [x] No new BTNOMB URL submitted during this acceptance upgrade.
- [x] No new funds spent during this acceptance upgrade.
- [x] This remains a pending submission until BTNOMB accepts/pays; it is not counted as realized earnings.