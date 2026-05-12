# Captionator Live Deployment

Status: live

## URLs

- Public production URL: https://captionator-nine.vercel.app/
- Immutable deployment URL: https://captionator-okq4xgrr3-agentic-work.vercel.app/
- Vercel inspect URL: https://vercel.com/agentic-work/captionator/7GVrBnUoEDNNo23kAWUrtKYqtpmL

## Deployment

- Deployed at: 2026-05-12T04:24:14Z
- Vercel project: `agentic-work/captionator`
- Source repo path: `macs-org/agentic-work-public/captionator`
- Deployment command, run from this directory:

```bash
set -a
. ~/.hermes/.env
set +a
export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH"
vercel --prod --yes --scope "$VERCEL_SCOPE" --token "$VERCEL_TOKEN"
```

## Verification

Local production build passed:

```bash
npm run build
```

Production smoke test passed:

```bash
python3 scripts/production_smoke.py "https://captionator-nine.vercel.app"
```

Smoke output is saved at `samples/production-smoke-vercel.json`.

Checks passed:

- HTTP 200 at `/`
- root HTML contains `Captionator`
- root HTML contains `Upload video`
- root HTML contains `Export VTT`
- browser visual verification showed the polished app shell with upload, preview, draft assistant, cue editor, exports, and production-path sections
