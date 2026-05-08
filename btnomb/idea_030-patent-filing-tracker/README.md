# Patent Filing Tracker

Autonomous patent filing tracker SaaS MVP for BTNOMB idea_030.

It monitors USPTO PatentsView for new filings/publications/grants, lets subscribers create company/keyword watchlists, summarizes matching filings, sends email/webhook alerts, and exposes a live dashboard with trends and payment-gated exports.

## Acceptance criteria coverage

- **Live USPTO PatentsView connection:** `PatentsViewClient` queries `PATENTSVIEW_API_BASE` (default `https://search.patentsview.org/api/v1/patent/`) and normalizes multiple PatentsView response shapes.
- **Watchlist configuration:** `POST /api/watchlists` supports `company` and `keyword` entries.
- **AI summary per filing:** every filing is summarized with `summarize_filing`; optional external LLM can be added later without changing the API contract.
- **Email alerts functional:** SMTP delivery works when `SMTP_HOST` is set; otherwise alerts are persisted in a dev outbox so the flow is testable without credentials. Webhook delivery is also implemented.
- **Dashboard:** `GET /` renders recent filings, watchlists, filters, and trend summary.
- **x402 payment integration:** `GET /api/payments/x402/requirements` exposes payment requirements; `GET /api/export` is payment-gated by `X-PAYMENT` or `X-Plan: enterprise`.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000.

## Docker

```bash
docker build -t patent-filing-tracker .
docker run -p 8000:8000 -v patent-data:/data patent-filing-tracker
```

## Example API usage

Create a company watchlist:

```bash
curl -X POST http://localhost:8000/api/watchlists   -H 'content-type: application/json'   -d '{"kind":"company","value":"OpenAI","email":"alerts@example.com"}'
```

Create a keyword watchlist:

```bash
curl -X POST http://localhost:8000/api/watchlists   -H 'content-type: application/json'   -d '{"kind":"keyword","value":"agentic AI","webhook_url":"https://example.com/patents"}'
```

Poll PatentsView:

```bash
curl -X POST http://localhost:8000/api/poll
```

View recent filings:

```bash
curl http://localhost:8000/api/filings
```

Payment-gated export:

```bash
curl http://localhost:8000/api/export -H 'X-PAYMENT: demo-paid-receipt'
```

## Environment

- `PATENT_TRACKER_DB`: SQLite path, default `/tmp/patent_tracker.db`
- `PATENTSVIEW_API_BASE`: PatentsView endpoint, default `https://search.patentsview.org/api/v1/patent/`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`: optional SMTP settings
- `X402_PAY_TO`: wallet receiving x402 payments, default Agentic Work wallet

## Tests

```bash
pytest tests -q
```
