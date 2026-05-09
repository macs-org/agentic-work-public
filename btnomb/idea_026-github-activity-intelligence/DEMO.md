# Reviewer Demo — GitHub Activity Intelligence

Bounty: `idea_026` — GitHub Activity Intelligence, surface hot emerging libraries before they go mainstream.

This demo shows the submitted FastAPI MVP running locally with in-memory SQLite or a local SQLite file. It does not require private credentials, a live GitHub token, real wallet keys, or a live x402 facilitator. `GITHUB_TOKEN` is optional and only increases GitHub API rate limits for the live `/poll` endpoint.

## 1. Install and run tests

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-06_btnomb-github-activity-intelligence-saas/work/github_activity_intelligence
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=. ./.venv/bin/python -m pytest tests -q
```

Verified on 2026-05-09 counter-response run:

```text
....                                                                     [100%]
4 passed, 26 warnings in 0.95s
```

Captured output is also in `samples/test-output.txt`.

## 2. Start the API

```bash
APP_API_KEY=dev-api-key DATABASE_URL=sqlite:///github_activity.db ./.venv/bin/uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/dashboard
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
http://127.0.0.1:8000/healthz
http://127.0.0.1:8000/readyz
```

## 3. End-to-end reviewer flow

Seed a repository with current metrics:

```bash
curl -sS -X POST http://127.0.0.1:8000/repos/seed \
  -H 'X-API-Key: dev-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"full_name":"acme/hot-ai-agents","description":"LLM agent inference toolkit with API orchestration and observability","language":"Python","stars":100,"forks":10,"open_issues":25,"watchers":100,"contributors":5,"commits":50}'
```

Add historical snapshots so momentum scoring can compare current velocity against 7-day and 30-day baselines:

```bash
curl -sS -X POST http://127.0.0.1:8000/snapshots \
  -H 'X-API-Key: dev-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"full_name":"acme/hot-ai-agents","stars":130,"forks":14,"open_issues":22,"contributors":8,"commits":75,"created_at":"2026-05-01T00:00:00+00:00"}'

curl -sS -X POST http://127.0.0.1:8000/snapshots \
  -H 'X-API-Key: dev-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"full_name":"acme/hot-ai-agents","stars":260,"forks":38,"open_issues":9,"contributors":22,"commits":180}'
```

Search and rank emerging libraries:

```bash
curl -sS 'http://127.0.0.1:8000/repos?category=AI/ML&q=agent&min_score=1&limit=10'
```

Expected result includes the seeded AI agent repo with a positive composite `momentum_score`, plus category/language/search filters.

## 4. Watchlists, alerts, and digest

Create a watchlist threshold and evaluate alerts:

```bash
curl -sS -X POST http://127.0.0.1:8000/watchlist \
  -H 'X-API-Key: dev-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"email":"reviewer@example.com","repo_full_name":"acme/hot-ai-agents","threshold":25}'

curl -sS -X POST http://127.0.0.1:8000/alerts/evaluate -H 'X-API-Key: dev-api-key'
curl -sS 'http://127.0.0.1:8000/alerts?email=reviewer@example.com' -H 'X-API-Key: dev-api-key'
```

Generate a weekly rising-stars digest grouped by category:

```bash
curl -sS -X POST http://127.0.0.1:8000/digest/weekly -H 'X-API-Key: dev-api-key'
```

## 5. Optional live GitHub polling

With or without `GITHUB_TOKEN`, poll GitHub REST for real repositories:

```bash
curl -sS -X POST http://127.0.0.1:8000/poll \
  -H 'X-API-Key: dev-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"repos":["fastapi/fastapi","pydantic/pydantic"],"limit":2}'
```

The endpoint stores metadata snapshots, approximates contributor and commit counts from GitHub pagination, recomputes scores, evaluates watchlists, and reports per-repo errors without aborting the full batch.

## 6. x402-style checkout surface

```bash
curl -i -X POST http://127.0.0.1:8000/plans/checkout \
  -H 'Content-Type: application/json' \
  -d '{"plan":"pro"}'
```

Expected result: HTTP 402 with Base USDC x402 requirement fields including `x402Version`, `accepts`, `network: base`, and `asset: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`.

## 7. Deployment and production smoke verification

To address production-readiness review, the package includes `DEPLOYMENT.md`, `docker-compose.yml`, `render.yaml`, `/healthz`, `/readyz`, and a no-dependency smoke verifier.

```bash
docker compose up --build
curl http://127.0.0.1:8000/readyz
python3 scripts/production_smoke_test.py --base-url http://127.0.0.1:8000 --api-key "$APP_API_KEY"
```

Counter-response verification captured in `samples/production-smoke-output.json`:

```text
ok=true; 14/14 checks passed
```

Smoke coverage includes health, readiness, repo seed, historical snapshots, recompute, ranked search, repo detail persistence, watchlist, alert evaluation, weekly digest, x402 402 checkout, and dashboard rendering.

## 8. Sample artifacts

Generated from the app with `FastAPI TestClient`, `sqlite:///:memory:`, and a live local uvicorn smoke process:

- `samples/00_evidence_summary.json` — generated evidence summary and key checks.
- `samples/01_seed_repos_response.json` — repo seeding responses.
- `samples/02_snapshots_response.json` — historical snapshot responses.
- `samples/03_ranked_repos_response.json` — multi-repo momentum ranking.
- `samples/04_search_filter_response.json` — AI/ML + text query filter evidence.
- `samples/05_repo_detail_response.json` — repo detail with snapshot history.
- `samples/06_watchlist_alerts_response.json` — watchlist creation, alert evaluation, and alert listing.
- `samples/07_weekly_digest_response.json` — grouped weekly rising-stars digest.
- `samples/08_x402_checkout_response.json` — x402-style HTTP 402 payment requirements.
- `samples/09_dashboard_snippet.html` — HTML dashboard snippet.
- `samples/test-output.txt` — current pytest output.
- `samples/production-smoke-output.json` — live uvicorn smoke output with 14/14 checks passing.

## 9. Why this meets the bounty

The deliverable is a working GitHub activity intelligence service: it ingests repository metrics, stores historical snapshots, computes velocity-based momentum scores, tags categories, supports ranked/searchable API results and an HTML dashboard, triggers watchlist alerts, generates weekly rising-star digests, optionally polls live GitHub data, protects write/admin routes, and exposes an x402-style paid-plan checkout surface.