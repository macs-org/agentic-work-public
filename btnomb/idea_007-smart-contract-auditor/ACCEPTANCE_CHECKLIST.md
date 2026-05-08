# Acceptance Criteria Checklist — BTNOMB idea_007

Submission path: `btnomb/idea_007-smart-contract-auditor`

## Required by brief

- [x] API accepts Solidity source code.
  - `POST /audit` accepts `source` for single-file contracts.
  - `POST /audit` accepts `files[]` for multi-file projects.
- [x] Structured security report.
  - JSON response includes `audit_id`, `severity_summary`, `findings`, `gas_optimizations`, `compliance`, `model_reports`, `markdown_report`, and `pdf_report`.
- [x] Multi-model pipeline shape.
  - Two deterministic model-provider passes (`heuristic-model-a`, `heuristic-model-b`) plus synthesis layer are implemented behind the same `ModelReport` abstraction that can be swapped for live LLM providers.
- [x] Severity-ranked vulnerability list.
  - Findings are sorted Critical → High → Medium → Low → Informational.
- [x] Attack vectors and proof-of-concept descriptions.
  - Every finding includes `attack_vector`.
- [x] Line-by-line annotations.
  - Every finding includes `file`, `line`, and `code`.
- [x] Remediation snippets.
  - Every finding includes `remediation` and `fixed_snippet`.
- [x] Gas recommendations.
  - `gas_optimizations[]` flags patterns such as cacheable array lengths and calldata candidates.
- [x] ERC-20 / ERC-721 / ERC-1155 checks.
  - `compliance` reports shape/completeness for requested standards.
- [x] Free preview + paid full audit.
  - `preview: true` returns severity summary only.
  - Full audit emits x402-style 402 requirements unless `X-PAYMENT` is present.
- [x] API key authentication.
  - Protected endpoints require `X-API-Key`.
- [x] Dashboard/history/report formats.
  - `/history`, `/dashboard`, `/reports/{audit_id}`, `.md`, `.html`, and `.pdf` are implemented.
- [x] Dockerfile and tests.
  - `Dockerfile`, `requirements.txt`, and pytest suite included.
- [x] Production readiness and deployment probe.
  - `GET /ready`, Docker `HEALTHCHECK`, unprivileged container user, persistent history path, and `DEPLOYMENT.md` are included.
- [x] End-to-end integration test.
  - `tests/test_e2e_http.py` starts a real Uvicorn process and verifies preview, x402 payment gate, paid audit, report retrieval, history, readiness, and <90s completion.

## Evidence added in acceptance upgrade

- `DEMO.md` with copy/paste commands and expected result summary.
- `examples/VulnerableVault.sol` — intentionally vulnerable demo contract.
- `examples/DemoToken.sol` — ERC-20 shape/compliance demo contract.
- `demo/preview-request.json` and `demo/preview-response.json`.
- `demo/full-audit-request.json` and `demo/full-audit-response.json`.
- `demo/full-audit-report.md` and `demo/full-audit-report.txt`.
- `tests/test_e2e_http.py` — process-level HTTP E2E test for readiness, preview, x402 gate, paid audit, reports, and history.
- `scripts/e2e_smoke.py` — smoke runner for local containers or public deployments.
- `DEPLOYMENT.md` — production deployment/runbook and readiness evidence checklist.
- `evidence/e2e-smoke.json` and `evidence/pytest-2026-05-08.txt` — generated verification artifacts.
