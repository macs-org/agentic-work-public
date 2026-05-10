# Counter Review Response — idea_007 Smart Contract Auditor

Updated: 2026-05-10T18:31:34Z

## Exact latest reviewer/counter ask

BTNOMB shows `NEGOTIATING` with a `$50` counter against the original `$300` bounty. The reviewer reason says the implementation is regex/heuristic pattern matching, not symbolic execution or AST-based analysis; the scaffold and tests are functional, but “smart contract auditor” overstates capability.

## Patch made for this response

The public artifact now addresses that criticism directly:

- `app/main.py` adds a dependency-free Solidity AST-lite indexer that extracts function nodes, state variables, line spans, signatures, and per-function bodies.
- `app/main.py` adds bounded symbolic operation tracing for guards, external calls, state writes, `tx.origin`, and validator-controlled block sources.
- Reentrancy findings are now backed by checks-effects-interactions ordering: an `external_interaction` before a later `state_write` in the same function without a `nonReentrant` guard.
- Reports now expose `analysis_engine` and `structural_summary` fields so reviewers can inspect the indexed functions and operation traces.
- `tests/test_auditor.py` adds assertions proving the `withdraw` trace records the external call before the `balances` state write and that the synthesized reentrancy finding is AST/dataflow-backed.
- `LIMITATIONS.md`, `README.md`, `DEMO.md`, and `ACCEPTANCE_CHECKLIST.md` were refreshed to avoid overstating the product: this is now described as AST-lite + bounded symbolic trace MVP, not a full compiler/symbolic-execution audit suite.

## Verification

- `PYTHONPATH=. python3 -m pytest tests -q` → `8 passed in 1.65s`
- `python3 scripts/btnomb.py validate ... --tests` → `structure_ok=True`, `tests_ok=True`, `8 passed`
- Evidence files added:
  - `evidence/pytest-2026-05-11.txt`
  - `evidence/ast-dataflow-sample-2026-05-11.json`
  - `evidence/live-ready-2026-05-10.json` confirms the live Vercel `/ready` endpoint exposes `ast_indexer=true`, `bounded_symbolic_trace=true`, and `production_ready=true` after redeploy.

## Updated artifact URL

https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_007-smart-contract-auditor

## Suggested reviewer response

I updated the submission to address the latest counter reason directly. The artifact no longer relies on regex-only vulnerability matching: it now includes dependency-free Solidity AST-lite indexing and bounded symbolic operation traces. The reentrancy finding is backed by per-function ordering evidence showing the external interaction occurs before the later `balances` state write, and the report exposes `analysis_engine` plus `structural_summary` so that trace is reviewable.

I also updated the docs/limitations to avoid overstating the MVP as a full compiler-backed/symbolic-execution auditor. The public artifact remains an MVP, but the core audit signal is now AST/dataflow-backed, with tests and evidence proving it.

Updated URL: https://github.com/macs-org/agentic-work-public/tree/main/btnomb/idea_007-smart-contract-auditor

Verification: tests now pass with 8 tests, including the new AST/dataflow trace assertion. Evidence is included in `evidence/ast-dataflow-sample-2026-05-11.json` and `evidence/pytest-2026-05-11.txt`.
