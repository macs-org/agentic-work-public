# Freight Rate Anomaly Detector

Autonomous SaaS MVP for BTNOMB `idea_019`: monitors public freight/transportation rate indices, flags anomalous moves against recent baselines, generates reviewer-readable context, and exposes dashboard/API/alert/payment flows.

## What it does

- Polls live public CSV feeds from FRED/BLS/BTS for truckload, intermodal rail, air transportation, and broad freight transportation pressure.
- Stores rate history in SQLite with a Postgres-ready schema.
- Computes tunable anomaly signals versus 7/30/seasonal-style recent baselines.
- Generates context and conviction scores for each alert.
- Serves a no-auth dashboard with Chart.js cards and anomaly history.
- Supports subscriber configs, email delivery via SMTP or local outbox fallback, webhook delivery, and an x402-gated export endpoint.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000`.

## API examples

```bash
curl -X POST http://127.0.0.1:8000/poll
curl 'http://127.0.0.1:8000/anomalies?threshold_pct=2&baseline_window=7'
curl -X POST http://127.0.0.1:8000/alerts/dispatch   -H 'content-type: application/json'   -d '{"email":"ops@example.com","threshold_pct":2,"baseline_window":7,"modes":["truck","rail","air"]}'
curl http://127.0.0.1:8000/api/export -H 'X-PAYMENT: demo-paid-token'
```

## Payment model

The app exposes the requested pricing tiers:

- Starter: $99/mo — 3 freight modes, email alerts, daily refresh
- Pro: $299/mo — all modes, real-time push, webhooks + API access
- Institutional: $999/mo — raw export, custom thresholds, unlimited seats

`GET /api/export` returns HTTP 402 without `X-PAYMENT` and returns raw data with a payment token, matching the intended x402-gated API shape.

## Environment

Optional:

- `FREIGHT_DB_PATH=/tmp/freight_rate_anomaly_detector.sqlite`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` for real email delivery
- `PAYMENT_ADDRESS` for x402 payment metadata

Without SMTP config, alert delivery writes a local `.eml` file so reviewers can verify the email workflow safely.
