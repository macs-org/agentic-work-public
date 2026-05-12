import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import ffmpegPath from "ffmpeg-static";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 60;

const VENICE_TRANSCRIPTION_URL = "https://api.venice.ai/api/v1/audio/transcriptions";
const MAX_UPLOAD_BYTES = 90 * 1024 * 1024;

type VeniceSegment = {
  start?: number;
  end?: number;
  text?: string;
};

type Caption = {
  id: string;
  start: number;
  end: number;
  text: string;
};

function getVeniceApiKey() {
  return process.env.VENICE_API_KEY || process.env.VENICE_KEY || process.env.VENICE_API_TOKEN;
}

function extensionForMime(mime: string, fallbackName: string) {
  const cleanName = fallbackName.toLowerCase();
  const ext = path.extname(cleanName);
  if (ext) return ext;
  if (mime.includes("mp4")) return ".mp4";
  if (mime.includes("quicktime")) return ".mov";
  if (mime.includes("webm")) return ".webm";
  if (mime.includes("mpeg")) return ".mp3";
  if (mime.includes("wav")) return ".wav";
  return ".bin";
}

function getFfmpegBinary() {
  const bundled = ffmpegPath || "";
  const cwdBundled = path.join(/* turbopackIgnore: true */ process.cwd(), "node_modules/ffmpeg-static/ffmpeg");
  if (bundled && existsSync(bundled)) return bundled;
  if (existsSync(cwdBundled)) return cwdBundled;
  return "ffmpeg";
}

function runFfmpeg(args: string[]) {
  return new Promise<void>((resolve, reject) => {
    const child = spawn(getFfmpegBinary(), args, { stdio: ["ignore", "ignore", "pipe"] });
    let stderr = "";

    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
      if (stderr.length > 4000) stderr = stderr.slice(-4000);
    });

    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr || `ffmpeg exited with ${code}`));
    });
  });
}

function clampSeconds(value: number) {
  if (!Number.isFinite(value) || value < 0) return 0;
  return Math.round(value * 1000) / 1000;
}

function splitTranscriptToCaptions(text: string, durationSeconds: number): Caption[] {
  const words = text.split(/\s+/).map((word) => word.trim()).filter(Boolean);
  if (words.length === 0) return [];

  const targetDuration = durationSeconds > 0 ? durationSeconds : Math.max(12, Math.ceil(words.length / 2.4));
  const wordsPerCue = 9;
  const chunks: string[] = [];

  for (let index = 0; index < words.length; index += wordsPerCue) {
    chunks.push(words.slice(index, index + wordsPerCue).join(" "));
  }

  const segment = Math.max(1.4, targetDuration / chunks.length);
  return chunks.map((chunk, index) => {
    const start = clampSeconds(index * segment);
    const end = clampSeconds(index === chunks.length - 1 ? targetDuration : Math.min(targetDuration, (index + 1) * segment));
    return {
      id: `transcript-${index}`,
      start,
      end: Math.max(start + 0.5, end),
      text: chunk,
    };
  });
}

function captionsFromSegments(segments: VeniceSegment[] | undefined, fallbackText: string, fallbackDuration: number) {
  const captionSegments = (segments || [])
    .map((segment, index) => {
      const text = String(segment.text || "").trim();
      if (!text) return null;
      const start = clampSeconds(Number(segment.start || 0));
      const end = clampSeconds(Number(segment.end || start + 2));
      return {
        id: `venice-${index}`,
        start,
        end: Math.max(start + 0.5, end),
        text,
      } satisfies Caption;
    })
    .filter((caption): caption is Caption => caption !== null);

  if (captionSegments.length > 0) return captionSegments;
  return splitTranscriptToCaptions(fallbackText, fallbackDuration);
}

async function callVenice(audioBuffer: Buffer, apiKey: string) {
  async function request(verbose: boolean) {
    const form = new FormData();
    form.append("file", new Blob([new Uint8Array(audioBuffer)], { type: "audio/mpeg" }), "captionator-audio.mp3");
    form.append("model", "openai/whisper-large-v3");
    if (verbose) {
      form.append("response_format", "verbose_json");
      form.append("timestamp_granularities[]", "segment");
    }

    return fetch(VENICE_TRANSCRIPTION_URL, {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}` },
      body: form,
    });
  }

  let response = await request(true);
  let payload = await response.json().catch(() => ({}));

  if (!response.ok && response.status === 400) {
    response = await request(false);
    payload = await response.json().catch(() => ({}));
  }

  if (!response.ok) {
    const detail = payload?.error?.message || payload?.error || payload?.message || `Venice returned ${response.status}`;
    throw new Error(String(detail));
  }

  return payload as { text?: string; duration?: number; segments?: VeniceSegment[] };
}

export async function POST(request: Request) {
  const apiKey = getVeniceApiKey();
  if (!apiKey) {
    return NextResponse.json(
      { error: "VENICE_API_KEY is not configured for transcription." },
      { status: 500 },
    );
  }

  const form = await request.formData();
  const file = form.get("video");
  const durationSeconds = Number(form.get("duration") || 0);

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Upload a video or audio file in the `video` form field." }, { status: 400 });
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    return NextResponse.json(
      { error: "This upload is too large for the Vercel transcription path. Try a shorter source or pre-compressed clip." },
      { status: 413 },
    );
  }

  const workdir = await mkdtemp(path.join(tmpdir(), "captionator-"));
  const inputPath = path.join(workdir, `input${extensionForMime(file.type, file.name)}`);
  const audioPath = path.join(workdir, "audio.mp3");

  try {
    const bytes = Buffer.from(await file.arrayBuffer());
    await writeFile(inputPath, bytes);

    await runFfmpeg([
      "-y",
      "-i", inputPath,
      "-vn",
      "-ac", "1",
      "-ar", "16000",
      "-b:a", "48k",
      audioPath,
    ]);

    const audioBuffer = await readFile(audioPath);
    const venice = await callVenice(audioBuffer, apiKey);
    const text = String(venice.text || "").trim();
    const transcriptDuration = Number(venice.duration || durationSeconds || 0);
    const captions = captionsFromSegments(venice.segments, text, transcriptDuration);

    return NextResponse.json({
      text,
      duration: transcriptDuration,
      captions,
      model: "openai/whisper-large-v3",
      segments: venice.segments || [],
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Transcription failed." },
      { status: 500 },
    );
  } finally {
    await rm(workdir, { recursive: true, force: true });
  }
}
