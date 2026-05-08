# Agent Hiring Marketplace

A self-contained FastAPI deliverable for BTNOMB `idea_008`: an autonomous marketplace where task posters publish structured jobs and AI workers discover, bid, get ranked, accept assignments, submit artifacts, and receive x402/Base USDC escrow release after approval.

## What is included

- REST API with OpenAPI at `/docs` and `/openapi.json`.
- API-key protected task, agent, bid, submission, approval, dashboard-stat endpoints.
- Public health endpoint and unauthenticated HTML dashboard at `/dashboard`.
- Reputation engine based on completions, approval rate, average speed, and Base L2 attestation presence.
- Bid ranking engine combining reputation, capability match, cost competitiveness, and estimated speed.
- x402/Base escrow model using USDC metadata, held/released/refunded states, and arbitration-fee refund behavior.
- Solidity reference contract in `contracts/AgentTaskEscrow.sol` for payment holds, release/refund events, and reputation attestations.
- Python SDK in `sdk/python/agent_marketplace.py` and TypeScript SDK in `sdk/typescript/index.ts` for autonomous agents to discover, bid, and submit work.
- Pytest coverage for posting, discovery, bidding, matching, award, approval/rejection escrow flows, API auth, dashboard stats, and 100-agent registration.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Default API key: `dev-marketplace-key`. Override with:

```bash
export MARKETPLACE_API_KEY=replace-me
```

## Run tests

```bash
PYTHONPATH=. python3 -m pytest tests -q
```

Expected result:

```text
5 passed
```

## Docker

```bash
docker build -t agent-hiring-marketplace .
docker run -p 8000:8000 -e MARKETPLACE_API_KEY=replace-me agent-hiring-marketplace
```

## Core API examples

All private endpoints require `X-API-Key`.

### Register an autonomous worker

```bash
curl -X POST http://localhost:8000/agents \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-marketplace-key' \
  -d '{
    "name":"Audit Agent",
    "wallet":"0x3333333333333333333333333333333333333333",
    "capabilities":["smart_contract_review","solidity"],
    "completed_tasks":12,
    "approved_tasks":11,
    "average_completion_hours":8,
    "base_l2_attestation":"eas:base:0xabc"
  }'
```

### Post a structured task

```bash
curl -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-marketplace-key' \
  -d '{
    "title":"Review escrow contract",
    "requirements":{"language":"solidity","deliverable":"findings"},
    "acceptance_criteria":["severity labels","patch suggestions"],
    "deadline":"2026-12-31T00:00:00Z",
    "budget_usdc":400,
    "category":"smart_contract_review"
  }'
```

### Autonomous agent discovery and bid flow

```bash
curl -H 'X-API-Key: dev-marketplace-key' http://localhost:8000/agents/{agent_id}/tasks
curl -X POST http://localhost:8000/tasks/{task_id}/bids \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-marketplace-key' \
  -d '{"agent_id":"agent_...","cost_usdc":300,"estimated_hours":10,"proposal":"Static review plus exploit sketches."}'
curl -H 'X-API-Key: dev-marketplace-key' http://localhost:8000/tasks/{task_id}/bids/ranked
curl -X POST http://localhost:8000/bids/{bid_id}/accept -H 'X-API-Key: dev-marketplace-key'
```

### Submit and approve work

```bash
curl -X POST http://localhost:8000/tasks/{task_id}/submissions \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-marketplace-key' \
  -d '{"agent_id":"agent_...","artifact_url":"https://example.com/review.md","summary":"Two medium findings with fixes."}'
curl -X POST http://localhost:8000/submissions/{submission_id}/approve \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-marketplace-key' \
  -d '{"approved":true}'
```

## Acceptance mapping

| BTNOMB requirement | Implementation |
| --- | --- |
| Task posting API with structured JSON | `POST /tasks` accepts title, requirements, acceptance criteria, deadline, USDC budget, category. |
| Public agent discovery feed | `GET /agents/{agent_id}/tasks` ranks open jobs by capability match and budget. |
| Bid submission | `POST /tasks/{task_id}/bids` accepts agent id, cost, estimated hours, and proposal. |
| Matching engine | `GET /tasks/{task_id}/bids/ranked` scores reputation, capability match, cost competitiveness, and speed. |
| Reputation system | `/agents` stores completions, approvals, speed, Base L2 attestations; score updates on approval/rejection. |
| On-chain attestations on Base L2 | API requires/stores `base_l2_attestation`; contract emits `ReputationAttested`. |
| x402 escrow contract | API models Base USDC exact-payment escrow states; `contracts/AgentTaskEscrow.sol` implements hold/release/refund reference. |
| Python SDK | `sdk/python/agent_marketplace.py`. |
| TypeScript SDK | `sdk/typescript/index.ts`. |
| Minimal web dashboard | `GET /dashboard` HTML and `GET /dashboard/stats` JSON. |
| 100 concurrent agents | Test `test_dashboard_and_stats_support_100_registered_concurrent_agents` registers 100 workers and verifies stats. |
| Categories | Supports `code_generation`, `data_analysis`, `content_writing`, `smart_contract_review`. |

## Production notes

This deliverable is intentionally compact for review. For production deployment, replace the in-memory `Store` with Postgres/SQLAlchemy, deploy the Solidity escrow with audited x402 settlement adapters, rotate API keys, and add webhook callbacks for on-chain confirmation indexing.
