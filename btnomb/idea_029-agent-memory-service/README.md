# Agent Memory-as-a-Service

Managed memory storage and semantic retrieval API for AI agents.

Built as a compact MVP for BTNOMB bounty `idea_029`.

## Features

- FastAPI backend with OpenAPI docs at `/docs` and `/openapi.json`.
- SQLAlchemy persistence with SQLite local/demo and Postgres-compatible `DATABASE_URL`.
- Per-agent API keys.
- `POST /memory` to store memory with namespace/content/metadata.
- `GET /memory/search` to retrieve top-k relevant memories by lightweight semantic similarity.
- `DELETE /memory/{id}` to remove memories.
- Namespace isolation by agent and namespace.
- Deterministic local embedding fallback using hashed token vectors, so no external model/API cost is required.
- Usage metering for stores/searches/deletes and plan checkout attempts.
- x402-compatible payment requirements for paid plan upgrades.
- HTML dashboard with recent memories and usage stats.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## API examples

Create agent:

```bash
curl -sS -X POST http://127.0.0.1:8000/agents \
  -H 'Content-Type: application/json' \
  -d '{"name":"memory-agent"}'
```

Store memory:

```bash
curl -sS -X POST http://127.0.0.1:8000/memory \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"namespace":"project-a","content":"FastAPI billing invoices x402","metadata":{"kind":"api"}}'
```

Search memory:

```bash
curl -sS 'http://127.0.0.1:8000/memory/search?namespace=project-a&q=invoice%20api&top_k=5' \
  -H "X-API-Key: $API_KEY"
```

Delete memory:

```bash
curl -sS -X DELETE http://127.0.0.1:8000/memory/$MEMORY_ID \
  -H "X-API-Key: $API_KEY"
```

Usage:

```bash
curl -sS http://127.0.0.1:8000/usage \
  -H "X-API-Key: $API_KEY"
```

Plan checkout returns Base USDC x402 payment requirements:

```bash
curl -i -X POST http://127.0.0.1:8000/plans/checkout \
  -H "X-API-Key: $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"plan":"starter"}'
```

Dashboard:

```text
GET /dashboard
```

## Database

Default:

```text
sqlite:///agent_memory.db
```

Postgres-compatible deployment:

```text
postgresql+psycopg://user:pass@host:5432/agent_memory
```

## Tests

```bash
.venv/bin/python -m pytest tests -q
```

Current result:

```text
......                                                                   [100%]
6 passed in 0.90s
```

## Reviewer evidence

- `DEMO.md` provides an end-to-end reviewer walkthrough.
- `demo/` contains representative request/response artifacts for create-agent, store, search, usage, delete, and x402 plan checkout.
- `ACCEPTANCE_CHECKLIST.md` maps bounty requirements to files, endpoints, and tests.
- `LIMITATIONS.md` distinguishes implemented MVP functionality from production hardening work.

## Acceptance mapping from public preview

- Three core endpoints functional: implemented (`POST /memory`, `GET /memory/search`, `DELETE /memory/{id}`).
- Semantic search returning relevant results: implemented with deterministic hashed token vectors and cosine similarity.
- API key auth: implemented.
- Usage metering: implemented.
- Dashboard: implemented.
- Namespace isolation: implemented and tested.
- Automatic embedding generation: implemented locally, no client-side embedding needed.
- Plan upgrades: implemented via x402-compatible Base USDC requirements at `POST /plans/checkout`.
- Vector storage: SQLAlchemy stores deterministic embedding vectors locally; deployment can swap storage to Postgres/pgvector or Qdrant behind the same API.
- Embeddings: deterministic local embedding fallback keeps MVP runnable without external API keys; OpenAI/OpenRouter embedding clients can replace `embed()` for production.
- Documentation: README + FastAPI OpenAPI docs.
