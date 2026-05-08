# Reviewer Demo — Patent Filing Tracker

Bounty: `idea_030` — Patent Filing Tracker, monitor USPTO and EPO filings to surface competitive intelligence signals.

This demo shows the submitted FastAPI MVP running locally with SQLite. It does not require private credentials, SMTP credentials, wallet keys, or a live x402 facilitator. The live integration is the USPTO PatentsView client required by the acceptance criteria; the reviewer samples use deterministic in-process fixtures so the evidence is repeatable without network access.

## 1. Install and run tests

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-08_btnomb-patent-filing-tracker/work/patent_filing_tracker
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest tests -q -p no:cacheprovider
```

Verified on 2026-05-08 UTC:

```text
....                                                                     [100%]
4 passed in 0.93s
```

Captured output is also in `samples/test-output.txt`.

## 2. Start the API

```bash
PATENT_TRACKER_DB=patent_tracker.db ./.venv/bin/uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
http://127.0.0.1:8000/health
```

## 3. End-to-end reviewer flow

Create a company watchlist with email alerts:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/watchlists \
  -H 'Content-Type: application/json' \
  -d '{"kind":"company","value":"OpenAI","email":"reviewer@example.com"}'
```

Create a keyword watchlist with webhook alerts:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/watchlists \
  -H 'Content-Type: application/json' \
  -d '{"kind":"keyword","value":"agentic AI","webhook_url":"https://example.com/patent-alerts"}'
```

Poll USPTO PatentsView for each active watchlist. The production path calls `PATENTSVIEW_API_BASE` (default `https://search.patentsview.org/api/v1/patent/`) with a non-empty User-Agent and normalizes multiple response shapes.

```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/poll?per_watchlist=5'
```

Review filings, alerts, and trend data:

```bash
curl -sS 'http://127.0.0.1:8000/api/filings?q=agentic'
curl -sS http://127.0.0.1:8000/api/alerts
curl -sS http://127.0.0.1:8000/api/trends
```

## 4. Dashboard

Use the dashboard to inspect active watchlists, recent filings, summaries, strategic implications, and trend rows:

```text
http://127.0.0.1:8000/?q=agentic
```

Sample dashboard HTML is captured in `samples/11_dashboard_snippet.html`.

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

Evidence is captured in `samples/08_x402_payment_requirements.json`, `samples/09_export_payment_required_response.json`, and `samples/10_export_paid_response.json`.

## 6. Deterministic sample artifacts

Generated with `scripts/generate_samples.py` using FastAPI `TestClient`, a temporary SQLite database, deterministic PatentsView fixtures, stored email fallback, and a deterministic webhook stub:

- `samples/00_evidence_summary.json` — generated evidence summary and key checks.
- `samples/01_health_response.json` — health endpoint response.
- `samples/02_company_watchlist_response.json` — company watchlist creation response.
- `samples/03_keyword_watchlist_response.json` — keyword watchlist creation response.
- `samples/04_poll_response.json` — poll result showing matched and newly stored filings.
- `samples/05_filings_search_response.json` — search response with summaries and strategic implications.
- `samples/06_alerts_response.json` — email and webhook alert delivery records.
- `samples/07_trends_response.json` — filing volume trend rows by assignee/category/month.
- `samples/08_x402_payment_requirements.json` — Base/USDC payment requirement response.
- `samples/09_export_payment_required_response.json` — HTTP 402 payment-required response.
- `samples/10_export_paid_response.json` — paid export data.
- `samples/11_dashboard_snippet.html` — reviewer dashboard HTML snippet.
- `samples/test-output.txt` — current pytest output.

Regenerate samples:

```bash
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python scripts/generate_samples.py
```

## 7. Why this meets the bounty

The deliverable is a working patent-filing intelligence service: it stores company and keyword watchlists, polls the live USPTO PatentsView API path, normalizes patent rows, generates an AI-style title/abstract summary plus technology category and strategic implication, persists recent filings, records email and webhook alerts, renders a dashboard with filtering and trend data, and exposes a Base/USDC x402-style payment-gated export endpoint.
