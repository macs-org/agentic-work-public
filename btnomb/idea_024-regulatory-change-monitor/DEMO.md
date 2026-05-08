# Regulatory Change Monitor demo

Reviewer target: BTNOMB idea_024, public submission URL `https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_024-regulatory-change-monitor`.

This demo uses deterministic in-process FastAPI requests so reviewers can verify the core product without configuring SMTP, a scheduler, or external regulatory APIs. The production source adapter still calls the Federal Register API for SEC, FDA, FCC, and CFTC documents.

## Quick verification

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt pytest
pytest tests -q
```

Latest local acceptance-upgrade run, captured 2026-05-08T15:29:42Z:

```text
....                                                                     [100%]
4 passed in 0.60s
```

Raw captured output is in `demo/test-output.txt`.

## End-to-end sample flow

The sample evidence in `demo/sample-responses.json` exercises this flow:

1. `GET /health` returns configured source coverage: SEC, FDA, FCC, CFTC.
2. `POST /api/subscribers` creates a compliance subscriber with agency/topic/industry preferences.
3. `POST /api/poll?limit_per_source=1` ingests one mocked regulatory document from each of the four source agents.
4. The poll response reports `documents_seen: 4`, `new_alerts: 4`, and `summaries_generated_immediately: true`.
5. `GET /api/alerts?q=crypto&agency=SEC` proves searchable archive filtering.
6. `GET /api/deliveries` proves alert delivery records; when `SMTP_HOST` is unset, delivery is safely stored in the development outbox instead of failing.
7. `GET /api/trends` proves dashboard trend aggregation.
8. `GET /api/payments/x402/requirements` returns Base/USDC x402 requirements.
9. `GET /api/export` returns HTTP 402 without `X-PAYMENT`; the same endpoint returns the export payload with a demo `X-PAYMENT` header.
10. `GET /?agency=SEC&q=crypto` renders the reviewer dashboard. A captured HTML page is in `demo/dashboard-excerpt.html`.

## Manual API walkthrough

Start the service:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Create a subscriber:

```bash
curl -sS -X POST http://localhost:8000/api/subscribers \
  -H 'content-type: application/json' \
  -d '{"email":"compliance@example.test","agencies":["SEC","FDA"],"topics":["crypto","AI"],"industries":["fintech","AI/software"]}'
```

Poll live sources:

```bash
curl -sS -X POST 'http://localhost:8000/api/poll?limit_per_source=3'
```

Search the archive:

```bash
curl -sS 'http://localhost:8000/api/alerts?q=crypto&agency=SEC'
```

Verify payment-gated export:

```bash
curl -i http://localhost:8000/api/export
curl -sS http://localhost:8000/api/export -H 'X-PAYMENT: demo-receipt'
```

Open the dashboard at `http://localhost:8000/?agency=SEC&q=crypto`.

## Evidence files

- `demo/test-output.txt` — pytest output from the acceptance-upgrade run.
- `demo/sample-responses.json` — full request/response evidence for health, subscriber creation, polling, archive search, deliveries, trends, payment requirements, 402 gating, paid export, and scheduler status.
- `demo/dashboard-excerpt.html` — rendered dashboard HTML for the sample SEC crypto filter.
