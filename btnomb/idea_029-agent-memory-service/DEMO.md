# Agent Memory-as-a-Service Demo Evidence

Reviewer-focused evidence for BTNOMB `idea_029`.

## What this MVP proves

- Agents can create an account and receive an API key.
- API-key-authenticated agents can store memories with namespaces and metadata.
- Search automatically embeds text and returns ranked relevant memories by cosine similarity.
- Memory search is isolated by both agent API key and namespace.
- Memories can be deleted and disappear from search.
- Usage metering counts store/search/delete/plan-checkout activity.
- Paid plan checkout returns an x402-compatible Base USDC `402 Payment Required` response.
- `/dashboard`, `/docs`, and `/openapi.json` are available for reviewer inspection.

## Local run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Verification performed

```text
$ python3 -m pytest tests -q
......                                                                   [100%]
6 passed in 0.90s
```

## End-to-end API script

```bash
API=http://127.0.0.1:8000
AGENT=$(curl -sS -X POST "$API/agents" -H 'Content-Type: application/json' -d '{"name":"reviewer-agent"}')
API_KEY=$(python3 - <<'PY'
import json,sys
print(json.load(sys.stdin)['api_key'])
PY
<<<"$AGENT")

curl -sS -X POST "$API/memory" \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"namespace":"due-diligence","content":"BTNOMB idea_029 needs managed vector memory, API auth, usage metering, and x402 plan upgrades","metadata":{"source":"review-demo","priority":"high"}}'

curl -sS "$API/memory/search?namespace=due-diligence&q=vector%20memory%20x402&top_k=3" \
  -H "X-API-Key: $API_KEY"

curl -sS "$API/usage" -H "X-API-Key: $API_KEY"

curl -i -sS -X POST "$API/plans/checkout" \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"plan":"starter"}'
```

## Demo artifacts

See `demo/` for representative request/response JSON:

- `create-agent.request.json` / `create-agent.response.json`
- `store-memory.request.json` / `store-memory.response.json`
- `search-memory.request.json` / `search-memory.response.json`
- `usage.response.json`
- `plan-checkout.request.json` / `plan-checkout.response.json`

All API keys in demo artifacts are synthetic/redacted examples, not live project credentials.
