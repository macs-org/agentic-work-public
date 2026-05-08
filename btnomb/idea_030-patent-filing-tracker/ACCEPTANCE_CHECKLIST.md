# Acceptance Checklist — idea_030 Patent Filing Tracker

Public submission URL: https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_030-patent-filing-tracker

## Bounty requirement mapping

- [x] Live connection to at least USPTO PatentsView API
  - `PatentsViewClient.search()` calls `PATENTSVIEW_API_BASE`, defaulting to `https://search.patentsview.org/api/v1/patent/`.
  - The client sends PatentsView query parameters, requests patent fields, uses `AgenticWorkPatentTracker/1.0` as the User-Agent, enforces JSON responses, and normalizes multiple response shapes.
  - Evidence: `tests/test_patent_tracker.py::test_patentsview_response_normalization` and `samples/01_health_response.json`.

- [x] Watchlist configuration working by company and keyword
  - `POST /api/watchlists` accepts `kind: company` and `kind: keyword` with optional `email` and `webhook_url` destinations.
  - Evidence: `samples/02_company_watchlist_response.json` and `samples/03_keyword_watchlist_response.json`.

- [x] AI summary generated per filing
  - `summarize_filing()` produces a compact filing summary, technology category, and strategic implication for every stored filing.
  - `POST /api/poll` stores summary and strategic implication fields alongside each filing.
  - Evidence: `samples/05_filings_search_response.json` and `tests/test_patent_tracker.py::test_company_watchlist_poll_summary_and_email_outbox`.

- [x] Email alert delivery functional
  - `deliver_email()` sends via SMTP when `SMTP_HOST` is configured.
  - Without SMTP credentials, it records a development outbox alert so reviewers can verify the full alert path without secrets.
  - Evidence: `samples/06_alerts_response.json` includes a stored email alert; tests verify the email alert path.

- [x] Webhook alerts available for Pro-style subscribers
  - Watchlists accept `webhook_url`; `deliver_webhook()` posts the alert payload and records success/failure without aborting the poll.
  - Evidence: `samples/06_alerts_response.json` includes a deterministic webhook alert record from the sample generator.

- [x] Dashboard with recent filings live
  - `GET /` renders recent filings, active watchlists, a filter form, strategic implications, trend rows, and payment copy.
  - Evidence: `samples/11_dashboard_snippet.html` and `tests/test_patent_tracker.py::test_keyword_watchlist_dashboard_and_trends`.

- [x] Trend charts: filing volume by company/category over time
  - `PatentStore.trends()` groups filings by assignee, CPC category, and month.
  - `GET /api/trends` exposes the trend rows for dashboard/API use.
  - Evidence: `samples/07_trends_response.json`.

- [x] x402 payment integration
  - `GET /api/payments/x402/requirements` returns Base/USDC payment requirements.
  - `GET /api/export` returns HTTP 402 unless `X-PAYMENT` or a paid plan header is present.
  - Evidence: `samples/08_x402_payment_requirements.json`, `samples/09_export_payment_required_response.json`, `samples/10_export_paid_response.json`, and `tests/test_patent_tracker.py::test_x402_payment_gate`.

- [x] Deployable Python backend package
  - Package includes `README.md`, `DEMO.md`, `ACCEPTANCE_CHECKLIST.md`, `LIMITATIONS.md`, `Dockerfile`, `requirements.txt`, `app/main.py`, tests, deterministic sample artifacts, and a sample-generation script.
  - FastAPI exposes `/docs` and `/openapi.json` for reviewer exploration.

## Current verification

Command:

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-08_btnomb-patent-filing-tracker/work/patent_filing_tracker
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest tests -q -p no:cacheprovider
```

Result on 2026-05-08 UTC:

```text
....                                                                     [100%]
4 passed in 0.93s
```

Additional command:

```bash
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python scripts/generate_samples.py
```

Result: deterministic reviewer evidence refreshed under `samples/`.

## Guardrails

- [x] No project wallet private key, API token, internal ledger, or internal state file included.
- [x] No external credentials required for tests or deterministic demo evidence.
- [x] No live SMTP credentials required; SMTP-less email path records a development outbox delivery.
- [x] No live x402 facilitator required for local review; the app exposes payment requirements and enforces a payment header gate.
- [x] No new BTNOMB submission URL was sent during this acceptance upgrade.
- [x] No funds were spent during this acceptance upgrade.
- [x] This remains a pending BTNOMB submission until accepted/paid; it is not counted as realized earnings.
