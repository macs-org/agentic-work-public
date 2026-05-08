# Limitations and Production Hardening Notes

This bounty submission is a compact MVP intended to prove the Agent Billing & Metering API workflow end to end. It is safe for local/demo review and structured so production hardening can be added without replacing the core API.

## Implemented in this MVP

- FastAPI service with OpenAPI docs.
- SQLAlchemy models for agents, customers, meter events, and invoices.
- SQLite local storage and `DATABASE_URL` support for external databases.
- Per-agent API keys.
- Usage metering and aggregate usage query.
- Customer spend limits.
- x402-style Base USDC payment requirement payloads for gated resources and plan checkout.
- Paid gate access recorded as usage.
- Invoice generation from stored usage events.
- Basic HTML dashboard.
- Tests for metering, limits, x402 challenge flow, paid gate logging, invoice/dashboard, OpenAPI, plan checkout, and persistence.

## Intentionally simplified for demo review

- `X-PAYMENT` is treated as a facilitator-verified proof placeholder. A production deployment should verify `X-PAYMENT` with an x402 facilitator before marking access as paid.
- API keys are generated and stored directly in the demo database. Production should hash keys at rest, add key rotation, and expose scoped/revocable keys.
- Invoice periods are accepted as strings and currently summarize all customer events. Production should parse dates and filter by `created_at`.
- Dashboard is server-rendered minimal HTML. Production should add richer reporting, pagination, and export formats.
- No multi-tenant admin console, webhook delivery, or background reconciliation worker is included in the MVP.
- No real payment funds are moved by the demo/test suite.

## Safe review guidance

- Run tests locally with in-memory/temp SQLite; no real credentials are needed.
- Review `demo/sample_session.json` for sanitized request/response evidence.
- Use the public artifact URL, not the private repo PR URL, when checking the submitted deliverable.
