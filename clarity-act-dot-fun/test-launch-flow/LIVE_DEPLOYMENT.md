# Live deployment

Production URL: https://test-launch-flow.vercel.app
Vercel deployment URL: https://test-launch-flow-l6jhbre3f-agentic-work.vercel.app
Vercel inspect URL: https://vercel.com/agentic-work/test-launch-flow/BpJqEeXeRg215wi1fbwmSJWbkAiG
Smoke evidence: `samples/production-smoke-vercel.json`
Verified endpoint list:

- `/`
- `/health`
- `/ready`
- `/token/create`
- `/forms/demo/offering-statement`
- `/forms/demo/purchaser-information`
- `/reports/0xDemo/semiannual/2026-H1`
- `/certifications/0xDemo/maturity`
- `/token/0xDemo`

Test command/result:

```text
python3 -m venv .venv && . .venv/bin/activate && pip install -q -r requirements.txt && python -m pytest -q
12 passed in 0.96s
```

Production smoke command/result:

```text
python scripts/production_smoke.py https://test-launch-flow.vercel.app > samples/production-smoke-vercel.json
all_ok: true
```

Date/time verified: 2026-05-16T16:12:40.250210+00:00

Known limitations:

- Public test/demo app only; no real SEC/Commission filing is performed.
- Launch mechanics are simulated and never write onchain.
- Demo data is deterministic and not legal advice.
- The app demonstrates the current House-engrossed CLARITY Act requirement mapping; future SEC/CFTC rules are out of scope.
