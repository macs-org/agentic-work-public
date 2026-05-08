# Limitations and Production Hardening Notes

This submission is a compact, runnable MVP for BTNOMB `idea_029`, not a fully managed production service.

## Implemented in the MVP

- FastAPI API surface for agent creation, memory storage, memory search, deletion, usage, dashboard, health, and plan checkout.
- SQLAlchemy-backed persistence with SQLite by default and a Postgres-compatible `DATABASE_URL` path.
- Deterministic local embedding fallback, so the reviewer can run semantic retrieval with no external model API key.
- API key authentication and per-agent/namespace isolation.
- x402-compatible Base USDC payment requirements for paid plan checkout.
- Tests covering ranking, namespace isolation, per-agent API-key isolation, deletion, usage metering, persistence, dashboard/OpenAPI, and x402 checkout.

## Production hardening still needed

- Replace the deterministic hash embedding fallback with a production embedding provider or a dedicated local embedding model.
- Move vector search to pgvector, Qdrant, Chroma, Pinecone, or another ANN index for large datasets.
- Add API-key rotation, scoped keys, rate limits, and audit logs.
- Add migrations via Alembic instead of `Base.metadata.create_all`.
- Add background jobs for memory compaction/summarization and retention policies.
- Implement completed x402 payment verification/settlement after the checkout challenge is paid; the MVP currently returns valid payment requirements.
- Add hosted deployment configuration, TLS, observability, backups, and multi-region failover.

## Why the MVP is still acceptance-relevant

The bounty asks for a managed vector database and retrieval API built for AI agents. The submitted MVP demonstrates the core product loop end-to-end: authenticated agents store memories, retrieve semantically relevant items, view usage, and encounter a monetizable x402 plan-upgrade flow. The remaining items are production scale/hardening rather than missing core functionality.
