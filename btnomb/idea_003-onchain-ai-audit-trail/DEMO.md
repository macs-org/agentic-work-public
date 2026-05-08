# Demo: On-chain AI Audit Trail

This demo shows the reviewer path from agent action logging to Merkle batch commitment and auditor verification. It is local-only evidence; no private keys, wallet files, ledgers, or paid full-brief content are included.

## 1. Start the service

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open the explorer at `http://localhost:8000/` or run the scripted curl demo:

```bash
bash evidence/demo-curl.sh
```

## 2. Log agent actions

`POST /api/actions` accepts raw action fields and stores a canonical SHA-256 hash. The canonical field order is sorted JSON over:

- `agent_id`
- `action_type`
- `input_hash`
- `output_hash`
- `timestamp`
- `description`

Sample generated evidence is in `evidence/log-actions.json`.

## 3. Commit a Merkle batch

`POST /api/batches/commit` takes up to 100 queued actions, creates Merkle proofs, stores a batch, and returns a Base-ready root. The demo batch response in `evidence/commit-batch.json` produced:

```text
merkle_root=656de8125e189e2187696afe7d30f83babc607cc1581a73bfe8620e85d5dd353
actions=3
base_ready=true
```

In production, the same root is passed to `AIAuditTrail.commitBatch(root, actionCount, uri)` on Base. The local API records `AUDIT_CONTRACT_ADDRESS` and `LAST_COMMIT_TX_HASH` when those environment variables are set.

## 4. Verify an auditor-supplied action

`POST /api/verify` recomputes the canonical action hash, looks up the committed row, and returns the Merkle proof plus batch metadata. The successful demo response in `evidence/verify-committed-action.json` returned:

```json
{
  "verified": true,
  "batch_id": 1,
  "index": 1,
  "merkle_root": "656de8125e189e2187696afe7d30f83babc607cc1581a73bfe8620e85d5dd353"
}
```

The tampered-action demo in `evidence/verify-tampered-action.json` returns `verified=false` with `reason="hash not found"`, showing that changed raw fields do not match committed evidence.

## 5. Contract-side verification

The Solidity contract stores known Merkle roots and verifies inclusion proofs with:

```solidity
verifyAction(bytes32 root, bytes32 leaf, bytes32[] calldata proof, uint256 index)
```

Auditors can use the API response fields `action_hash`, `proof`, `index`, and `merkle_root` to reproduce the check locally or against the Base contract.
