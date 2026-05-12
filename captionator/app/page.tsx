
"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

type Caption = {
  id: string;
  start: number;
  end: number;
  text: string;
};

const starterCaptions: Caption[] = [
  { id: "sample-1", start: 0, end: 2.8, text: "Welcome to Captionator." },
  { id: "sample-2", start: 2.8, end: 6.2, text: "Upload a video, draft captions, and preview timing instantly." },
  { id: "sample-3", start: 6.2, end: 9.4, text: "Export WebVTT or SRT when you are ready." },
];

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

function downloadText(filename: string, mime: string, contents: string) {
  const blob = new Blob([contents], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export default function Home() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [videoUrl, setVideoUrl] = useState<string>("");
  const [videoName, setVideoName] = useState<string>("");
  const [duration, setDuration] = useState<number>(0);
  const [captions, setCaptions] = useState<Caption[]>(starterCaptions);
  const [trackUrl, setTrackUrl] = useState<string>("");
  const [start, setStart] = useState("00:00:00.000");
  const [end, setEnd] = useState("00:00:03.000");
  const [text, setText] = useState("Type a caption line here");
  const [transcript, setTranscript] = useState("Paste a transcript here, one caption per line.\nCaptionator will create timed draft cues you can refine.");

  const sortedCaptions = useMemo(() => captions.slice().sort((a, b) => a.start - b.start), [captions]);
  const wordCount = useMemo(() => captions.reduce((sum, caption) => sum + caption.text.split(/\s+/).filter(Boolean).length, 0), [captions]);

  useEffect(() => {
    const blob = new Blob([captionsToVtt(sortedCaptions)], { type: "text/vtt" });
    const url = URL.createObjectURL(blob);
    setTrackUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [sortedCaptions]);

  function handleVideoUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoName(file.name);
    setVideoUrl(URL.createObjectURL(file));
  }

  function handleCaptionImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const imported = parseCaptionFile(String(reader.result ?? ""));
      if (imported.length > 0) setCaptions(imported);
    };
    reader.readAsText(file);
  }

  function addCaption(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedStart = parseTimecode(start);
    const parsedEnd = Math.max(parsedStart + 0.5, parseTimecode(end));
    const cleaned = text.trim();
    if (!cleaned) return;
    setCaptions((current) => [
      ...current,
      { id: `caption-${Date.now()}`, start: parsedStart, end: parsedEnd, text: cleaned },
    ]);
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
    const lines = transcript.split("\n").map((line) => line.trim()).filter(Boolean);
    if (lines.length === 0) return;
    const targetDuration = duration > 0 ? duration : Math.max(lines.length * 3, 12);
    const segment = Math.max(1.5, targetDuration / lines.length);
    setCaptions(lines.map((line, index) => ({
      id: `draft-${Date.now()}-${index}`,
      start: clampSeconds(index * segment),
      end: clampSeconds(Math.min(targetDuration, (index + 1) * segment)),
      text: line,
    })));
  }

  return (
    <main>
      <section className="hero">
        <div className="eyebrow">Browser-first caption workflow</div>
        <h1>Captionator turns rough video uploads into clean caption files.</h1>
        <p>
          Upload a local video, draft captions from a transcript, tune cue timing in the browser, preview a WebVTT track,
          then export reviewer-ready VTT, SRT, or JSON without sending media to a server.
        </p>
        <div className="actions">
          <label className="primaryButton">
            Upload video
            <input type="file" accept="video/*" onChange={handleVideoUpload} />
          </label>
          <label className="secondaryButton">
            Import VTT/SRT
            <input type="file" accept=".vtt,.srt,text/vtt,text/plain" onChange={handleCaptionImport} />
          </label>
        </div>
      </section>

      <section className="grid">
        <div className="panel videoPanel">
          <div className="panelHeader">
            <div>
              <span className="label">Preview</span>
              <h2>{videoName || "No video uploaded yet"}</h2>
            </div>
            <span className="pill">{duration ? formatVttTime(duration) : "local only"}</span>
          </div>
          {videoUrl ? (
            <video
              ref={videoRef}
              controls
              className="video"
              src={videoUrl}
              onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)}
            >
              {trackUrl ? <track src={trackUrl} kind="captions" srcLang="en" label="Captionator" default /> : null}
            </video>
          ) : (
            <div className="emptyVideo">
              <div className="playIcon">▶</div>
              <p>Upload an MP4, MOV, or WebM to preview captions over the video.</p>
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
              <span className="label">Draft assistant</span>
              <h2>Make a first pass from transcript lines</h2>
            </div>
          </div>
          <textarea className="transcript" value={transcript} onChange={(event) => setTranscript(event.target.value)} />
          <button className="fullButton" onClick={createDraftFromTranscript}>Generate timed draft captions</button>
          <p className="hint">Draft cues are evenly distributed across the uploaded video duration, then you can refine each cue below.</p>
        </div>
      </section>

      <section className="panel editorPanel">
        <div className="panelHeader">
          <div>
            <span className="label">Cue editor</span>
            <h2>Add and tune captions</h2>
          </div>
          <div className="exportButtons">
            <button onClick={() => downloadText("captionator-captions.vtt", "text/vtt", captionsToVtt(sortedCaptions))}>Export VTT</button>
            <button onClick={() => downloadText("captionator-captions.srt", "text/plain", captionsToSrt(sortedCaptions))}>Export SRT</button>
            <button onClick={() => downloadText("captionator-captions.json", "application/json", JSON.stringify(sortedCaptions, null, 2))}>Export JSON</button>
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
        <span className="label">Production path</span>
        <h2>Why this MVP is safe for Vercel</h2>
        <div className="cards">
          <div><strong>Private by default</strong><p>Video files stay in the browser as object URLs; no server upload is required for the demo.</p></div>
          <div><strong>Accessible exports</strong><p>WebVTT and SRT downloads work with common editors, players, and social publishing tools.</p></div>
          <div><strong>Scalable next step</strong><p>Burned-in rendering can be added later through object storage and an external FFmpeg worker.</p></div>
        </div>
      </section>
    </main>
  );
}
