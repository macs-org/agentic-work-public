# Regulatory Change Monitor

Autonomous regulatory change monitoring SaaS MVP for BTNOMB idea_024.

It polls four live regulatory sources, summarizes new rules/guidance/enforcement actions, scores impact, lets subscribers set alert preferences, sends email/webhook alerts, and exposes a dashboard plus searchable archive.

## Acceptance criteria coverage

- **Live scraping of 4 regulatory sources:** SEC, FDA, FCC, and CFTC source agents query the Federal Register public API by agency. Source base URL is configurable with `FEDERAL_REGISTER_API`.
- **AI summaries within 5 minutes:** every newly ingested document is summarized synchronously during polling; default poll interval is `POLL_INTERVAL_SECONDS=900` and can be set to `300` for five-minute monitoring.
- **Subscriber signup + alert delivery:** `POST /api/subscribers` records agency/topic/industry preferences. SMTP email delivery works when `SMTP_HOST` is set; otherwise alerts are stored as dev outbox records. Webhooks are delivered with POST.
- **Dashboard:** `GET /` shows recent alerts with filters for agency/topic/industry.
- **Searchable archive:** `GET /api/alerts?q=...` searches title, summary, agency, topics, and industries.
- **Payment integration:** `GET /api/payments/x402/requirements` returns Base/USDC x402 requirements; `GET /api/export` is gated by `X-PAYMENT` or paid plan header.

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
docker build -t regulatory-change-monitor .
docker run -p 8000:8000 -v regulatory-data:/data regulatory-change-monitor
```

## API examples

Create subscriber:

```bash
curl -X POST http://localhost:8000/api/subscribers   -H 'content-type: application/json'   -d '{"email":"alerts@example.com","agencies":["SEC","FDA"],"topics":["AI","crypto"],"industries":["fintech","healthcare"]}'
```

Poll all configured sources:

```bash
curl -X POST 'http://localhost:8000/api/poll?limit_per_source=5'
```

Search archive:

```bash
curl 'http://localhost:8000/api/alerts?q=crypto&agency=SEC'
```

Payment-gated export:

```bash
curl http://localhost:8000/api/export -H 'X-PAYMENT: demo-receipt'
```

## Environment

- `REG_MONITOR_DB`: SQLite path, default `/tmp/regulatory_change_monitor.db`
- `POLL_INTERVAL_SECONDS`: default `900`, set `300` for 5-minute polling
- `FEDERAL_REGISTER_API`: default `https://www.federalregister.gov/api/v1/documents.json`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`: optional SMTP settings
- `X402_PAY_TO`: wallet receiving x402 payments

## Reviewer evidence

- `DEMO.md` gives a quick verification path and manual API walkthrough.
- `ACCEPTANCE_CHECKLIST.md` maps the implementation to every BTNOMB acceptance criterion.
- `LIMITATIONS.md` documents MVP constraints and production hardening steps.
- `demo/test-output.txt` captures the latest pytest run.
- `demo/sample-responses.json` contains end-to-end sample request/response evidence.
- `demo/dashboard-excerpt.html` contains a rendered dashboard sample.

## Tests

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt pytest
pytest tests -q
```

Latest acceptance-upgrade run: `4 passed in 0.60s`.
