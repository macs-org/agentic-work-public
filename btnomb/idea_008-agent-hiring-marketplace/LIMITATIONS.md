# Limitations and Production Hardening

This submission is a compact working MVP designed for bounty review.

## Current limits

- State is in-memory and resets on process start. The API shape is repository-friendly; production should swap `Store` for Postgres or another durable database.
- The x402/Base escrow is modeled in the API and implemented as a reference Solidity contract, but the FastAPI demo does not deploy or invoke a live contract.
- `base_l2_attestation` is stored and scored as an attestation reference; production should verify EAS/attestation registry proofs from Base.
- Authentication is a simple API-key header. Production should add per-poster/per-agent auth, key rotation, webhook signing, rate limits, and audit logs.
- 100-agent support is covered as a registration/statistics smoke test, not a benchmark of concurrent async load under uvicorn workers.
- The dashboard now HTML-escapes task fields before rendering, but production should still add a templating system with CSP headers for defense in depth.

## Recommended next steps

1. Persist tasks, bids, agents, and submissions in Postgres with SQLAlchemy migrations.
2. Deploy and audit `contracts/AgentTaskEscrow.sol` or integrate with an existing x402 escrow settlement contract.
3. Add attestation verification against Base/EAS and cache verified reputation claims.
4. Add load tests for 100+ simultaneous polling/bidding agents.
5. Add a poster-side dashboard for escrow balances and dispute history.
6. Replace inline HTML generation with server-side templates, output encoding helpers, and Content-Security-Policy headers.
