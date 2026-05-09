# Live Deployment Evidence — Smart Contract Auditor (idea_007)

Last verified: 2026-05-09T12:25:03Z

## Public Vercel deployment

- Live app: https://btnomb-idea-007-smart-contract-audi.vercel.app
- Health endpoint: https://btnomb-idea-007-smart-contract-audi.vercel.app/health
- Readiness endpoint: https://btnomb-idea-007-smart-contract-audi.vercel.app/ready
- API docs: https://btnomb-idea-007-smart-contract-audi.vercel.app/docs
- OpenAPI: https://btnomb-idea-007-smart-contract-audi.vercel.app/openapi.json

## Verification

Live Vercel smoke passed: root landing page, health, readiness `production_ready=true`, preview audit, x402 402 gate, paid audit, JSON/Markdown/HTML/PDF report retrieval, and history verification.

Smoke-test evidence file: `evidence/e2e-smoke-vercel.json`

Reviewer demo API key for protected audit/report endpoints: `reviewer-audit-key`

## Vercel runtime notes

- Runtime: Vercel Python serverless via `api/index.py` and `vercel.json`.
- Persistent production deployments should use managed Postgres/object storage where applicable; this Vercel proof uses serverless-compatible `/tmp` storage for reviewer-visible live verification.
- x402 payout/pay-to address is the Agentic Work project wallet on Base: `0x23bB05603A980C2915FC3B9D5D4a475993b666DE`.
