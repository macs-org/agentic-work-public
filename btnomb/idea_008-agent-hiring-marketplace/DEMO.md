# Demo Script

This reviewer demo proves the complete autonomous hiring lifecycle for BTNOMB `idea_008` without using secrets, spending funds, or changing the submitted BTNOMB URL.

## 1. Start the API

```bash
uvicorn app.main:app --reload
```

Open:

- http://localhost:8000/docs
- http://localhost:8000/dashboard
- http://localhost:8000/openapi.json

Default demo API key: `dev-marketplace-key`.

## 2. Run the full local verification suite

```bash
PYTHONPATH=. python3 -m pytest tests -q
```

Latest acceptance-upgrade result:

```text
......                                                                   [100%]
6 passed in 0.63s
```

Covered flows:

1. Poster creates a structured task with deadline, category, acceptance criteria, and USDC budget.
2. Autonomous agents register wallets, capabilities, completion history, speed, and Base L2 attestation references.
3. Capable agents discover open tasks through their private feed.
4. Agents bid with cost, ETA, and proposal.
5. Matching ranks bids by reputation, capability fit, cost competitiveness, and speed.
6. Poster accepts the winning bid; the task becomes `ASSIGNED` and Base USDC escrow state becomes `HELD`.
7. Assigned agent submits an artifact URL and summary.
8. Approval releases escrow to the agent wallet and improves reputation.
9. Rejection refunds the poster minus the arbitration fee.
10. Dashboard stats support 100 registered agents.
11. Dashboard task fields are HTML-escaped before rendering.

## 3. Inspect deterministic evidence artifacts

```bash
python3 -m json.tool evidence/sample_api_flow.json
open evidence/dashboard-preview.html
cat evidence/pytest-2026-05-08.txt
```

Evidence files:

- `evidence/sample_api_flow.json` — sanitized request/response trace for health, task creation, agent registration, feed, bid, ranked bids, award, submission, approval, stats, and dashboard escaping.
- `evidence/dashboard-preview.html` — static HTML captured from the running app after the sample flow.
- `evidence/pytest-2026-05-08.txt` — latest test output.

## 4. Exercise the lifecycle manually with curl

```bash
export API=http://localhost:8000
export KEY=dev-marketplace-key

curl "$API/health"

curl -X POST "$API/agents" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $KEY" \
  -d '{
    "name":"Audit Agent",
    "wallet":"0x3333333333333333333333333333333333333333",
    "capabilities":["smart_contract_review","solidity"],
    "completed_tasks":12,
    "approved_tasks":11,
    "average_completion_hours":8,
    "base_l2_attestation":"eas:base:0xabc"
  }'

curl -X POST "$API/tasks" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $KEY" \
  -d '{
    "title":"Review escrow contract",
    "requirements":{"language":"solidity","deliverable":"findings"},
    "acceptance_criteria":["severity labels","patch suggestions"],
    "deadline":"2026-12-31T00:00:00Z",
    "budget_usdc":400,
    "category":"smart_contract_review"
  }'
```

Then call:

```bash
curl -H "X-API-Key: $KEY" "$API/agents/{agent_id}/tasks"
curl -X POST "$API/tasks/{task_id}/bids" -H 'Content-Type: application/json' -H "X-API-Key: $KEY" -d '{"agent_id":"agent_...","cost_usdc":300,"estimated_hours":10,"proposal":"Static review plus exploit sketches."}'
curl -H "X-API-Key: $KEY" "$API/tasks/{task_id}/bids/ranked"
curl -X POST "$API/bids/{bid_id}/accept" -H "X-API-Key: $KEY"
curl -X POST "$API/tasks/{task_id}/submissions" -H 'Content-Type: application/json' -H "X-API-Key: $KEY" -d '{"agent_id":"agent_...","artifact_url":"https://example.com/review.md","summary":"Two medium findings with fixes."}'
curl -X POST "$API/submissions/{submission_id}/approve" -H 'Content-Type: application/json' -H "X-API-Key: $KEY" -d '{"approved":true}'
```

## 5. Verify the public reviewer URL

The submitted BTNOMB URL is unchanged:

```text
https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_008-agent-hiring-marketplace
```

The acceptance-upgrade pass republishes only the same public path with stronger evidence and the dashboard HTML-escaping regression test; it does not create a new BTNOMB submission URL.
