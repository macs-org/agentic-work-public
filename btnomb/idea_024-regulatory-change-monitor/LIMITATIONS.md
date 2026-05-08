# Limitations and reviewer notes

This MVP is intentionally compact for the BTNOMB delivery window. It is suitable for review, local demos, and a small pilot, but the following would be hardened before a production SaaS launch.

## Current constraints

- Federal Register coverage is used as the live source layer for SEC, FDA, FCC, and CFTC. EU-specific source adapters are not included in this MVP, although the source abstraction can add EUR-Lex or agency RSS/API feeds.
- The summarizer is deterministic keyword/rule based. It produces immediate summaries and impact scoring without external LLM costs; production can swap in an LLM summarizer behind `summarize_document`.
- Scheduling is exposed through `GET /api/scheduler/status` and the documented `POST /api/poll` command. Production deployment should call it from cron, a worker queue, or a managed scheduler every 300 seconds.
- SMTP delivery requires `SMTP_HOST` and related environment variables. Without SMTP, alerts are stored as development outbox delivery records for safe reviewer verification.
- Webhook delivery is best-effort with timeout and status recording; production should add retries, signing, and backoff.
- x402 support is implemented as a payment requirement endpoint and payment-gated export header check. Production should verify real x402 settlement receipts before granting durable access.
- SQLite persistence is sufficient for the MVP. Production should move to Postgres, add migrations, and add tenant/account isolation.
- Authentication/admin controls are out of scope for this bounty MVP; production dashboard and subscriber management would need auth.

## No secrets in evidence

The demo artifacts use example.test addresses, demo payment headers, and deterministic fake source documents. No project wallet private key, API token, SMTP secret, or internal BTNOMB state file is included.
