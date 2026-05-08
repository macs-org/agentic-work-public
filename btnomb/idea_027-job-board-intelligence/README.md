# Job Board Intelligence

Autonomous hiring-trend intelligence SaaS MVP for BTNOMB idea_027.

It tracks company career pages/job board APIs, tags roles, stores snapshots, detects hiring spikes/drops/new department signals, sends alerts/digests, and exposes a searchable dashboard plus payment-gated API export.

## Acceptance criteria coverage

- **Live tracking of 50+ companies:** app seeds 50 tracked companies across Greenhouse, Lever, and public career page metadata; Greenhouse and Lever use public APIs.
- **Trend detection:** polling stores snapshots and detects volume spikes, sudden drops, new departments, and tech-stack pivots.
- **Dashboard:** `GET /` renders company/department/seniority/location/tech filters and signal cards.
- **Email alerts:** SMTP delivery works when `SMTP_HOST` is set; otherwise alerts are stored in the dev outbox so the workflow is testable. Webhook delivery is also implemented.
- **x402 payment integration:** `GET /api/payments/x402/requirements` returns Base/USDC requirements; `GET /api/export` is gated by `X-PAYMENT` or paid plan header.

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
docker build -t job-board-intelligence .
docker run -p 8000:8000 -v job-intel-data:/data job-board-intelligence
```

## API examples

Seed/list tracked companies:

```bash
curl http://localhost:8000/api/companies
```

Create subscriber:

```bash
curl -X POST http://localhost:8000/api/subscribers   -H 'content-type: application/json'   -d '{"email":"alerts@example.com","companies":["OpenAI","Stripe"],"departments":["engineering"],"real_time":true}'
```

Poll public job board APIs:

```bash
curl -X POST 'http://localhost:8000/api/poll?limit_companies=50'
```

Search roles/signals:

```bash
curl 'http://localhost:8000/api/jobs?department=engineering&tech=python'
curl 'http://localhost:8000/api/signals?kind=spike'
```

Payment-gated export:

```bash
curl http://localhost:8000/api/export -H 'X-PAYMENT: demo-receipt'
```

## Environment

- `JOB_INTEL_DB`: SQLite path, default `/tmp/job_board_intelligence.db`
- `POLL_INTERVAL_SECONDS`: cron interval metadata, default `3600`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`: optional email delivery settings
- `X402_PAY_TO`: wallet receiving x402 payments

## Tests

```bash
pytest tests -q
```
