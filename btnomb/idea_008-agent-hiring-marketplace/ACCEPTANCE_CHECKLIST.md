# Acceptance Checklist

BTNOMB `idea_008`: Agent hiring marketplace — hire autonomous AI workers by the task.

## Product requirements

- [x] REST task-posting API with OpenAPI spec at `/docs` and `/openapi.json`.
  - Evidence: `app/main.py`, `README.md`, `evidence/sample_api_flow.json`.
- [x] Structured task schema: title, requirements, acceptance criteria, deadline, budget in USDC, category.
  - Evidence: `TaskCreate` model and `POST /tasks`; tests create multiple structured tasks.
- [x] Public-style agent discovery feed for open tasks, ranked by capability fit.
  - Evidence: `GET /agents/{agent_id}/tasks`; `test_task_posting_feed_bidding_matching_and_award_flow`.
- [x] Autonomous worker registration with wallet, capabilities, completion stats, speed, and Base L2 attestation reference.
  - Evidence: `AgentCreate` model, `reputation_score`, `POST /agents`.
- [x] Bid submission with cost, estimated completion time, and proposal.
  - Evidence: `POST /tasks/{task_id}/bids` and `BidCreate` model.
- [x] Matching engine ranks bids by reputation, capability match, cost competitiveness, and speed.
  - Evidence: `bid_rank_score`, `capability_match`, ranked-bids endpoint, lifecycle test.
- [x] Accepted bid exposes full spec to winning agent and creates a held Base USDC escrow record.
  - Evidence: `POST /bids/{bid_id}/accept`; response includes `assigned_agent.full_spec_visible=true`; escrow `network=base`, `asset=USDC`, `x402_scheme=exact`, `state=HELD`.
- [x] Work submission endpoint with artifact URL and summary.
  - Evidence: `POST /tasks/{task_id}/submissions`.
- [x] Approval path releases escrow to agent wallet and improves reputation.
  - Evidence: `test_submission_approval_releases_escrow_and_updates_reputation_stats`.
- [x] Rejection path refunds poster minus 2.5% arbitration fee and updates completed count.
  - Evidence: `test_rejected_submission_refunds_poster_minus_arbitration_fee`.
- [x] Reference Solidity escrow/attestation contract included.
  - Evidence: `contracts/AgentTaskEscrow.sol` with hold/release/refund and `ReputationAttested` event.
- [x] Python SDK included.
  - Evidence: `sdk/python/agent_marketplace.py`.
- [x] TypeScript SDK included.
  - Evidence: `sdk/typescript/index.ts`.
- [x] Minimal dashboard and stats endpoints included.
  - Evidence: `GET /dashboard`, `GET /dashboard/stats`, `evidence/dashboard-preview.html`.
- [x] 100 concurrent/large-agent-list smoke coverage.
  - Evidence: `test_dashboard_and_stats_support_100_registered_concurrent_agents` registers 100 workers and verifies stats/capability counts.
- [x] Dockerfile and local run instructions included.
  - Evidence: `Dockerfile`, `README.md`.

## Acceptance-upgrade evidence added 2026-05-08

- [x] Reran tests after upgrade.
  - Command: `PYTHONPATH=. python3 -m pytest tests -q`
  - Result: `6 passed in 0.63s`.
  - Artifact: `evidence/pytest-2026-05-08.txt`.
- [x] Added reviewer-facing sample request/response artifact.
  - Artifact: `evidence/sample_api_flow.json`.
  - Covers: health, task creation, agent registration, discovery feed, bid, ranking, award, submission, approval, dashboard stats, dashboard HTML-escaping regression.
- [x] Added static dashboard preview artifact.
  - Artifact: `evidence/dashboard-preview.html`.
- [x] Closed the prior non-blocking reviewer caveat about unescaped dashboard task fields.
  - Code: `app/main.py` now escapes title/category/status/budget before interpolating into dashboard rows.
  - Test: `test_dashboard_escapes_task_fields_before_rendering_html`.
- [x] Preserved the already-submitted public URL.
  - URL: `https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_008-agent-hiring-marketplace`.
  - No new BTNOMB submit call required.

## Validation status

- [x] Local tests pass: `6 passed`.
- [x] BTNOMB validator pass after cleanup: `structure_ok=True`, `tests_ok=True`.
- [x] Public no-auth GitHub URL verification completed for the existing submission path.
- [x] No wallet keys, ledgers, state files, full briefs, caches, DB files, or generated Python artifacts are included in the public deliverable.
