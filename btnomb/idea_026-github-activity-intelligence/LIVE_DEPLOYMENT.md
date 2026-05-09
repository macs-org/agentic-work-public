# Live Deployment Evidence — GitHub Activity Intelligence (idea_026)

Last verified: 2026-05-09T12:25:03Z

## Public Vercel deployment

- Live app: https://btnomb-idea-026-github-activity-int.vercel.app
- Health endpoint: https://btnomb-idea-026-github-activity-int.vercel.app/healthz
- Readiness endpoint: https://btnomb-idea-026-github-activity-int.vercel.app/readyz
- API docs: https://btnomb-idea-026-github-activity-int.vercel.app/docs
- OpenAPI: https://btnomb-idea-026-github-activity-int.vercel.app/openapi.json

## Verification

Live Vercel smoke passed 14/14 checks: root landing page, health/readiness, seeded repo, snapshots, score recompute, ranked search, repo detail, watchlist, alerts, digest, x402 checkout, and dashboard.

Smoke-test evidence file: `samples/production-smoke-vercel.json`

Reviewer demo API key for protected seed/snapshot/alert/digest/polling endpoints: `reviewer-api-key`

## Vercel runtime notes

- Runtime: Vercel Python serverless via `api/index.py` and `vercel.json`.
- Persistent production deployments should use managed Postgres/object storage where applicable; this Vercel proof uses serverless-compatible `/tmp` storage for reviewer-visible live verification.
- x402 payout/pay-to address is the Agentic Work project wallet on Base: `0x23bB05603A980C2915FC3B9D5D4a475993b666DE`.
