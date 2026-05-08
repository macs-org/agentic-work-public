# Reviewer Demo — Job Board Intelligence

Bounty: `idea_027` — Job Board Intelligence, track hiring trends to detect company pivots, scale-ups, and cuts.

This demo shows the submitted FastAPI MVP running locally with SQLite. It does not require private credentials, real email credentials, wallet keys, or a live x402 facilitator. The Greenhouse/Lever clients can poll public job-board APIs; the included reviewer samples use deterministic in-process fixtures so the evidence is repeatable without network access.

## 1. Install and run tests

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-08_btnomb-job-board-intelligence/work/job_board_intelligence
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest tests -q -p no:cacheprovider
```

Verified on 2026-05-08:

```text
....                                                                     [100%]
4 passed in 0.85s
```

Captured output is also in `samples/test-output.txt`.

## 2. Start the API

```bash
JOB_INTEL_DB=job_board_intelligence.db ./.venv/bin/uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
http://127.0.0.1:8000/health
```

## 3. End-to-end reviewer flow

List the seeded company universe. The app seeds 50 tracked companies across Greenhouse, Lever, and public-company metadata entries:

```bash
curl -sS http://127.0.0.1:8000/api/companies
```

Create a subscriber interested in hiring moves at OpenAI and Stripe (you can also add department/tech filters for narrower alerts):

```bash
curl -sS -X POST http://127.0.0.1:8000/api/subscribers \
  -H 'Content-Type: application/json' \
  -d '{"email":"reviewer@example.com","companies":["OpenAI","Stripe"],"departments":[],"tech_stacks":[],"real_time":true}'
```

Poll up to 50 tracked companies. Greenhouse and Lever sources use public APIs; public metadata entries are tracked and extension-ready for robots-aware per-domain scraping:

```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/poll?limit_companies=50'
```

Search the ingested active jobs and trend signals:

```bash
curl -sS 'http://127.0.0.1:8000/api/jobs?department=engineering&tech=python'
curl -sS 'http://127.0.0.1:8000/api/signals?company=OpenAI'
curl -sS 'http://127.0.0.1:8000/api/deliveries'
```

Generate a weekly digest for subscribers:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/digest/send
```

## 4. Dashboard

Use the dashboard filters to review hiring signals and role rows:

```text
http://127.0.0.1:8000/?company=OpenAI&department=engineering
```

Sample dashboard HTML is captured in `samples/12_dashboard_snippet.html`.

## 5. x402-style paid export surface

Inspect the payment requirements:

```bash
curl -sS http://127.0.0.1:8000/api/payments/x402/requirements
```

The export endpoint is payment-gated. Without `X-PAYMENT` it returns HTTP 402 with Base/USDC requirements; with a demo receipt header it returns export data:

```bash
curl -i http://127.0.0.1:8000/api/export
curl -sS http://127.0.0.1:8000/api/export -H 'X-PAYMENT: demo-reviewer-receipt'
```

Evidence is captured in `samples/09_x402_payment_requirements.json`, `samples/10_export_payment_required_response.json`, and `samples/11_export_paid_summary.json`.

## 6. Deterministic sample artifacts

Generated with `scripts/generate_samples.py` using FastAPI `TestClient`, a temporary SQLite database, and deterministic job fixtures:

- `samples/00_evidence_summary.json` — generated evidence summary and key checks.
- `samples/01_health_response.json` — health endpoint with tracked-company count.
- `samples/02_companies_sample_response.json` — seeded company count and sample rows.
- `samples/03_subscriber_response.json` — subscriber creation response.
- `samples/04_poll_response.json` — poll result showing tracked companies, new jobs, signals, and errors.
- `samples/05_jobs_filter_response.json` — engineering + Python role search evidence.
- `samples/06_signals_response.json` — baseline/new-role trend signals.
- `samples/07_deliveries_response.json` — realtime alert delivery records stored in development outbox.
- `samples/08_weekly_digest_response.json` — weekly digest run output.
- `samples/09_x402_payment_requirements.json` — Base/USDC payment requirement response.
- `samples/10_export_payment_required_response.json` — HTTP 402 payment-required response.
- `samples/11_export_paid_summary.json` — paid export summary with sample jobs/signals.
- `samples/12_dashboard_snippet.html` — reviewer dashboard HTML snippet.
- `samples/test-output.txt` — current pytest output.

Regenerate samples:

```bash
python3 scripts/generate_samples.py
```

## 7. Why this meets the bounty

The deliverable is a working job-board intelligence service: it tracks 50 companies, polls public Greenhouse and Lever APIs, tags roles by department/seniority/tech/location, stores snapshots, detects spikes/drops/new departments/new role expansion, sends realtime email/webhook-style alerts with a testable development outbox, provides a filterable dashboard and API, generates weekly digests, and exposes a Base/USDC x402-style payment-gated export endpoint.