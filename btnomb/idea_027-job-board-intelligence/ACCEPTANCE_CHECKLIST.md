# Acceptance Checklist — idea_027 Job Board Intelligence

Public submission URL: https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_027-job-board-intelligence

## Bounty requirement mapping

- [x] Track hiring trends to detect company pivots, scale-ups, and cuts
  - `Store.snapshot_and_detect()` stores every company snapshot and emits baseline, spike, drop, new-role, and new-department signals.
  - Evidence: `samples/04_poll_response.json` and `samples/06_signals_response.json`.

- [x] Live tracking of 50+ companies
  - `SEED_COMPANIES` contains 50 tracked companies across Greenhouse, Lever, and public metadata entries.
  - `GET /api/companies` returns the active universe.
  - Evidence: `samples/02_companies_sample_response.json` shows `count: 50`.

- [x] Public job-board API ingestion
  - `JobBoardClient.fetch_greenhouse()` calls the public Greenhouse board API.
  - `JobBoardClient.fetch_lever()` calls the public Lever postings API.
  - Per-company polling continues even if one source errors, returning per-company errors in the poll response instead of aborting the batch.

- [x] Role tagging and intelligence fields
  - `tag_role()` classifies department, seniority, and tech stack from title/location text.
  - `GET /api/jobs` supports filters for company, department, tech, seniority, and limit.
  - Evidence: `samples/05_jobs_filter_response.json` contains engineering/Python matches.

- [x] Persistent snapshots, active-role store, and cuts/drops
  - SQLite tables cover companies, jobs, snapshots, signals, subscribers, and deliveries.
  - `upsert_jobs_for_company()` marks missing previously active jobs inactive, enabling drop/cut detection.
  - Evidence: `tests/test_job_board_intelligence.py::test_trend_drop_detection` verifies sudden job removal signals.

- [x] Filterable reviewer dashboard
  - `GET /` renders a simple HTML dashboard with company/department/tech/seniority filters, trend signals, active role rows, and payment copy.
  - Evidence: `samples/12_dashboard_snippet.html`.

- [x] Realtime email and webhook alert flow
  - Subscriber preferences cover email, webhook URL, companies, departments, tech stacks, and realtime toggle.
  - `send_email()` uses SMTP when configured and falls back to a persisted development outbox when `SMTP_HOST` is absent.
  - `send_webhook()` posts signal payloads to subscriber webhook URLs and records success/failure.
  - Evidence: `samples/07_deliveries_response.json` shows stored delivery records; tests verify alert creation.

- [x] Weekly digest flow
  - `POST /api/digest/send` matches recent signals to subscriber preferences and records weekly email deliveries.
  - Evidence: `samples/08_weekly_digest_response.json`.

- [x] x402-compatible paid export surface
  - `GET /api/payments/x402/requirements` returns Base/USDC payment requirements.
  - `GET /api/export` returns HTTP 402 unless `X-PAYMENT` or a paid plan header is present.
  - Evidence: `samples/09_x402_payment_requirements.json`, `samples/10_export_payment_required_response.json`, and `samples/11_export_paid_summary.json`.

- [x] Deployable package
  - Package includes `README.md`, `DEMO.md`, `ACCEPTANCE_CHECKLIST.md`, `LIMITATIONS.md`, `Dockerfile`, `requirements.txt`, `app/main.py`, tests, sample artifacts, and a sample-generation script.
  - FastAPI exposes `/docs` and `/openapi.json` for reviewer exploration.

## Current verification

Command:

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-08_btnomb-job-board-intelligence/work/job_board_intelligence
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests -q -p no:cacheprovider
```

Result on 2026-05-08:

```text
....                                                                     [100%]
4 passed in 0.85s
```

Additional command:

```bash
python3 scripts/generate_samples.py
```

Result: deterministic reviewer evidence refreshed under `samples/`.

## Guardrails

- [x] No project wallet private key, API token, internal ledger, or internal state file included.
- [x] No external credentials required for tests or deterministic demo evidence.
- [x] No live SMTP credentials required; SMTP-less email path records a development outbox delivery.
- [x] No new BTNOMB URL submitted during this acceptance upgrade.
- [x] No funds spent during this acceptance upgrade.
- [x] This remains a pending BTNOMB submission until accepted/paid; it is not counted as realized earnings.