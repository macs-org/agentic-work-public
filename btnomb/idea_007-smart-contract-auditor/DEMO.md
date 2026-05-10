# Smart Contract Auditor Demo

This demo package is meant to make BTNOMB review easier. It includes a vulnerable Solidity contract, example API requests, generated JSON output, and a full Markdown report.

## Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
AUDITOR_API_KEY=dev-audit-key .venv/bin/uvicorn app.main:app --reload
```

Open:

- API docs: http://127.0.0.1:8000/docs
- Dashboard: http://127.0.0.1:8000/dashboard with `X-API-Key: dev-audit-key`

## Demo contract

`examples/VulnerableVault.sol` intentionally contains multiple common risk patterns:

- external call before state update (`SWC-107` reentrancy class)
- unchecked low-level call result (`SWC-104`)
- `tx.origin` authorization (`SWC-115`)
- `block.timestamp` randomness/time dependency (`SWC-116`)

## Free preview request

```bash
curl -sS -X POST http://127.0.0.1:8000/audit   -H 'Content-Type: application/json'   -H 'X-API-Key: dev-audit-key'   -d @demo/preview-request.json | jq .
```

Expected behavior:

- HTTP 200
- `preview: true`
- nonzero `severity_summary`
- detailed findings hidden

Stored evidence: `demo/preview-response.json`.

## Full paid-audit demo request

```bash
curl -sS -X POST http://127.0.0.1:8000/audit   -H 'Content-Type: application/json'   -H 'X-API-Key: dev-audit-key'   -H 'X-PAYMENT: demo-payment-proof'   -d @demo/full-audit-request.json | jq .
```

Expected behavior:

- HTTP 200
- ranked findings list
- per-finding file/line/code annotations
- attack vectors
- remediation snippets
- synthesized summary
- Markdown and PDF-ish report strings

Stored evidence:

- `demo/full-audit-response.json`
- `demo/full-audit-report.md`
- `demo/full-audit-report.txt`

## Generated finding summary

The included full-audit evidence detects the high-signal issues expected from `VulnerableVault.sol`, including:

- `External call before state update`
- `Authorization uses tx.origin`
- `Miner/validator-influenced time dependency`

This demonstrates the end-to-end flow requested in the bounty: Solidity input → AST-lite structure extraction → bounded symbolic operation trace → multi-pass analysis shape → synthesis → structured report → remediation guidance → report formats.

## Tests

```bash
PYTHONPATH=. python -m pytest tests -q
```

The test suite includes unit/API tests plus `tests/test_e2e_http.py`, which starts a real Uvicorn server on an ephemeral local port and verifies the live HTTP flow: `/ready`, preview audit, x402 `402 Payment Required`, paid audit, report downloads, history, and the under-90-second target. It also asserts that the `withdraw` trace records an external interaction before the later `balances` state write, which is the AST/dataflow-backed reentrancy signal added for the counter response.

For deployment smoke checks against a local container or public URL:

```bash
python3 scripts/e2e_smoke.py --base-url http://127.0.0.1:8000 --api-key dev-audit-key --out evidence/e2e-smoke.json
```

Expected result: all tests pass.
