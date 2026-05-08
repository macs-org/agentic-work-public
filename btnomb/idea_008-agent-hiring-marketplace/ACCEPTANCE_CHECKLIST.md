# Acceptance Checklist

- [x] REST task-posting API with OpenAPI spec at `/docs` and `/openapi.json`.
- [x] Structured task schema: title, requirements, acceptance criteria, deadline, budget in USDC, category.
- [x] Public-style agent discovery feed for open tasks, ranked by capability fit.
- [x] Autonomous worker registration with wallet, capabilities, completion stats, speed, and Base L2 attestation reference.
- [x] Bid submission with cost, estimated completion time, and proposal.
- [x] Matching engine ranks bids by reputation, capability match, cost competitiveness, and speed.
- [x] Accepted bid exposes full spec to winning agent and creates a held Base USDC escrow record.
- [x] Work submission endpoint with artifact URL and summary.
- [x] Approval path releases escrow to agent wallet and improves reputation.
- [x] Rejection path refunds poster minus 2.5% arbitration fee and updates completed count.
- [x] Reference Solidity escrow/attestation contract included.
- [x] Python SDK included.
- [x] TypeScript SDK included.
- [x] Minimal dashboard and stats endpoints included.
- [x] Test suite covers key lifecycle and 100-agent support.
- [x] Dockerfile and local run instructions included.
