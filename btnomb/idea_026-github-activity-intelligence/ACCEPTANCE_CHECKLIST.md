# Acceptance Checklist — idea_026 GitHub Activity Intelligence

Public submission URL: https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_026-github-activity-intelligence

## Bounty requirement mapping

- [x] Surface hot emerging libraries before they go mainstream
  - `momentum_for_repo()` compares latest metrics to 7-day and 30-day baselines, weighting recent star/fork/commit velocity, contributor growth, and issue-resolution proxy.
  - Evidence: `samples/03_ranked_repos_response.json` ranks a fast-rising AI agent repo over larger but slower repos.

- [x] GitHub activity ingestion
  - `POST /poll` fetches GitHub REST repo metadata and approximates contributor/commit counts from pagination headers.
  - `POST /repos/seed` and `POST /snapshots` make demos/tests deterministic without live GitHub credentials.
  - Optional `GITHUB_TOKEN` is supported for higher API rate limits.

- [x] Historical persistence
  - SQLAlchemy models persist repositories, metric snapshots, watchlists, alerts, and weekly digests.
  - SQLite works by default; `DATABASE_URL` supports production-style database configuration.
  - Evidence: `tests/test_github_activity.py::test_dashboard_auth_openapi_checkout_and_persistence` verifies persistence across app clients.

- [x] Searchable ranked API
  - `GET /repos` supports `category`, `language`, text query `q`, minimum score, limit, and sort by momentum score.
  - `GET /repos/{owner}/{name}` returns detail plus recent snapshot history.
  - Evidence: `samples/04_search_filter_response.json` and `samples/05_repo_detail_response.json`.

- [x] Category tagging
  - `classify_repo()` maps descriptions/languages/full names to AI/ML, DevTools, Web3, Backend, Frontend, or Other.
  - Tests verify AI/ML and DevTools paths; samples include AI/ML, DevTools, and Frontend repos.

- [x] Watchlist alerts
  - `POST /watchlist` stores subscriber thresholds.
  - `POST /alerts/evaluate` creates delivered demo alert records when a repo score crosses threshold.
  - `GET /alerts` lists captured alert evidence.
  - Evidence: `samples/06_watchlist_alerts_response.json`.

- [x] Weekly rising-stars digest
  - `POST /digest/weekly` groups the top 10 repos per category into persisted digest bodies.
  - Evidence: `samples/07_weekly_digest_response.json`.

- [x] Reviewer-visible dashboard
  - `GET /dashboard` renders filterable HTML with repo/category/language/stars/forks/momentum rows.
  - Evidence: `samples/09_dashboard_snippet.html`.

- [x] API security
  - Protected write/admin routes require `X-API-Key`.
  - Tests verify unauthorized seed attempts return 401.

- [x] OpenAPI and deployable package
  - FastAPI exposes `/docs` and `/openapi.json`.
  - Package includes `Dockerfile`, `docker-compose.yml`, `render.yaml`, `.env.example`, `requirements.txt`, README, tests, and reviewer evidence.
  - `Dockerfile` runs as an unprivileged user, persists SQLite under `/data`, and health-checks `/readyz`.

- [x] Live deployment and production verification evidence
  - `GET /healthz` returns service liveness.
  - `GET /readyz` checks DB query/schema, configured admin API key, Base USDC asset, pay-to address, count metadata, and runtime warnings.
  - `DEPLOYMENT.md` documents Docker Compose, direct Docker, Render/Railway/Fly-style deployment, and a 10-point verification checklist.
  - `scripts/production_smoke_test.py` verifies any live hosted URL using only Python stdlib.
  - Evidence: `samples/production-smoke-output.json` captured 14/14 live uvicorn smoke checks passing.

- [x] x402-compatible paid-plan surface
  - `POST /plans/checkout` returns HTTP 402 with x402-style Base USDC payment requirements when `X-PAYMENT` is absent for paid plans.
  - Evidence: `samples/08_x402_checkout_response.json`.

## Current verification

Command:

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-06_btnomb-github-activity-intelligence-saas/work/github_activity_intelligence
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest tests -q -p no:cacheprovider
```

Result on 2026-05-09 counter-response run:

```text
....                                                                     [100%]
4 passed, 26 warnings in 0.95s
```

Production smoke run:

```text
python3 scripts/production_smoke_test.py --base-url http://127.0.0.1:8017 --api-key dev-api-key --out samples/production-smoke-output.json
{"checks": "14/14", "ok": true, "out": "samples/production-smoke-output.json"}
```

The warnings are Python 3.14 `datetime.utcnow()` deprecation warnings; they do not affect MVP behavior. Production hardening should switch to timezone-aware `datetime.now(datetime.UTC)`.

## Guardrails

- [x] No project wallet private key or internal ledger/state file included.
- [x] No external API credentials required for tests or deterministic demo evidence.
- [x] No live GitHub token required; polling degrades to unauthenticated GitHub REST limits.
- [x] No new BTNOMB URL submitted during this acceptance upgrade.
- [x] No funds spent during this acceptance upgrade.
- [x] This remains a pending submission until BTNOMB accepts/pays; it is not counted as realized earnings.