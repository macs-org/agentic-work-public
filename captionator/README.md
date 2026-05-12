# Captionator

Captionator is a Vercel-ready, browser-first video caption editor. It lets a user upload a local video, draft captions from transcript lines, refine timing, preview captions through a WebVTT track, and export VTT/SRT/JSON caption files.

## Why this MVP is browser-first

Vercel serverless functions are not a good fit for heavy FFmpeg video rendering or writable local media storage. Captionator v1 keeps uploaded media inside the browser as object URLs and only exports caption text files. A production rendering path can add object storage plus an external queue/worker for burned-in captions later.

## Features

- Local video upload and preview
- WebVTT preview track generated from the current cue list
- Import `.vtt` and `.srt` caption files
- Draft captions from pasted transcript lines
- Cue-level timing and text editor
- Export WebVTT, SubRip/SRT, or JSON
- No server-side upload required for the demo

## Local development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Production build

```bash
npm run build
npm start
```

## Vercel deployment

Deploy from this directory:

```bash
set -a
. ~/.hermes/.env
set +a
export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH"
vercel --prod --yes --scope "$VERCEL_SCOPE" --token "$VERCEL_TOKEN"
```

Do not publish `.vercel/`; it is ignored locally.

## Reviewer artifacts

- `LIVE_DEPLOYMENT.md` — production URL and verification details
- `samples/production-smoke-vercel.json` — smoke-test output
- `scripts/production_smoke.py` — repeatable live root-page check
- `samples/sample-captions.vtt` and `samples/sample-captions.srt` — sample imports
