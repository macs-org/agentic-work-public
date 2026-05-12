# Captionator

Captionator is a Vercel-ready video captioning web app. It lets a user upload a local video, extract speech with Venice Whisper, edit caption text/timing, customize how captions appear on the video, and download a captioned WebM render from the browser.

## Architecture

Captionator uses a hybrid approach that fits Vercel while still supporting real uploaded videos:

- The uploaded video stays local in the browser for preview, editing, styling, and final render.
- `/api/transcribe` temporarily accepts the upload, uses FFmpeg to extract compressed audio in `/tmp`, sends that audio to Venice `openai/whisper-large-v3`, then deletes temp files.
- Caption styling and burned-in video export run client-side with Canvas + MediaRecorder, so the app does not store user media or run heavy final video rendering on Vercel.

Large production uploads should eventually move the transcription path to object storage plus a worker queue; the current Vercel route is intended for short/medium clips that fit Vercel request/function limits.

## Features

- Local video upload and preview
- AI transcription via Venice Whisper using the same API pattern as the macro-econ transcription scripts
- Automatic draft captions from Venice segments when available, otherwise transcript chunking across duration
- Import `.vtt` and `.srt` caption files
- Cue-level timing and text editor
- Caption appearance controls: font, size, weight, text color, background, position, alignment, transition effect
- Live styled overlay preview
- Browser-side burned-in WebM export with captions drawn onto frames
- Export WebVTT, SubRip/SRT, or JSON caption files

## Environment

Production and local transcription require a Venice API key:

```bash
VENICE_API_KEY=...
```

The key is already configured in Vercel production for the live app. Keep it in local shell env or `.env.local`; never commit it.

## Local development

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH"
npm install
npm run dev
```

Open `http://localhost:3000`.

## Production build

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH"
npm run build
npm audit --audit-level=moderate
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

The Vercel project needs `VENICE_API_KEY` configured for production. Do not publish `.vercel/`; it is ignored locally.

## Verification

Local full-flow smoke used an 8-second sample clipped from the macro-econ YouTube source `https://www.youtube.com/watch?v=D5SzNWC2QOE`:

1. Upload sample video.
2. Transcribe uploaded video through `/api/transcribe` and Venice Whisper.
3. Confirm transcript and 4 drafted cues appear.
4. Preview styled captions over the video.
5. Render and download a captioned WebM in browser.

## Reviewer artifacts

- `LIVE_DEPLOYMENT.md` — production URL and verification details
- `samples/production-smoke-vercel.json` — smoke-test output
- `scripts/production_smoke.py` — repeatable live root-page check
- `samples/sample-captions.vtt` and `samples/sample-captions.srt` — sample imports
