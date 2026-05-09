# Limitations and Production Hardening Notes — GitHub Activity Intelligence

This is a compact BTNOMB MVP meant to be easy for reviewers to run and inspect. It demonstrates the core product loop but intentionally keeps production infrastructure small.

## Current MVP boundaries

- GitHub polling uses GitHub REST and approximates contributor/commit counts from pagination headers. This is enough for MVP ranking and demos, but production should add GraphQL queries, event streams, release metrics, dependency graph signals, and rate-limit/backoff orchestration.
- Alert delivery is persisted as delivered demo records. Production should wire email/webhook/Slack delivery and retry dead-letter queues.
- x402 checkout is a payment-requirements surface and demo receipt path, not a full facilitator-backed payment verifier.
- `APP_API_KEY` is a single shared admin key. Production should add per-user auth, scoped keys, rotation, and audit logs.
- SQLite is the default database for local review. Production should run Postgres with migrations, backups, and indexes sized for large repo universes.
- Scheduler behavior is represented by callable API endpoints; production should run polling/digest jobs from cron, a queue worker, or a cloud scheduler.
- The dashboard is functional reviewer HTML, not a polished frontend product.
- Tests cover the main product contract plus health/readiness production checks; `scripts/production_smoke_test.py` covers a live HTTP process. Production hardening should still add load tests and authenticated live GitHub API integration tests.

## Known non-blocking issue

Python 3.14 emits deprecation warnings for `datetime.utcnow()`. The app and tests pass; production hardening should replace it with timezone-aware UTC calls.

## No secret requirements

The evidence package contains no wallet private keys, API tokens, internal ledger/state files, or live user data. The sample `dev-api-key` is a local demo value only.