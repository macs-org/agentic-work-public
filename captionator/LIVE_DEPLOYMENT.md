# Captionator Live Deployment

Status: live

## URLs

- Public production URL: https://captionator-nine.vercel.app/
- Immutable deployment URL: https://captionator-kf0917pid-agentic-work.vercel.app/
- Vercel inspect URL: https://vercel.com/agentic-work/captionator/5EGr8fxVioQgL6HeCAJG7ULj1FM8

## Deployment

- Deployed at: 2026-05-12T12:31:19Z
- Vercel project: `agentic-work/captionator`
- Source repo path: `macs-org/agentic-work-public/captionator`
- Production env: `VENICE_API_KEY` is configured in Vercel for transcription.
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

Note: Next/Turbopack emits a non-fatal NFT tracing warning from the FFmpeg-backed API route, but TypeScript/build completes and the route works locally and in production.

Local audit passed:

```bash
npm audit --audit-level=moderate
```

Local full-flow smoke passed using an 8-second sample clipped from the macro-econ YouTube source `https://www.youtube.com/watch?v=D5SzNWC2QOE`:

- uploaded local MP4 sample
- `/api/transcribe` extracted audio with FFmpeg and transcribed through Venice Whisper
- response returned text, duration `8.01`, model `openai/whisper-large-v3`, and 4 draft cues
- browser preview displayed styled captions over the video
- browser render completed and downloaded a captioned WebM

Production smoke test passed:

```bash
python3 scripts/production_smoke.py "https://captionator-nine.vercel.app"
```

Production API smoke passed with the same sample upload:

- `POST https://captionator-nine.vercel.app/api/transcribe`
- result: `has_text=true`, `caption_count=4`, `duration=8.01`, `model=openai/whisper-large-v3`, `error=null`

Smoke output is saved at `samples/production-smoke-vercel.json`.

Checks passed:

- HTTP 200 at `/`
- root HTML contains `Captionator`
- root HTML contains `Upload video`
- root HTML contains `Transcribe uploaded video`
- root HTML contains `Style captions for the final video`
- root HTML contains `Download captioned video`
- root HTML contains `Export VTT`
- browser visual verification showed the polished app shell with upload, transcription, preview, appearance controls, cue editor, caption-file exports, and captioned-video download sections
