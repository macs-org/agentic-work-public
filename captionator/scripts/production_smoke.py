#!/usr/bin/env python3
"""Smoke-test the Captionator public Vercel root URL."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: production_smoke.py https://captionator.example.vercel.app", file=sys.stderr)
        return 2

    url = sys.argv[1].rstrip("/") + "/"
    req = urllib.request.Request(url, headers={"User-Agent": "CaptionatorSmoke/1.0"})
    started = time.time()
    with urllib.request.urlopen(req, timeout=60) as response:
        html = response.read().decode("utf-8", "replace")
        status = response.status

    checks = {
        "status_200": status == 200,
        "has_title": "Captionator" in html,
        "has_upload_copy": "Upload video" in html,
        "has_transcription_copy": "Transcribe uploaded video" in html,
        "has_style_copy": "Style captions for the final video" in html,
        "has_video_download_copy": "Download captioned video" in html,
        "has_export_copy": "Export VTT" in html,
    }
    result = {
        "url": url,
        "status": status,
        "elapsed_ms": round((time.time() - started) * 1000),
        "checks": checks,
        "ok": all(checks.values()),
        "html_preview": html[:500],
    }
    out = Path("samples/production-smoke-vercel.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
