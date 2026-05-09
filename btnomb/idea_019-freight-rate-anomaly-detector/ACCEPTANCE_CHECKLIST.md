# Acceptance checklist — BTNOMB idea_019

- Live data from at least 2 freight rate sources: implemented via four public FRED/BLS/BTS CSV series (`truckload_ppi`, `intermodal_rail_ppi`, `air_transport_ppi`, `freight_tsi`).
- Anomaly detection algorithm working and tunable: `GET /anomalies?threshold_pct=&baseline_window=` computes baseline move %, z-score, anomaly flag, and conviction.
- AI context generation per alert: `generate_context()` creates cause-oriented alert explanations per mode.
- Dashboard with charts and anomaly history live: `/` renders no-auth Chart.js dashboard and signal cards.
- Email alert delivery working: `POST /alerts/dispatch` sends through SMTP if configured or writes a reviewer-visible `.eml` outbox fallback.
- Webhook alert delivery: `POST /alerts/dispatch` posts JSON to `webhook_url` when configured.
- API access for programmatic queries: `/rates`, `/anomalies`, `/api/export`.
- Stripe or x402 payment integration: x402-style `X-PAYMENT` gate on `/api/export` and `/pricing` payment metadata.
- Python backend / cron polling: `POST /poll` is cron-safe and idempotently upserts public series data.
- Postgres-ready storage: SQLite for MVP/runtime, normalized `rate_points`, `alerts`, `subscribers` tables that can be moved to Postgres.
