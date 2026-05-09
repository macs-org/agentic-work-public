# Deployment and Production Verification — GitHub Activity Intelligence

This counter-response package addresses BTNOMB's reviewer note that the original submission lacked live deployment and production verification evidence.

The app is still published as source for reviewers, but it is now deployable with Docker Compose or any Docker-capable host and includes health/readiness endpoints plus a reusable live smoke verifier.

## Runtime contract

- Web process: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Health endpoint: `GET /healthz`
- Readiness endpoint: `GET /readyz`
- API docs: `GET /docs` and `GET /openapi.json`
- Dashboard: `GET /dashboard`
- Persistent storage: `DATABASE_URL`; SQLite defaults to `/data/github_activity.db` in the container, Postgres-style URLs are supported by SQLAlchemy.
- Admin/write auth: `X-API-Key: $APP_API_KEY`

## One-command Docker Compose deployment

```bash
cp .env.example .env
# Edit APP_API_KEY before exposing publicly.
docker compose up --build
curl http://127.0.0.1:8000/readyz
python3 scripts/production_smoke_test.py --base-url http://127.0.0.1:8000 --api-key "$APP_API_KEY"
```

`docker-compose.yml` persists SQLite data in the `github_activity_data` volume and checks `/readyz` every 30 seconds.

## Direct Docker deployment

```bash
docker build -t github-activity-intelligence .
docker run --rm -p 8000:8000 \
  -e APP_API_KEY=replace-with-a-secret \
  -e DATABASE_URL=sqlite:////data/github_activity.db \
  -e PAY_TO=0x9c768177521C9A832B0f8567265ef02E89D0282e \
  -v github_activity_data:/data \
  github-activity-intelligence
```

The Dockerfile runs as an unprivileged `appuser`, stores state in `/data`, and includes a Docker `HEALTHCHECK` against `/readyz`.

## Render/Railway/Fly-style deployment

Render metadata is included in `render.yaml`:

- runtime: Docker
- health check path: `/readyz`
- generated `APP_API_KEY`
- persistent `DATABASE_URL` value for the container example
- optional `GITHUB_TOKEN` secret slot

For Railway/Fly/Cloud Run, use equivalent environment variables and map the health check to `/readyz`.

## Production verification checklist

Run these checks against the deployed URL before asking for review:

1. `GET /healthz` returns `status=ok`.
2. `GET /readyz` returns `status=ok`, `database_query=true`, `schema_initialized=true`, `pay_to_configured=true`, and count metadata.
3. Admin endpoints reject missing `X-API-Key` and accept the configured key.
4. A seeded repo plus 30-day/7-day/current snapshots produces a positive momentum score.
5. `/repos` search/filter returns the hot repo above the min-score threshold.
6. `/repos/{owner}/{repo}` returns persisted historical snapshots.
7. Watchlist + alert evaluation creates at least one delivered alert record.
8. Weekly digest generation stores a category digest.
9. Paid plan checkout without `X-PAYMENT` returns HTTP 402 with Base USDC x402 requirements.
10. `/dashboard` renders the ranked repo.

`scripts/production_smoke_test.py` automates the checklist with Python stdlib only:

```bash
python3 scripts/production_smoke_test.py \
  --base-url https://your-host.example \
  --api-key "$APP_API_KEY" \
  --out samples/production-smoke-output.json
```

The included `samples/production-smoke-output.json` was captured from a live uvicorn process after this counter-response patch.

## Reviewer note

No private keys, real GitHub tokens, or wallet secrets are required for deployment verification. `GITHUB_TOKEN` is optional; if unset, live GitHub polling uses the public REST rate limit while deterministic seed/snapshot flows remain fully testable.
