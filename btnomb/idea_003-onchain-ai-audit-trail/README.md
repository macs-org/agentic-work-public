# On-chain AI Audit Trail

Audit trail system for autonomous agents: every significant action is hashed, batched into a Merkle root, and committed to a Base-compatible smart contract.

## What is included

- Solidity contract: `contracts/AIAuditTrail.sol`
- Python SDK: `sdk/python/audit_trail.py`
- TypeScript SDK: `sdk/typescript/index.ts`
- REST verification API + explorer: `app/main.py`
- Merkle batching up to 100 actions per root
- Canonical SHA-256 action hashes over agent id, action type, input hash, output hash, timestamp, and description
- Proof generation and verification API for enterprise auditors
- Deploy scripts/templates for Base mainnet/testnet

## Acceptance criteria coverage

- **Smart contract:** stores Merkle roots with batch metadata and verifies inclusion proofs.
- **Gas optimized batching:** API batches up to 100 action hashes per Merkle root. 10,000 actions/day = 100 root submissions/day.
- **TypeScript SDK:** exposes `logAction`, `hashAction`, and `verifyAction`.
- **Python SDK:** exposes equivalent `log_action`, `hash_action`, and `verify_action`.
- **REST API:** accepts raw action fields and returns whether they match a committed proof.
- **Explorer:** `GET /` shows batches and recent agent actions with verification status.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API examples

```bash
curl -X POST http://localhost:8000/api/actions -H 'content-type: application/json'   -d '{"agent_id":"agent-7","action_type":"payment","input_hash":"abc","output_hash":"def","timestamp":"2026-05-08T00:00:00Z","description":"Paid invoice via x402"}'

curl -X POST http://localhost:8000/api/batches/commit

curl -X POST http://localhost:8000/api/verify -H 'content-type: application/json'   -d '{"agent_id":"agent-7","action_type":"payment","input_hash":"abc","output_hash":"def","timestamp":"2026-05-08T00:00:00Z","description":"Paid invoice via x402"}'
```

## Base deployment

Compile/deploy `contracts/AIAuditTrail.sol` with Foundry or Hardhat using Base RPC. Constructor takes no args.

```bash
export BASE_RPC_URL=https://mainnet.base.org
export PRIVATE_KEY=0x...
forge create contracts/AIAuditTrail.sol:AIAuditTrail --rpc-url "$BASE_RPC_URL" --private-key "$PRIVATE_KEY"
```

After deployment set `AUDIT_CONTRACT_ADDRESS` and attach each commit tx hash as `LAST_COMMIT_TX_HASH`.

## Auditor workflow

1. Enterprise exports raw action fields.
2. Auditor submits fields to `/api/verify`.
3. API recomputes canonical SHA-256 hash.
4. API returns batch id, root, Merkle proof, index and contract address.
5. Auditor verifies proof locally or calls `verifyAction(root, leaf, proof, index)` on Base.

## Tests

```bash
pytest tests -q
```
