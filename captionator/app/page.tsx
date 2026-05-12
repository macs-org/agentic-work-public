"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

type Caption = {
  id: string;
  start: number;
  end: number;
  text: string;
};

type CaptionStyle = {
  fontFamily: string;
  fontSize: number;
  fontWeight: string;
  color: string;
  backgroundColor: string;
  shadowColor: string;
  position: "top" | "middle" | "bottom";
  align: "left" | "center" | "right";
  effect: "none" | "fade" | "pop" | "slide";
};

type TranscriptionResponse = {
  text: string;
  duration: number;
  captions: Caption[];
  model: string;
  error?: string;
};

const starterCaptions: Caption[] = [
  { id: "sample-1", start: 0, end: 2.8, text: "Upload a video and let Venice Whisper draft captions." },
  { id: "sample-2", start: 2.8, end: 6.2, text: "Edit the text, timing, font, size, color, and effects." },
  { id: "sample-3", start: 6.2, end: 9.4, text: "Then download a captioned WebM video or caption files." },
];

const defaultStyle: CaptionStyle = {
  fontFamily: "Inter, Arial, sans-serif",
  fontSize: 44,
  fontWeight: "800",
  color: "#ffffff",
  backgroundColor: "#000000cc",
  shadowColor: "#000000",
  position: "bottom",
  align: "center",
  effect: "fade",
};

function clampSeconds(value: number) {
  if (!Number.isFinite(value) || value < 0) return 0;
  return Math.round(value * 1000) / 1000;
}

function parseTimecode(raw: string): number {
  const value = raw.trim().replace(",", ".");
  if (!value) return 0;
  if (/^\d+(\.\d+)?$/.test(value)) return clampSeconds(Number(value));
  const parts = value.split(":").map(Number);
  if (parts.some((part) => Number.isNaN(part))) return 0;
  if (parts.length === 2) return clampSeconds(parts[0] * 60 + parts[1]);
  if (parts.length === 3) return clampSeconds(parts[0] * 3600 + parts[1] * 60 + parts[2]);
  return 0;
}

function formatVttTime(seconds: number): string {
  const safe = clampSeconds(seconds);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = Math.floor(safe % 60);
  const millis = Math.round((safe - Math.floor(safe)) * 1000);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(millis).padStart(3, "0")}`;
}

function formatSrtTime(seconds: number): string {
  return formatVttTime(seconds).replace(".", ",");
}

function captionsToVtt(captions: Caption[]): string {
  const body = captions
    .slice()
    .sort((a, b) => a.start - b.start)
    .map((caption) => `${formatVttTime(caption.start)} --> ${formatVttTime(caption.end)}\n${caption.text.trim()}`)
    .join("\n\n");
  return `WEBVTT\n\n${body}\n`;
}

function captionsToSrt(captions: Caption[]): string {
  return captions
    .slice()
    .sort((a, b) => a.start - b.start)
    .map((caption, index) => `${index + 1}\n${formatSrtTime(caption.start)} --> ${formatSrtTime(caption.end)}\n${caption.text.trim()}`)
    .join("\n\n") + "\n";
}

function parseCaptionFile(contents: string): Caption[] {
  const normalized = contents.replace(/\r/g, "").trim();
  const blocks = normalized
    .replace(/^WEBVTT(?:\n|$)/i, "")
    .split(/\n\s*\n/g)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.flatMap((block, index) => {
    const lines = block.split("\n").filter(Boolean);
    const timingIndex = lines.findIndex((line) => line.includes("-->"));
    if (timingIndex < 0) return [];
    const [startRaw, endRaw] = lines[timingIndex].split("-->").map((part) => part.trim().split(/\s+/)[0]);
    const text = lines.slice(timingIndex + 1).join("\n").trim();
    if (!text) return [];
    const start = parseTimecode(startRaw);
    const end = Math.max(start + 0.5, parseTimecode(endRaw));
    return [{ id: `import-${Date.now()}-${index}`, start, end, text }];
  });
}

function downloadBlob(filename: string, mime: string, contents: BlobPart[]) {
  const blob = new Blob(contents, { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function splitTranscriptToCaptions(transcript: string, duration: number): Caption[] {
  const words = transcript.split(/\s+/).map((word) => word.trim()).filter(Boolean);
  if (!words.length) return [];
  const chunks: string[] = [];
  for (let index = 0; index < words.length; index += 9) chunks.push(words.slice(index, index + 9).join(" "));
  const targetDuration = duration > 0 ? duration : Math.max(chunks.length * 2.5, 12);
  const segment = Math.max(1.5, targetDuration / chunks.length);
  return chunks.map((chunk, index) => {
    const start = clampSeconds(index * segment);
    return {
      id: `draft-${Date.now()}-${index}`,
      start,
      end: clampSeconds(Math.max(start + 0.5, Math.min(targetDuration, (index + 1) * segment))),
      text: chunk,
    };
  });
}

function activeCaptionAt(captions: Caption[], time: number) {
  return captions.find((caption) => time >= caption.start && time <= caption.end) || null;
}

function transitionStyle(caption: Caption | null, time: number, style: CaptionStyle) {
  if (!caption || style.effect === "none") return { opacity: 1, transform: "translateY(0) scale(1)" };
  const fadeIn = Math.min(1, Math.max(0, (time - caption.start) / 0.28));
  const fadeOut = Math.min(1, Math.max(0, (caption.end - time) / 0.28));
  const eased = Math.min(fadeIn, fadeOut);
  if (style.effect === "fade") return { opacity: eased, transform: "translateY(0) scale(1)" };
  if (style.effect === "pop") return { opacity: eased, transform: `translateY(0) scale(${0.92 + 0.08 * eased})` };
  return { opacity: eased, transform: `translateY(${(1 - eased) * 16}px) scale(1)` };
}

function wrapCanvasText(context: CanvasRenderingContext2D, text: string, maxWidth: number) {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (context.measureText(candidate).width <= maxWidth || !current) current = candidate;
    else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines;
}

function rgba(hex: string, opacity: number) {
  if (hex.startsWith("#") && (hex.length === 7 || hex.length === 9)) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const a = hex.length === 9 ? parseInt(hex.slice(7, 9), 16) / 255 : 1;
    return `rgba(${r}, ${g}, ${b}, ${Math.max(0, Math.min(1, a * opacity))})`;
  }
  return hex;
}

function drawCaption(context: CanvasRenderingContext2D, canvas: HTMLCanvasElement, caption: Caption | null, time: number, style: CaptionStyle) {
  if (!caption) return;
  const transition = transitionStyle(caption, time, style);
  const fontSize = Math.max(14, Math.round((style.fontSize / 720) * canvas.height));
  const paddingX = Math.round(fontSize * 0.55);
  const paddingY = Math.round(fontSize * 0.34);
  const maxWidth = canvas.width * 0.86;

  context.save();
  context.globalAlpha = transition.opacity;
  context.font = `${style.fontWeight} ${fontSize}px ${style.fontFamily}`;
  context.textAlign = style.align;
  context.textBaseline = "middle";
  context.shadowColor = style.shadowColor;
  context.shadowBlur = Math.round(fontSize * 0.18);

  const lines = wrapCanvasText(context, caption.text, maxWidth);
  const lineHeight = Math.round(fontSize * 1.18);
  const boxWidth = Math.min(maxWidth, Math.max(...lines.map((line) => context.measureText(line).width), 0)) + paddingX * 2;
  const boxHeight = lines.length * lineHeight + paddingY * 2;
  const x = style.align === "left" ? canvas.width * 0.07 : style.align === "right" ? canvas.width * 0.93 : canvas.width / 2;
  const y = style.position === "top" ? canvas.height * 0.16 : style.position === "middle" ? canvas.height * 0.5 : canvas.height * 0.84;
  const offsetY = style.effect === "slide" ? (1 - transition.opacity) * fontSize * 0.5 : 0;
  const scale = style.effect === "pop" ? 0.92 + 0.08 * transition.opacity : 1;
  const boxX = style.align === "left" ? x - paddingX : style.align === "right" ? x - boxWidth + paddingX : x - boxWidth / 2;
  const boxY = y - boxHeight / 2 + offsetY;

  context.translate(x, y + offsetY);
  context.scale(scale, scale);
  context.translate(-x, -(y + offsetY));
  context.fillStyle = rgba(style.backgroundColor, transition.opacity);
  context.beginPath();
  context.roundRect(boxX, boxY, boxWidth, boxHeight, Math.max(12, fontSize * 0.28));
  context.fill();

  context.fillStyle = style.color;
  lines.forEach((line, index) => {
    const lineY = boxY + paddingY + lineHeight / 2 + index * lineHeight;
    context.fillText(line, x, lineY, maxWidth);
  });
  context.restore();
}

async function waitForEvent(target: EventTarget, eventName: string) {
  await new Promise<void>((resolve) => target.addEventListener(eventName, () => resolve(), { once: true }));
}

export default function Home() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState<string>("");
  const [videoName, setVideoName] = useState<string>("");
  const [duration, setDuration] = useState<number>(0);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [captions, setCaptions] = useState<Caption[]>(starterCaptions);
  const [start, setStart] = useState("00:00:00.000");
  const [end, setEnd] = useState("00:00:03.000");
  const [text, setText] = useState("Type a caption line here");
  const [transcript, setTranscript] = useState("Upload a video, then click Transcribe to extract its text with Venice Whisper. You can also paste text here and draft cues manually.");
  const [captionStyle, setCaptionStyle] = useState<CaptionStyle>(defaultStyle);
  const [status, setStatus] = useState<string>("");
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isRendering, setIsRendering] = useState(false);

  const sortedCaptions = useMemo(() => captions.slice().sort((a, b) => a.start - b.start), [captions]);
  const wordCount = useMemo(() => captions.reduce((sum, caption) => sum + caption.text.split(/\s+/).filter(Boolean).length, 0), [captions]);
  const activeCaption = activeCaptionAt(sortedCaptions, currentTime);
  const liveTransition = transitionStyle(activeCaption, currentTime, captionStyle);

  useEffect(() => () => {
    if (videoUrl) URL.revokeObjectURL(videoUrl);
  }, [videoUrl]);

  function handleVideoUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoFile(file);
    setVideoName(file.name);
    setDuration(0);
    setCurrentTime(0);
    setVideoUrl(URL.createObjectURL(file));
    setStatus("Video loaded locally. Click Transcribe to extract captions, or edit manually.");
  }

  function handleCaptionImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const imported = parseCaptionFile(String(reader.result ?? ""));
      if (imported.length > 0) {
        setCaptions(imported);
        setStatus(`Imported ${imported.length} caption cues.`);
      }
    };
    reader.readAsText(file);
  }

  function addCaption(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedStart = parseTimecode(start);
    const parsedEnd = Math.max(parsedStart + 0.5, parseTimecode(end));
    const cleaned = text.trim();
    if (!cleaned) return;
    setCaptions((current) => [...current, { id: `caption-${Date.now()}`, start: parsedStart, end: parsedEnd, text: cleaned }]);
    setStart(formatVttTime(parsedEnd));
    setEnd(formatVttTime(parsedEnd + 3));
    setText("");
  }

  function updateCaption(id: string, patch: Partial<Caption>) {
    setCaptions((current) => current.map((caption) => (caption.id === id ? { ...caption, ...patch } : caption)));
  }

  function seekTo(seconds: number) {
    if (!videoRef.current) return;
    videoRef.current.currentTime = seconds;
    void videoRef.current.play();
  }

  function useCurrentTime(which: "start" | "end") {
    const current = formatVttTime(videoRef.current?.currentTime ?? 0);
    if (which === "start") setStart(current);
    else setEnd(current);
  }

  function createDraftFromTranscript() {
    const draft = splitTranscriptToCaptions(transcript, duration);
    if (!draft.length) return;
    setCaptions(draft);
    setStatus(`Created ${draft.length} timed cues from transcript text.`);
  }

  async function transcribeVideo() {
    if (!videoFile) {
      setStatus("Upload a video first.");
      return;
    }
    setIsTranscribing(true);
    setStatus("Extracting audio and transcribing with Venice Whisper…");
    try {
      const form = new FormData();
      form.append("video", videoFile);
      form.append("duration", String(duration || 0));
      const response = await fetch("/api/transcribe", { method: "POST", body: form });
      const payload = await response.json() as TranscriptionResponse;
      if (!response.ok) throw new Error(payload.error || "Transcription failed.");
      setTranscript(payload.text || "");
      if (payload.captions?.length) setCaptions(payload.captions);
      setStatus(`Transcribed with ${payload.model}; ${payload.captions?.length || 0} cues drafted.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Transcription failed.");
    } finally {
      setIsTranscribing(false);
    }
  }

  async function renderBurnedInVideo() {
    if (!videoUrl || !videoFile) {
      setStatus("Upload a video first.");
      return;
    }
    if (!sortedCaptions.length) {
      setStatus("Add at least one caption before rendering.");
      return;
    }

    setIsRendering(true);
    setStatus("Rendering captioned video in your browser. This runs in real time for the video duration…");

    const renderVideo = document.createElement("video");
    renderVideo.src = videoUrl;
    renderVideo.playsInline = true;
    renderVideo.preload = "auto";
    renderVideo.volume = 1;

    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    if (!context) {
      setStatus("Canvas rendering is not available in this browser.");
      setIsRendering(false);
      return;
    }

    const chunks: Blob[] = [];
    let audioContext: AudioContext | null = null;
    let animationId = 0;

    try {
      await waitForEvent(renderVideo, "loadedmetadata");
      canvas.width = renderVideo.videoWidth || 1280;
      canvas.height = renderVideo.videoHeight || 720;

      const stream = canvas.captureStream(30);
      try {
        audioContext = new AudioContext();
        const source = audioContext.createMediaElementSource(renderVideo);
        const destination = audioContext.createMediaStreamDestination();
        source.connect(destination);
        destination.stream.getAudioTracks().forEach((track) => stream.addTrack(track));
      } catch {
        // Some browsers block media-element audio capture. Video export still works without audio.
      }

      const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
        ? "video/webm;codecs=vp9,opus"
        : "video/webm;codecs=vp8,opus";
      const recorder = new MediaRecorder(stream, { mimeType: mime });
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };

      const draw = () => {
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.drawImage(renderVideo, 0, 0, canvas.width, canvas.height);
        drawCaption(context, canvas, activeCaptionAt(sortedCaptions, renderVideo.currentTime), renderVideo.currentTime, captionStyle);
        if (!renderVideo.ended) animationId = requestAnimationFrame(draw);
      };

      renderVideo.currentTime = 0;
      await waitForEvent(renderVideo, "seeked");
      recorder.start(750);
      draw();
      await renderVideo.play();
      await waitForEvent(renderVideo, "ended");
      cancelAnimationFrame(animationId);
      recorder.stop();
      await waitForEvent(recorder, "stop");

      downloadBlob(`${videoName.replace(/\.[^.]+$/, "") || "captionator"}-captioned.webm`, "video/webm", chunks);
      setStatus("Rendered and downloaded a captioned WebM video.");
    } catch (error) {
      cancelAnimationFrame(animationId);
      setStatus(error instanceof Error ? error.message : "Video rendering failed.");
    } finally {
      renderVideo.removeAttribute("src");
      renderVideo.load();
      await audioContext?.close().catch(() => undefined);
      setIsRendering(false);
    }
  }

  const overlayStyle = {
    color: captionStyle.color,
    backgroundColor: captionStyle.backgroundColor,
    fontFamily: captionStyle.fontFamily,
    fontSize: `${captionStyle.fontSize}px`,
    fontWeight: captionStyle.fontWeight,
    textShadow: `0 4px 18px ${captionStyle.shadowColor}`,
    textAlign: captionStyle.align,
    opacity: liveTransition.opacity,
    transform: liveTransition.transform,
  } as const;

  return (
    <main>
      <section className="hero">
        <div className="eyebrow">AI transcription + burned-in captions</div>
        <h1>Captionator turns uploads into captioned videos.</h1>
        <p>
          Upload any local video, extract a transcript with Venice Whisper, edit the cue text and timing, style how captions
          appear on-screen, then render a downloadable captioned WebM directly in the browser.
        </p>
        <div className="actions">
          <label className="primaryButton">
            Upload video
            <input type="file" accept="video/*,audio/*" onChange={handleVideoUpload} />
          </label>
          <button className="secondaryButton" onClick={transcribeVideo} disabled={isTranscribing || !videoFile}>
            {isTranscribing ? "Transcribing…" : "Transcribe uploaded video"}
          </button>
          <label className="secondaryButton">
            Import VTT/SRT
            <input type="file" accept=".vtt,.srt,text/vtt,text/plain" onChange={handleCaptionImport} />
          </label>
        </div>
        {status ? <p className="status">{status}</p> : null}
      </section>

      <section className="grid">
        <div className="panel videoPanel">
          <div className="panelHeader">
            <div>
              <span className="label">Preview</span>
              <h2>{videoName || "No video uploaded yet"}</h2>
            </div>
            <span className="pill">{duration ? formatVttTime(duration) : "local preview"}</span>
          </div>
          {videoUrl ? (
            <div className={`videoFrame ${captionStyle.position}`}>
              <video
                ref={videoRef}
                controls
                className="video"
                src={videoUrl}
                onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)}
                onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
                onSeeked={(event) => setCurrentTime(event.currentTarget.currentTime)}
              />
              {activeCaption ? <div className={`captionOverlay ${captionStyle.position}`} style={overlayStyle}>{activeCaption.text}</div> : null}
            </div>
          ) : (
            <div className="emptyVideo">
              <div className="playIcon">▶</div>
              <p>Upload an MP4, MOV, or WebM to extract speech and preview captions over the video.</p>
            </div>
          )}
          <div className="stats">
            <div><strong>{captions.length}</strong><span>cues</span></div>
            <div><strong>{wordCount}</strong><span>words</span></div>
            <div><strong>{duration ? Math.round(duration) : "—"}</strong><span>seconds</span></div>
          </div>
        </div>

        <div className="panel">
          <div className="panelHeader">
            <div>
              <span className="label">Transcript</span>
              <h2>Extract or paste source text</h2>
            </div>
          </div>
          <textarea className="transcript" value={transcript} onChange={(event) => setTranscript(event.target.value)} />
          <button className="fullButton" onClick={createDraftFromTranscript}>Generate timed draft captions</button>
          <p className="hint">Venice Whisper returns text and, when available, segment timestamps. Manual drafts split pasted text across the video duration.</p>
        </div>
      </section>

      <section className="panel stylePanel">
        <div className="panelHeader">
          <div>
            <span className="label">Appearance</span>
            <h2>Style captions for the final video</h2>
          </div>
        </div>
        <div className="styleGrid">
          <label>Font
            <select value={captionStyle.fontFamily} onChange={(event) => setCaptionStyle({ ...captionStyle, fontFamily: event.target.value })}>
              <option value="Inter, Arial, sans-serif">Inter</option>
              <option value="Georgia, serif">Georgia</option>
              <option value="Impact, Haettenschweiler, sans-serif">Impact</option>
              <option value="Courier New, monospace">Courier</option>
            </select>
          </label>
          <label>Size
            <input type="range" min="22" max="86" value={captionStyle.fontSize} onChange={(event) => setCaptionStyle({ ...captionStyle, fontSize: Number(event.target.value) })} />
            <span>{captionStyle.fontSize}px</span>
          </label>
          <label>Weight
            <select value={captionStyle.fontWeight} onChange={(event) => setCaptionStyle({ ...captionStyle, fontWeight: event.target.value })}>
              <option value="500">Medium</option>
              <option value="700">Bold</option>
              <option value="800">Extra bold</option>
              <option value="900">Black</option>
            </select>
          </label>
          <label>Text color
            <input type="color" value={captionStyle.color} onChange={(event) => setCaptionStyle({ ...captionStyle, color: event.target.value })} />
          </label>
          <label>Background
            <input type="color" value={captionStyle.backgroundColor.slice(0, 7)} onChange={(event) => setCaptionStyle({ ...captionStyle, backgroundColor: `${event.target.value}cc` })} />
          </label>
          <label>Position
            <select value={captionStyle.position} onChange={(event) => setCaptionStyle({ ...captionStyle, position: event.target.value as CaptionStyle["position"] })}>
              <option value="bottom">Bottom</option>
              <option value="middle">Middle</option>
              <option value="top">Top</option>
            </select>
          </label>
          <label>Align
            <select value={captionStyle.align} onChange={(event) => setCaptionStyle({ ...captionStyle, align: event.target.value as CaptionStyle["align"] })}>
              <option value="center">Center</option>
              <option value="left">Left</option>
              <option value="right">Right</option>
            </select>
          </label>
          <label>Transition
            <select value={captionStyle.effect} onChange={(event) => setCaptionStyle({ ...captionStyle, effect: event.target.value as CaptionStyle["effect"] })}>
              <option value="fade">Fade</option>
              <option value="pop">Pop</option>
              <option value="slide">Slide</option>
              <option value="none">None</option>
            </select>
          </label>
        </div>
      </section>

      <section className="panel editorPanel">
        <div className="panelHeader">
          <div>
            <span className="label">Cue editor</span>
            <h2>Add and tune captions</h2>
          </div>
          <div className="exportButtons">
            <button onClick={() => downloadBlob("captionator-captions.vtt", "text/vtt", [captionsToVtt(sortedCaptions)])}>Export VTT</button>
            <button onClick={() => downloadBlob("captionator-captions.srt", "text/plain", [captionsToSrt(sortedCaptions)])}>Export SRT</button>
            <button onClick={() => downloadBlob("captionator-captions.json", "application/json", [JSON.stringify(sortedCaptions, null, 2)])}>Export JSON</button>
            <button className="renderButton" onClick={renderBurnedInVideo} disabled={isRendering || !videoFile}>{isRendering ? "Rendering…" : "Download captioned video"}</button>
          </div>
        </div>

        <form className="cueForm" onSubmit={addCaption}>
          <label>
            Start
            <input value={start} onChange={(event) => setStart(event.target.value)} />
            <button type="button" onClick={() => useCurrentTime("start")}>Use player time</button>
          </label>
          <label>
            End
            <input value={end} onChange={(event) => setEnd(event.target.value)} />
            <button type="button" onClick={() => useCurrentTime("end")}>Use player time</button>
          </label>
          <label className="captionText">
            Caption
            <textarea value={text} onChange={(event) => setText(event.target.value)} />
          </label>
          <button className="addButton" type="submit">Add cue</button>
        </form>

        <div className="cueList">
          {sortedCaptions.map((caption, index) => (
            <article className="cue" key={caption.id}>
              <button className="cueIndex" onClick={() => seekTo(caption.start)}>{index + 1}</button>
              <div className="cueFields">
                <div className="timeRow">
                  <input aria-label={`Caption ${index + 1} start`} value={formatVttTime(caption.start)} onChange={(event) => updateCaption(caption.id, { start: parseTimecode(event.target.value) })} />
                  <span>→</span>
                  <input aria-label={`Caption ${index + 1} end`} value={formatVttTime(caption.end)} onChange={(event) => updateCaption(caption.id, { end: parseTimecode(event.target.value) })} />
                </div>
                <textarea aria-label={`Caption ${index + 1} text`} value={caption.text} onChange={(event) => updateCaption(caption.id, { text: event.target.value })} />
              </div>
              <button className="deleteButton" onClick={() => setCaptions((current) => current.filter((item) => item.id !== caption.id))}>Delete</button>
            </article>
          ))}
        </div>
      </section>

      <section className="panel roadmap">
        <span className="label">Architecture</span>
        <h2>Built for uploaded videos without storing user media</h2>
        <div className="cards">
          <div><strong>Speech extraction</strong><p>The API temporarily extracts compressed audio with FFmpeg, sends it to Venice Whisper, then deletes local temp files.</p></div>
          <div><strong>Private editing</strong><p>The video preview, styling, cue edits, and burned-in render happen in the user browser from the local upload.</p></div>
          <div><strong>Downloadable output</strong><p>Exports include VTT/SRT/JSON plus a real-time browser-rendered WebM with captions drawn onto the frames.</p></div>
        </div>
      </section>
    </main>
  );
}
