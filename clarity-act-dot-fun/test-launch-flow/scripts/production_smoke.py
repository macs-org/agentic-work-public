#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PATHS = [
    "/",
    "/health",
    "/ready",
    "/token/create",
    "/forms/demo/offering-statement",
    "/forms/demo/purchaser-information",
    "/reports/0xDemo/semiannual/2026-H1",
    "/certifications/0xDemo/maturity",
    "/token/0xDemo",
]


def check(base_url: str, path: str) -> dict:
    url = base_url.rstrip("/") + path
    try:
        req = Request(url, headers={"User-Agent": "clarity-act-dot-fun-smoke/1.0"})
        with urlopen(req, timeout=20) as response:
            body = response.read(1200).decode("utf-8", errors="replace")
            status = response.getcode()
            return {"path": path, "url": url, "status": status, "ok": status == 200, "sample": body[:240]}
    except HTTPError as exc:
        return {"path": path, "url": url, "status": exc.code, "ok": False, "error": str(exc)}
    except URLError as exc:
        return {"path": path, "url": url, "status": None, "ok": False, "error": str(exc)}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: production_smoke.py <production-url>", file=sys.stderr)
        return 2
    base_url = sys.argv[1].rstrip("/")
    checks = [check(base_url, path) for path in PATHS]
    payload = {
        "base_url": base_url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "all_ok": all(item["ok"] for item in checks),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
