# Live deployment evidence

- Production URL: https://agenttokenlaunchpad.vercel.app
- Vercel deployment: https://agenttokenlaunchpad-g3id4aim0-agentic-work.vercel.app
- Smoke evidence: `samples/production-smoke-vercel.json`

Verified 2026-05-09:

- `/health` HTTP 200
- `/` HTTP 200 and human-readable `Agent Token Launchpad` dashboard
- `/pricing` HTTP 200
- `/tokens` HTTP 200 discovery feed
- `/openapi-agent.json` HTTP 200 agent-native API spec
- `/api/export` HTTP 200 with `X-PAYMENT: demo`
