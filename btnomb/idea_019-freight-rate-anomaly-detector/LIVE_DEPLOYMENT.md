# Live deployment evidence

- Production URL: https://freightrateanomalydetector.vercel.app
- Vercel deployment: https://freightrateanomalydetector-hp5hvxod5-agentic-work.vercel.app
- Smoke evidence: `samples/production-smoke-vercel.json`

Verified 2026-05-09:

- `/health` returned HTTP 200
- `/` returned HTTP 200 and contains the human-readable dashboard title `Freight Rate Anomaly Detector`
- `/pricing` returned HTTP 200 with Starter/Pro/Institutional pricing
- `/anomalies` returned HTTP 200 with anomaly signal JSON
- `/api/export` returned HTTP 200 when called with `X-PAYMENT: demo-paid-token`

The root App URL is a human-visible no-auth page, not an API-only health endpoint.
