#!/usr/bin/env python3
"""Production smoke verifier for GitHub Activity Intelligence.

Runs against any live URL (local uvicorn, Docker, Render, Railway, Fly, etc.) using
only Python stdlib so reviewers can verify a deployed instance without pytest.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def request(base_url: str, method: str, path: str, *, api_key: str | None = None, body: dict[str, Any] | None = None, expected: int | tuple[int, ...] = 200) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    data = None
    headers = {"User-Agent": "github-activity-intelligence-smoke/1.0"}
    if api_key:
        headers["X-API-Key"] = api_key
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    expected_codes = (expected,) if isinstance(expected, int) else expected
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status
            content_type = resp.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        status = exc.code
        content_type = exc.headers.get("content-type", "")
    if status not in expected_codes:
        raise AssertionError(f"{method} {path} returned {status}, expected {expected_codes}: {raw[:500]}")
    if "application/json" in content_type or raw.strip().startswith(("{", "[")):
        parsed: Any = json.loads(raw)
    else:
        parsed = {"text": raw[:1000]}
    return {"status": status, "body": parsed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="dev-api-key")
    parser.add_argument("--out", default="samples/production-smoke-output.json")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    repo = f"reviewer/live-signal-{int(time.time())}"
    steps: list[dict[str, Any]] = []

    def record(name: str, result: dict[str, Any]) -> dict[str, Any]:
        steps.append({"name": name, **result})
        return result

    try:
        health = record("healthz", request(base_url, "GET", "/healthz"))
        ready = record("readyz", request(base_url, "GET", "/readyz"))
        assert health["body"]["status"] == "ok"
        assert ready["body"]["status"] == "ok"
        assert ready["body"]["checks"]["database_query"] is True

        seed = record(
            "seed_repo",
            request(
                base_url,
                "POST",
                "/repos/seed",
                api_key=args.api_key,
                body={
                    "full_name": repo,
                    "description": "LLM agent observability library for production smoke verification",
                    "language": "Python",
                    "stars": 80,
                    "forks": 8,
                    "open_issues": 18,
                    "watchers": 80,
                    "contributors": 4,
                    "commits": 45,
                },
                expected=201,
            ),
        )
        assert seed["body"]["full_name"] == repo

        for days, stars, forks, contributors, commits, issues in ((30, 80, 8, 4, 45, 18), (7, 120, 13, 8, 88, 14), (0, 240, 35, 18, 180, 7)):
            record(
                f"snapshot_{days}d",
                request(
                    base_url,
                    "POST",
                    "/snapshots",
                    api_key=args.api_key,
                    body={
                        "full_name": repo,
                        "stars": stars,
                        "forks": forks,
                        "open_issues": issues,
                        "contributors": contributors,
                        "commits": commits,
                        "created_at": (datetime.now(UTC) if days == 0 else datetime.now(UTC) - timedelta(days=days)).isoformat(),
                    },
                    expected=201,
                ),
            )

        recompute = record("scores_recompute", request(base_url, "POST", "/scores/recompute", api_key=args.api_key))
        assert recompute["body"]["repos_scored"] >= 1

        ranked = record("ranked_search", request(base_url, "GET", "/repos?category=AI/ML&q=agent&min_score=1&limit=5"))
        assert any(item["full_name"] == repo for item in ranked["body"]["repos"])

        detail = record("repo_detail", request(base_url, "GET", f"/repos/{urllib.parse.quote(repo, safe='/')}"))
        assert len(detail["body"]["snapshots"]) >= 3

        watch = record(
            "watchlist",
            request(base_url, "POST", "/watchlist", api_key=args.api_key, body={"email": "reviewer@example.com", "repo_full_name": repo, "threshold": 25}, expected=201),
        )
        assert watch["body"]["repo_full_name"] == repo

        alerts = record("alerts_evaluate", request(base_url, "POST", "/alerts/evaluate", api_key=args.api_key))
        assert alerts["body"]["alerts_created"] >= 1

        digest = record("weekly_digest", request(base_url, "POST", "/digest/weekly", api_key=args.api_key))
        assert digest["body"]["categories"] >= 1

        checkout = record("x402_checkout", request(base_url, "POST", "/plans/checkout", body={"plan": "pro"}, expected=402))
        assert checkout["body"]["accepts"][0]["network"] == "base"

        dashboard = record("dashboard", request(base_url, "GET", "/dashboard?q=live-signal"))
        assert repo in dashboard["body"]["text"]

        output = {
            "ok": True,
            "base_url": base_url,
            "repo_under_test": repo,
            "checks_passed": len(steps),
            "checks_total": len(steps),
            "checked_at": datetime.now(UTC).isoformat(),
            "steps": steps,
        }
    except Exception as exc:  # noqa: BLE001 - CLI smoke output should capture any failure.
        output = {
            "ok": False,
            "base_url": base_url,
            "checked_at": datetime.now(UTC).isoformat(),
            "error": str(exc),
            "steps": steps,
        }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"ok": output["ok"], "checks": f"{output.get('checks_passed', 0)}/{output.get('checks_total', len(steps))}", "out": str(out_path)}, sort_keys=True))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
