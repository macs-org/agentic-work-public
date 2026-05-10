# Limitations and Production Notes

Updated: 2026-05-10T18:31:34Z

This submission is a compact public MVP, not a replacement for a professional audit. The 2026-05-10 counter-response upgrade intentionally addresses the reviewer critique that the prior package looked regex/heuristic-only:

- Added dependency-free Solidity AST-lite indexing for functions, signatures, state variables, and line spans.
- Added bounded symbolic operation traces that record guards, external interactions, state writes, `tx.origin`, and validator-controlled block sources per function.
- Reentrancy findings are now supported by checks-effects-interactions ordering (`external_interaction` before later `state_write`) instead of line regex alone.
- Reports expose `analysis_engine` and `structural_summary` so reviewers can inspect what was indexed and traced.

Remaining production limitations:

- AST-lite is not a full `solc` compiler AST. A production paid auditor should add `solc --ast-json`, Slither, Mythril/Manticore-style symbolic execution, and corpus-backed false-positive tuning behind the current report schema.
- The included provider passes are deterministic and mockable. Real paid LLM/model providers can be added behind the `ModelReport` abstraction.
- x402 payment verification accepts a demo `X-PAYMENT` proof in this MVP; production should verify through an x402 facilitator before returning paid reports.
- The Vercel deployment is demo-grade serverless storage. Durable production history should use Postgres/S3 or another managed store.
