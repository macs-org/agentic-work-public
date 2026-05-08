# Acceptance Checklist — BTNOMB idea_029

## Requirement mapping

- [x] Managed memory/retrieval API for agents — `app/main.py`, FastAPI app title `Agent Memory-as-a-Service`.
- [x] Store memory endpoint — `POST /memory` in `app/main.py`.
- [x] Search/retrieval endpoint — `GET /memory/search` in `app/main.py`.
- [x] Delete memory endpoint — `DELETE /memory/{memory_id}` in `app/main.py`.
- [x] API key authentication — `current_agent()` dependency and tests.
- [x] Per-agent isolation — covered by `test_agent_api_keys_isolate_memory_between_agents`.
- [x] Namespace isolation — covered by `test_memory_search_is_namespace_isolated_and_ranks_relevant_content`.
- [x] Automatic embeddings — `embed()` generates deterministic vectors on every stored memory/query.
- [x] Ranked semantic retrieval — cosine ranking in `search_memory()`.
- [x] Persistence — SQLAlchemy models and persistence test.
- [x] Usage metering — `Usage` model plus `/usage` endpoint.
- [x] x402-compatible plan upgrade path — `POST /plans/checkout` returns Base USDC payment requirements.
- [x] Dashboard — `GET /dashboard` with recent memories and usage.
- [x] OpenAPI docs — FastAPI `/docs` and `/openapi.json`.
- [x] Container/deploy starter — `Dockerfile` and `requirements.txt`.
- [x] Reviewer demo artifacts — `DEMO.md` and `demo/`.
- [x] Honest production limitations — `LIMITATIONS.md`.

## Latest verification

```text
2026-05-08T12:36:19Z
python3 -m pytest tests -q
......                                                                   [100%]
6 passed in 0.90s
```

## Public artifact safety

The public deliverable path should contain only source, tests, docs, and demo artifacts for this MVP. It must not include internal Agentic Work state, ledgers, wallet files, private keys, generated databases, `.venv`, caches, or BTNOMB unlock/private brief files.
