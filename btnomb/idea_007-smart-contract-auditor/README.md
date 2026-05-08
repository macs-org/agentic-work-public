# Smart Contract Auditor MVP

Compact FastAPI MVP for BTNOMB `idea_007`: an API-key protected Solidity smart contract auditing service that accepts single-file or multi-file Solidity source and returns structured audit reports.

## What it does

- Accepts Solidity source via `POST /audit` as either `source` or `files`.
- Supports basic multi-file import inlining for local imports.
- Requires `X-API-Key` for all audit/history/report/dashboard endpoints.
- Implements deterministic static heuristic analysis for common Solidity risk patterns:
  - reentrancy / external call before state update (`SWC-107`)
  - unchecked low-level calls (`SWC-104`)
  - unsafe `tx.origin` authorization (`SWC-115`)
  - timestamp/block dependency (`SWC-116`)
  - `delegatecall`, `selfdestruct`, old pragma, unchecked arithmetic, hash collision, access-control hints
- Provides a mockable multi-model abstraction: two deterministic provider passes plus a synthesizer that merges severity-ranked findings.
- Returns severity-ranked findings with attack vectors, line annotations, SWC IDs where applicable, remediation guidance, and corrected Solidity snippets.
- Includes gas optimization suggestions and ERC-20 / ERC-721 / ERC-1155 shape checks.
- Supports free preview mode (`preview: true`) that returns only severity summary and hides detailed findings.
- Emits x402-style `402 Payment Required` requirements for paid full audits:
  - $2 for contracts under 500 lines
  - $5 for 500+ lines
- Persists audit history to JSONL and exposes `/history`, `/dashboard`, and report views.
- Produces JSON, Markdown, HTML, and PDF-ish text reports.

This MVP is self-contained and deterministic so it can be tested/submitted without paid model keys. Production model providers can be added behind the same `ModelReport` shape.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
AUDITOR_API_KEY=dev-audit-key .venv/bin/uvicorn app.main:app --reload
```

Open API docs at:

```text
http://127.0.0.1:8000/docs
```

## Authentication

Set an API key in the environment:

```bash
export AUDITOR_API_KEY='replace-with-a-real-secret'
```

For local tests and demos, the default key is:

```text
dev-audit-key
```

Use it as:

```text
X-API-Key: dev-audit-key
```

## API examples

### Free preview

```bash
curl -sS -X POST http://127.0.0.1:8000/audit \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-audit-key' \
  -d '{
    "contract_name":"Vault",
    "preview":true,
    "source":"pragma solidity ^0.8.20; contract Vault { mapping(address=>uint) balances; function withdraw() external { uint amount = balances[msg.sender]; (bool ok,) = msg.sender.call{value: amount}(\"\"); balances[msg.sender]=0; } }"
  }'
```

Preview returns severity counts but hides details:

```json
{
  "preview": true,
  "severity_summary": {"Critical": 1, "High": 1, "Medium": 0, "Low": 0, "Informational": 0},
  "findings": []
}
```

### Full audit with x402-style payment gate

Without `X-PAYMENT`, full audits return `402` with payment requirements:

```bash
curl -i -X POST http://127.0.0.1:8000/audit \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-audit-key' \
  -d '{"source":"pragma solidity ^0.8.20; contract A {}"}'
```

Demo full audit with a payment proof header:

```bash
curl -sS -X POST http://127.0.0.1:8000/audit \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-audit-key' \
  -H 'X-PAYMENT: demo-payment-proof' \
  -d '{"contract_name":"A","source":"pragma solidity ^0.8.20; contract A {}"}'
```

The MVP accepts any `X-PAYMENT` value for local/demo use. A production deployment should verify the payment with an x402 facilitator before generating the paid report.

### Multi-file audit

```bash
curl -sS -X POST http://127.0.0.1:8000/audit \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-audit-key' \
  -H 'X-PAYMENT: demo-payment-proof' \
  -d '{
    "contract_name":"Token",
    "files":[
      {"path":"lib/Ownable.sol","content":"pragma solidity ^0.8.20; contract Ownable { address owner; }"},
      {"path":"contracts/Token.sol","content":"pragma solidity ^0.8.20; import \"../lib/Ownable.sol\"; contract Token { function mint(address to, uint256 amount) public { } }"}
    ]
  }'
```

## Endpoints

- `GET /health` — health check.
- `GET /ready` — production-readiness check for deployment probes.
- `POST /audit` — run preview or paid audit.
- `GET /reports/{audit_id}` — JSON report.
- `GET /reports/{audit_id}.md` — Markdown report.
- `GET /reports/{audit_id}.html` — human-readable HTML report.
- `GET /reports/{audit_id}.pdf` — PDF-ish plain text response with `application/pdf` media type for MVP portability.
- `GET /history` — recent audit history.
- `GET /dashboard` — lightweight HTML dashboard.

## Report schema highlights

Each full report includes:

- `severity_summary`
- `findings[]` sorted Critical → High → Medium → Low → Informational
- `findings[].attack_vector`
- `findings[].file` and `findings[].line`
- `findings[].fixed_snippet`
- `findings[].swc_id`
- `gas_optimizations[]`
- `compliance`
- `model_reports[]`
- `markdown_report`
- `pdf_report`

## Tests

Run from this directory:

```bash
PYTHONPATH=. python -m pytest tests -q
```

## Docker

```bash
docker build -t smart-contract-auditor-mvp .
docker run --rm -p 8000:8000 \
  -e AUDITOR_API_KEY=replace-with-a-real-secret \
  -e X402_PAY_TO=0x23bB05603A980C2915FC3B9D5D4a475993b666DE \
  -v auditor-data:/data \
  smart-contract-auditor-mvp
```

`GET /ready` is designed for live deployment probes and reports whether persistent history storage, non-demo API key, and x402 payout configuration are production-ready. See `DEPLOYMENT.md` for the full deployment runbook and E2E smoke command.

## Acceptance mapping

- Solidity source API: implemented via `POST /audit`.
- Multi-file import resolution: local import inlining implemented.
- API key auth: implemented via `X-API-Key`.
- Multi-model AI pipeline: deterministic provider abstraction + synthesizer implemented; no external paid models required.
- Severity-ranked vulnerability list: implemented.
- Attack vectors and proof-of-concept scenarios: included per finding.
- Line-by-line annotations: file/line/code included per finding.
- Fix suggestions with Solidity snippets: included per finding.
- Gas recommendations: implemented.
- ERC-20/ERC-721/ERC-1155 checks: implemented as shape/completeness checks.
- JSON/HTML/Markdown/PDF-ish reports: implemented.
- Free preview: implemented.
- x402 pricing: emitted as payment requirements; facilitator verification hook documented.
- Dashboard/history: implemented.
- Tests and Dockerfile: included.

## Limitations

This is a public-submission-ready MVP, not a replacement for a professional audit. The heuristic engine is intentionally deterministic and compact; production deployments should add AST parsing, Slither/Mythril integration, verified x402 facilitator checks, and real model provider adapters behind the included report abstraction.
