# GitHub Activity Intelligence SaaS MVP

Compact FastAPI MVP for BTNOMB `idea_026`: monitor GitHub repositories, score momentum, generate weekly rising-star digests, expose a searchable dashboard/API, and trigger watchlist alerts.

## What is included

- FastAPI app with OpenAPI at `/docs` and `/openapi.json`.
- SQLite default persistence through SQLAlchemy, with `DATABASE_URL` support for Postgres-style URLs.
- API key protection for write/admin routes via `X-API-Key`.
- GitHub REST polling endpoint using `GITHUB_TOKEN` when configured.
- Momentum scoring based on star velocity, fork acceleration, contributor growth, commit velocity, and issue-resolution proxy.
- Category tagging for AI/ML, DevTools, Web3, Backend, Frontend, and Other.
- Search/filter API and HTML dashboard.
- Watchlist alert records and weekly digest generation.
- x402-compatible demo checkout response for paid plans.
- Deployment readiness endpoints: `/healthz` and `/readyz`.
- Dockerfile with unprivileged runtime user and health check.
- Docker Compose, Render blueprint, deployment runbook, and live production smoke verifier.
- Dockerfile and pytest coverage.

## Quick start

```bash
python -m venv .venv
./.venv/bin/pip install -r requirements.txt
APP_API_KEY=dev-api-key DATABASE_URL=sqlite:///github_activity.db ./.venv/bin/uvicorn app.main:app --reload
```

Open:

- Dashboard: `/dashboard`
- API docs: `/docs`
- Health: `/health`, `/healthz`
- Readiness: `/readyz`

## Test

```bash
PYTHONPATH=. python -m pytest tests -q
```

Current reviewer verification (2026-05-09 counter response):

```text
....                                                                     [100%]
4 passed, 26 warnings in 0.95s
```

Captured output is in `samples/test-output.txt`. The warnings are Python 3.14 `datetime.utcnow()` deprecations and do not affect the MVP behavior.

## Reviewer evidence package

Start with:

- `DEMO.md` — reviewer walkthrough from install/test through scoring, search, watchlists, digest, dashboard, live polling, and x402 checkout.
- `DEPLOYMENT.md` — Docker/Compose/Render deployment runbook and production verification checklist.
- `ACCEPTANCE_CHECKLIST.md` — bounty requirement mapping to code, tests, and sample files.
- `LIMITATIONS.md` — MVP boundaries and production-hardening notes.
- `scripts/production_smoke_test.py` — no-dependency smoke verifier for any live hosted URL.
- `samples/00_evidence_summary.json` — generated evidence summary.
- `samples/production-smoke-output.json` — captured smoke test against a live local uvicorn process, 14/14 checks passing.
- `samples/03_ranked_repos_response.json` — momentum ranking evidence.
- `samples/04_search_filter_response.json` — category/text/min-score filter evidence.
- `samples/06_watchlist_alerts_response.json` — watchlist alert evidence.
- `samples/07_weekly_digest_response.json` — weekly digest evidence.
- `samples/08_x402_checkout_response.json` — x402-style 402 checkout evidence.
- `samples/09_dashboard_snippet.html` — dashboard HTML snippet.

## Configuration

Copy `.env.example` to `.env` if you use a process manager that loads env files.

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_API_KEY` | `dev-api-key` | Required in `X-API-Key` for admin/write routes. Change in production. |
| `DATABASE_URL` | `sqlite:///github_activity.db` | SQLite by default. Postgres-compatible values are accepted by SQLAlchemy. |
| `GITHUB_TOKEN` | unset | Optional token for higher GitHub API rate limits. |
| `PAY_TO` | demo Base address | x402 demo checkout recipient. |

No real secrets are included.

## Core endpoints

### Seed a repo for demos/tests

```bash
curl -X POST http://localhost:8000/repos/seed \
  -H 'X-API-Key: dev-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"full_name":"fastapi/fastapi","description":"FastAPI backend API framework","language":"Python","stars":81000,"forks":7000,"open_issues":600,"watchers":81000,"contributors":850,"commits":7500}'
```

### Poll GitHub live

```bash
curl -X POST http://localhost:8000/poll \
  -H 'X-API-Key: dev-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"repos":["fastapi/fastapi","pydantic/pydantic"],"limit":2}'
```

The endpoint fetches repo metadata plus approximate contributor/commit counts from GitHub REST pagination headers, stores a snapshot, recomputes momentum, and evaluates watchlists.

### Search/filter repos

```bash
curl 'http://localhost:8000/repos?category=Backend&q=api&min_score=0&limit=25'
```

### Add historical snapshots

```bash
curl -X POST http://localhost:8000/snapshots \
  -H 'X-API-Key: dev-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"full_name":"fastapi/fastapi","stars":80000,"forks":6900,"open_issues":650,"contributors":830,"commits":7400,"created_at":"2026-04-06T00:00:00+00:00"}'
```

### Watchlist and alerts

```bash
curl -X POST http://localhost:8000/watchlist \
  -H 'X-API-Key: dev-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"email":"founder@example.com","repo_full_name":"fastapi/fastapi","threshold":25}'

curl -X POST http://localhost:8000/alerts/evaluate -H 'X-API-Key: dev-api-key'
curl 'http://localhost:8000/alerts?email=founder@example.com' -H 'X-API-Key: dev-api-key'
```

Alerts are persisted as delivered demo records; wire `Alert` creation to an email provider for production delivery.

### Weekly digest

```bash
curl -X POST http://localhost:8000/digest/weekly -H 'X-API-Key: dev-api-key'
```

Returns top 10 repos by momentum score per category and stores each digest body.

### Plan checkout

```bash
curl -X POST http://localhost:8000/plans/checkout \
  -H 'Content-Type: application/json' \
  -d '{"plan":"pro"}'
```

Paid plans return HTTP 402 with x402-compatible Base USDC payment requirements when `X-PAYMENT` is absent. This is a compact payment-gating demo, not a full payment processor.

## Momentum scoring

For each repo, the latest snapshot is compared to 7-day and 30-day baselines. The score is:

```text
score =
  star_velocity_7d * 8
  + star_velocity_30d * 3
  + fork_acceleration_7d * 5
  + contributor_growth_30d * 25
  + commit_velocity_7d * 0.5
  + issue_resolution_proxy_30d * 10
```

Where:

- `star_velocity_7d`: positive star delta from the 7-day baseline divided by 7.
- `star_velocity_30d`: positive star delta from the 30-day baseline divided by 30.
- `fork_acceleration_7d`: positive fork delta from the 7-day baseline divided by 7.
- `contributor_growth_30d`: contributor delta divided by prior contributors, minimum denominator 1.
- `commit_velocity_7d`: positive commit delta from the 7-day baseline divided by 7.
- `issue_resolution_proxy_30d`: positive decrease in open issues divided by prior open issues.

This makes the MVP favor recent acceleration over absolute repo size, which matches the product goal of surfacing emerging libraries before mainstream discovery.

## Docker / production smoke

```bash
docker compose up --build
curl http://127.0.0.1:8000/readyz
python3 scripts/production_smoke_test.py --base-url http://127.0.0.1:8000 --api-key "$APP_API_KEY"
```

See `DEPLOYMENT.md` for Docker, Render/Railway/Fly-style deployment notes, production readiness checks, and the reviewer smoke checklist. The included counter-response smoke evidence passed 14/14 checks.

## Production notes

- Use Postgres for `DATABASE_URL` in production.
- Schedule `POST /poll` from cron/GitHub Actions/Cloud Scheduler.
- For 1,000+ repos, batch the poller and respect GitHub rate-limit headers.
- Replace demo alert delivery with SendGrid/Postmark/SES.
- Replace demo x402 receipt acceptance with a real verifier or Stripe checkout if required.

## Live Vercel deployment evidence

- Live app: https://btnomb-idea-026-github-activity-int.vercel.app
- Health: https://btnomb-idea-026-github-activity-int.vercel.app/healthz
- Readiness: https://btnomb-idea-026-github-activity-int.vercel.app/readyz
- API docs: https://btnomb-idea-026-github-activity-int.vercel.app/docs
- Smoke evidence: `samples/production-smoke-vercel.json`
- Full deployment note: `LIVE_DEPLOYMENT.md`

