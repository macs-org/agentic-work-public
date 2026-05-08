# Acceptance Checklist

Reviewer-facing checklist for BTNOMB `idea_003`: On-chain AI audit trail — every agent action hashed to Base.

## Required deliverables

- [x] Solidity smart contract for Merkle root storage and verification on Base
  - File: `contracts/AIAuditTrail.sol`
  - Evidence: `commitBatch(bytes32 root, uint64 actionCount, string calldata uri)` stores roots; `verifyAction(...)` validates inclusion proofs for known roots.

- [x] Gas-conscious batching
  - File: `app/main.py`
  - Evidence: `MAX_BATCH_SIZE = 100`; `POST /api/batches/commit` commits up to 100 actions per root.
  - Test: `test_verify_unseen_and_batch_limit_shape` asserts a 105-action queue commits exactly 100 actions.

- [x] TypeScript SDK with `logAction()` and `verifyAction()`
  - File: `sdk/typescript/index.ts`
  - Evidence: `AuditTrailClient.logAction()`, `AuditTrailClient.verifyAction()`, `hashAction()`, and `canonicalAction()`.

- [x] Python SDK equivalent
  - File: `sdk/python/audit_trail.py`
  - Evidence: `AuditTrailClient.log_action()`, `AuditTrailClient.verify_action()`, and `hash_action()`.
  - Test: `test_python_sdk_hash_matches_service_schema` asserts Python SDK hashes match the API/service schema.

- [x] REST API for verification
  - File: `app/main.py`
  - Evidence: `POST /api/verify` returns `verified`, `action_hash`, `batch_id`, `merkle_root`, `proof`, `index`, `contract_address`, and `tx_hash`.

- [x] Simple web explorer of recent agent actions
  - File: `app/main.py`
  - Evidence: `GET /` renders recent batches and recent actions with queued/committed status.

- [x] Enterprise auditor documentation
  - Files: `README.md`, `DEMO.md`, `ACCEPTANCE_CHECKLIST.md`
  - Evidence artifacts: `evidence/*.json`, `evidence/demo-curl.sh`.

## Verification rerun

Command:

```bash
cd /Users/macsclawd/Projects/agentic-work
. /tmp/agentic-work-idea003-venv/bin/activate
python3 scripts/btnomb.py cleanup /Users/macsclawd/Projects/agentic-work/platforms/agent-native/btnomb/jobs/2026-05-08_btnomb-onchain-ai-audit-trail/work/onchain_ai_audit_trail
python3 scripts/btnomb.py validate /Users/macsclawd/Projects/agentic-work/platforms/agent-native/btnomb/jobs/2026-05-08_btnomb-onchain-ai-audit-trail/work/onchain_ai_audit_trail --tests
```

Result: 5 pytest tests passed; BTNOMB validator reported `structure_ok=True` and `tests_ok=True`.

Full output is recorded in `evidence/test-output.txt`.

## Limitations / production notes

- The submitted MVP is Base-ready but not deployed to Base in this package; set `AUDIT_CONTRACT_ADDRESS` and `LAST_COMMIT_TX_HASH` after deployment to attach on-chain transaction metadata to API verification responses.
- The API uses SQLite for local MVP storage. A production enterprise deployment should use managed Postgres, durable object storage for batch payload URIs, authentication, and retention policies.
- `contracts/AIAuditTrail.sol` is intentionally minimal: owner-only root commits, known-root checks, and Merkle proof verification. Production deployments should add operational owner rotation and monitoring around the commit pipeline.
