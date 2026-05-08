# Limitations and Production Hardening Notes

This BTNOMB submission is a compact MVP optimized for reviewer validation. It is functional locally and packaged for Docker, but the following items should be hardened before production use.

## Intentional MVP simplifications

- The default database is SQLite (`sqlite:///autonomous_qa.db`). Production deployments should use Postgres or another managed SQL database via `DATABASE_URL`.
- The semantic similarity assertion is deterministic token-hash cosine similarity. It avoids external model credentials for review, but production users may want configurable embedding providers.
- The scheduler is represented as a tick endpoint (`POST /scheduler/tick`) instead of a bundled always-on worker. In production, call it from cron, a queue worker, or a platform scheduler.
- Email and webhook alerts are safe-by-default: missing SMTP config and non-HTTP demo webhook targets are captured in the database rather than failing runs.
- x402 checkout returns compatible payment requirements, but does not bundle facilitator verification or settlement callbacks.
- API keys are generated with `secrets.token_urlsafe`; production should add rotation, revocation UI, and hashed-at-rest key storage.

## Operational hardening recommended

- Add database migrations (Alembic) and persistent managed storage.
- Add organization/team RBAC, audit logs, and per-suite rate limits.
- Add background job processing for high-volume suite runs and alert delivery retries.
- Add richer endpoint target adapters for chat completions, tool-call traces, streaming responses, and multi-step agent workflows.
- Add pluggable model/embedding integrations for semantic assertions and drift thresholds.
- Add hosted dashboard authentication and charts for pass-rate history.
- Add x402 facilitator verification before unlocking paid features.

## Review-safe behavior

- Tests run entirely in memory with `sqlite:///:memory:`.
- Sample artifacts were generated from local TestClient calls.
- No private wallet files, API keys, SMTP credentials, or internal Agentic Work ledger/state files are required or included.
- The reviewer can validate all core bounty behavior from `README.md`, `DEMO.md`, `ACCEPTANCE_CHECKLIST.md`, `samples/`, and the pytest suite.