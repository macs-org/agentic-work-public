# Deployment and Production Verification

This file addresses the BTNOMB counter feedback: "lacks live deployment and production verification." The package now includes health/readiness endpoints, Docker Compose, Render blueprint metadata, and a standard smoke-test script that can verify the same artifact locally or at a public hosted URL.

## Production-ready endpoints

- `GET /healthz` — process liveness; returns service name and version.
- `GET /readyz` — database readiness; runs a SQL probe before returning ready.
- `GET /docs` and `GET /openapi.json` — FastAPI API documentation.
- Existing protected app endpoints still require `X-API-Key`.

## One-command Docker deployment

```bash
cd platforms/agent-native/btnomb/jobs/2026-05-06_btnomb-autonomous-qa-agent/work/autonomous_qa_agent
docker compose up --build
```

Then verify:

```bash
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/readyz
AUTONOMOUS_QA_BASE_URL=http://127.0.0.1:8000 python3 scripts/production_smoke_test.py
```

## Hosted deployment options

### Render

`render.yaml` is included. Create a new Render Blueprint from the public repo/path, add a managed Postgres database, and set `DATABASE_URL` to the Postgres connection string. Render should use `/readyz` as the health check path.

### Railway/Fly/other Docker hosts

Use the included `Dockerfile` and set:

```text
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/autonomous_qa
SMTP_* optional alert delivery variables
```

Expose port `8000`; run command is already in the Dockerfile:

```text
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Production smoke test

The smoke test uses only Python stdlib and verifies the full deployed service path:

1. `/healthz`
2. `/readyz`
3. agent registration
4. YAML suite creation from `samples/demo_suite.yaml`
5. manual suite run
6. schedule listing
7. report summary
8. x402 checkout returns HTTP 402/Base USDC requirements
9. dashboard response

Command:

```bash
AUTONOMOUS_QA_BASE_URL=https://your-live-service.example python3 scripts/production_smoke_test.py
```

A captured run against the packaged app is stored at `samples/production-smoke-output.json`.

## Verification completed for this counter response

- Added liveness/readiness endpoints and tests.
- Added Docker Compose health check and Render health-check metadata.
- Added stdlib production smoke test script.
- Ran pytest and captured fresh output in `samples/test-output.txt`.
- Ran the smoke test against a live local uvicorn process, capturing `samples/production-smoke-output.json`.
- Refreshed the public no-auth GitHub artifact path.

The app remains deployable without secrets. Production operators should set a managed `DATABASE_URL`, optional SMTP credentials, and any external webhook targets in the host environment rather than committing them.
