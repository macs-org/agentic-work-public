# clarity-act.fun public test launch flow

No-auth FastAPI/Vercel public test app for a CLARITY Act-aware token launch flow.

The app is intentionally scoped to `clarity-act-dot-fun/test-launch-flow/` in `macs-org/agentic-work-public`. It demonstrates:

- every current House-engrossed CLARITY Act token-creator requirement (`R-001` through `R-080`) as a visible input/status/button or hosted form section;
- page-level `CLARITY Act references` panels and control-level citation chips with local source file and line ranges;
- buyer-visible hosted public forms/reports with JSON exports and content hashes;
- confidential ownership-list handling that shows public status without leaking private details;
- launch mechanics labeled as smart-contract/API requirements, not CLARITY Act requirements.

This is a deterministic demo only. It does not file with the SEC/Commission, use private keys, call Bankr/Liquid/Doppler, or write onchain.

## Local run

```bash
cd clarity-act-dot-fun/test-launch-flow
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
uvicorn app.main:app --reload
```

Open:

- <http://127.0.0.1:8000/>
- <http://127.0.0.1:8000/token/create>
- <http://127.0.0.1:8000/forms/demo/offering-statement>
- <http://127.0.0.1:8000/forms/demo/purchaser-information>
- <http://127.0.0.1:8000/token/0xDemo>

## Vercel deploy

This subdirectory uses the Python serverless pattern:

```bash
PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH" vercel --prod --yes
```

Then run production smoke checks:

```bash
python scripts/production_smoke.py <production-url> > samples/production-smoke-vercel.json
```

## File map

- `api/index.py` — Vercel serverless entrypoint.
- `app/main.py` — FastAPI route handlers and HTML rendering.
- `app/requirements_matrix.py` — generated `R-001` through `R-080` requirement registry with citations/excerpts.
- `app/hosted_forms.py` — deterministic public form/report/certification package rendering data.
- `app/sample_data.py` — deterministic demo token, launch mechanics, and private/export-only sample object.
- `tests/test_flow.py` — readiness, route, coverage, citation, confidentiality, external-affirmation, and security hygiene tests.
- `scripts/production_smoke.py` — live URL smoke checker.
- `samples/production-smoke-vercel.json` — committed production smoke evidence after deploy.
