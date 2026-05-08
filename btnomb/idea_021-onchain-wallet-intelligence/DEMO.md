# Reviewer Demo — On-Chain Wallet Intelligence

This demo is designed to be reproducible without private API keys. Live chain polling uses configurable Ethereum/Base JSON-RPC URLs; the included tests and evidence use a deterministic fake RPC client so reviewers can verify the product flow without relying on current block contents.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 for the dashboard.

## Core demo flow

1. Confirm the service seeded 50 watched wallets:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/wallets
```

Expected: `health.wallets` is 50 or greater, and `/api/wallets` includes curated wallet labels, tiers, scores, chain scope, and source metadata.

2. Create an alert subscriber:

```bash
curl -X POST http://localhost:8000/api/subscribers \
  -H 'content-type: application/json' \
  -d '{"email":"alerts@example.com","telegram_chat_id":"123456789","min_score":50}'
```

With SMTP/Telegram credentials set, alerts are sent through those channels. Without credentials, delivery rows are stored with a clear development-outbox status so reviewers can inspect behavior safely.

3. Add a custom Base watchlist wallet:

```bash
curl -X POST http://localhost:8000/api/watchlists \
  -H 'content-type: application/json' \
  -d '{"subscriber_id":1,"address":"0x0000000000000000000000000000000000000003","label":"custom whale","chain":"base"}'
```

4. Poll recent Base/Ethereum blocks:

```bash
curl -X POST 'http://localhost:8000/api/poll?chains=base,ethereum&blocks=2'
```

Expected: response includes `wallets_tracked`, `matched_transactions`, `new_alerts`, `errors`, and `under_60_second_polling_configured`. RPC URLs can be overridden with `BASE_RPC_URL` and `ETHEREUM_RPC_URL`.

5. Inspect parsed alerts and delivery records:

```bash
curl 'http://localhost:8000/api/alerts?min_score=50'
curl http://localhost:8000/api/deliveries
```

Expected alert fields include transaction hash, chain, watched wallet, event type (`transfer`, `swap`, `lp`, `nft`, or `contract`), human-readable summary, AI-style context, likely intent, conviction score, and ETH value.

6. Verify the x402-style paid export gate:

```bash
curl -i http://localhost:8000/api/export
curl http://localhost:8000/api/payments/x402/requirements
curl http://localhost:8000/api/export -H 'X-PAYMENT: demo-receipt'
```

Expected: the first export call returns HTTP 402 with payment requirements; the call with `X-PAYMENT` returns watched wallets and alert data.

## Evidence files

- `evidence/sample_api_flow.json` — deterministic TestClient run covering health, seeded wallets, subscriber creation, custom watchlist, polling, alert parsing, delivery outbox, and x402-gated export.
- `evidence/dashboard-preview.html` — dashboard HTML snapshot after the deterministic demo flow.
- `evidence/pytest-2026-05-08.txt` — latest local test output.
- `evidence/public-url-verification-2026-05-08.txt` — no-auth public URL verification for the submitted GitHub path.

## Limitations / production hardening

- This MVP uses SQLite for speed of review. Production should move to Postgres and add migrations.
- AI context is deterministic scoring/rules rather than an external LLM call, which avoids API keys and makes tests repeatable.
- The export endpoint demonstrates x402-compatible gating semantics by requiring `X-PAYMENT`; production should verify receipts against the chosen x402 facilitator.
- Email and Telegram are implemented, but the public demo intentionally does not include private SMTP or bot credentials.
- Polling is request-driven in the MVP. A production deployment should run `POST /api/poll` from a scheduler or background worker every 45 seconds.
