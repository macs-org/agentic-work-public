# Production Deployment Evidence and Runbook

This file addresses the reviewer counter: live deployment readiness, end-to-end integration tests, and production-readiness verification.

## Production configuration

Required environment variables:

```bash
export AUDITOR_API_KEY='replace-with-a-long-random-secret'
export X402_PAY_TO='0x23bB05603A980C2915FC3B9D5D4a475993b666DE'
export AUDIT_HISTORY_PATH='/data/audit_history.jsonl'
```

The service exposes two public health endpoints:

- `GET /health` returns a simple serving check.
- `GET /ready` returns production-readiness checks: writable history storage, non-demo API key, configured x402 pay-to wallet, pricing settings, report formats, and startup timestamp.

A production deployment should treat `/ready` returning `checks.production_ready=true` as the deployment gate.

## Docker deployment

```bash
docker build -t smart-contract-auditor-mvp .
docker run --rm \
  -p 8000:8000 \
  -e AUDITOR_API_KEY="$AUDITOR_API_KEY" \
  -e X402_PAY_TO="$X402_PAY_TO" \
  -e AUDIT_HISTORY_PATH=/data/audit_history.jsonl \
  -v auditor-data:/data \
  smart-contract-auditor-mvp
```

The included Dockerfile now:

- runs as the unprivileged `nobody` user,
- stores audit history under `/data`,
- defines a Docker `HEALTHCHECK` against `/ready`,
- copies reviewer docs into the image,
- keeps all runtime secrets in environment variables.

## Cloud deployment shape

Any container host that supports public HTTPS and persistent volume storage can run the same image. Minimum settings:

- public HTTPS route to container port `8000`,
- persistent volume mounted at `/data`,
- secret env vars for `AUDITOR_API_KEY` and `X402_PAY_TO`,
- readiness probe: `GET /ready`,
- liveness probe: `GET /health`.

Example platform mapping:

- Fly.io/Render/Railway: Dockerfile deploy, set env vars, attach persistent disk, health check `/ready`.
- Kubernetes: Deployment + Service + Ingress, `readinessProbe.httpGet.path=/ready`, `livenessProbe.httpGet.path=/health`, PVC mounted at `/data`.

## End-to-end smoke test

Run against any live deployment or local container:

```bash
python3 scripts/e2e_smoke.py \
  --base-url https://YOUR_PUBLIC_DEPLOYMENT_URL \
  --api-key "$AUDITOR_API_KEY" \
  --out evidence/e2e-smoke-live.json
```

The smoke test verifies:

1. `/health` responds.
2. `/ready` responds and reports production readiness.
3. unauthenticated/protected audit behavior is gated by API key in the pytest suite.
4. free preview returns severity summary only.
5. full audit without `X-PAYMENT` returns x402-style `402 Payment Required`.
6. full audit with payment proof returns ranked Critical/High findings.
7. JSON, Markdown, HTML, and PDF-ish reports are retrievable.
8. `/history` contains the generated audit.
9. the flow completes under the 90-second requirement.

## Current public artifact status

The submitted public artifact is updated at:

https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_007-smart-contract-auditor

This repo package now includes deployment instructions, `/ready`, Docker health checks, real HTTP E2E tests, and generated smoke evidence. A durable hosted URL still requires choosing a hosting target and credentials; accepting the $150 counter is an irreversible payout decision and should be confirmed before accepting the counter-offer.
