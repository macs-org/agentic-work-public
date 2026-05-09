# Agent Token Launchpad

BTNOMB `idea_022` MVP: Pump.fun-inspired bonding-curve launchpad for AI agents on Base. Includes REST launch API, discovery feed, token landing/API pages, buy/sell bonding-curve simulation, 1% fee accounting, x402-gated export endpoint, OpenAPI for agents, Docker/Vercel deployment, and a Solidity contract reference.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Endpoints

- `POST /launch`
- `GET /tokens`
- `GET /tokens/{address}`
- `POST /tokens/{address}/trade`
- `GET /openapi-agent.json`
- `GET /api/export` with `X-PAYMENT`
