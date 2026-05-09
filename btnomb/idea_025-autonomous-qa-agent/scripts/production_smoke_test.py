#!/usr/bin/env python3
"""Production smoke test for the Autonomous QA Agent BTNOMB deliverable.

Usage:
  AUTONOMOUS_QA_BASE_URL=https://your-service.example python3 scripts/production_smoke_test.py

The script uses only the Python standard library so it can run from CI/CD, Render
shell, Railway shell, Fly console, or a local Docker container without installing
extra client packages.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = os.getenv("AUTONOMOUS_QA_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = float(os.getenv("AUTONOMOUS_QA_SMOKE_TIMEOUT", "10"))


def request(method: str, path: str, body: dict[str, Any] | None = None, api_key: str | None = None) -> tuple[int, dict[str, Any] | str]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode()
            try:
                parsed: dict[str, Any] | str = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = raw
            return resp.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed: dict[str, Any] | str = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def load_demo_suite() -> str:
    sample = Path(__file__).resolve().parents[1] / "samples" / "demo_suite.yaml"
    return sample.read_text()


def check(name: str, ok: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def main() -> int:
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    checks: list[dict[str, Any]] = []

    status, health = request("GET", "/healthz")
    checks.append(check("healthz", status == 200 and isinstance(health, dict) and health.get("status") == "ok", {"status": status, "body": health}))

    status, ready = request("GET", "/readyz")
    checks.append(check("readyz", status == 200 and isinstance(ready, dict) and ready.get("status") == "ready", {"status": status, "body": ready}))

    status, agent = request("POST", "/agents", {"name": "production-smoke", "plan": "starter"})
    api_key = agent.get("api_key") if isinstance(agent, dict) else None
    agent_id = agent.get("agent_id") if isinstance(agent, dict) else None
    checks.append(check("create_agent", status == 201 and bool(api_key), {"status": status, "agent_id": agent_id, "api_key_present": bool(api_key)}))
    if not api_key:
        result = {"base_url": BASE_URL, "started_at": started, "ok": False, "checks": checks}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    status, suite = request("POST", "/suites", {"definition": load_demo_suite()}, api_key)
    suite_id = suite.get("suite_id") if isinstance(suite, dict) else None
    checks.append(check("create_suite", status == 201 and bool(suite_id), {"status": status, "suite_id": suite_id, "case_count": suite.get("case_count") if isinstance(suite, dict) else None}))

    status, run = request("POST", f"/suites/{suite_id}/run", api_key=api_key)
    checks.append(check("manual_run", status == 201 and isinstance(run, dict) and run.get("status") == "passed", {"status": status, "run_status": run.get("status") if isinstance(run, dict) else None, "passed": run.get("passed") if isinstance(run, dict) else None, "total": run.get("total") if isinstance(run, dict) else None}))

    status, schedules = request("GET", "/schedules", api_key=api_key)
    checks.append(check("schedules", status == 200 and isinstance(schedules, dict) and len(schedules.get("schedules", [])) >= 1, {"status": status, "count": len(schedules.get("schedules", [])) if isinstance(schedules, dict) else None}))

    status, summary = request("GET", "/reports/summary", api_key=api_key)
    checks.append(check("reports_summary", status == 200 and isinstance(summary, dict) and len(summary.get("suites", [])) >= 1, {"status": status, "suites": len(summary.get("suites", [])) if isinstance(summary, dict) else None}))

    status, checkout = request("POST", "/plans/checkout", {"plan": "pro"}, api_key)
    x402_ok = status == 402 and isinstance(checkout, dict) and checkout.get("x402Version") == 1 and checkout.get("accepts", [{}])[0].get("network") == "base"
    checks.append(check("x402_checkout", x402_ok, {"status": status, "network": checkout.get("accepts", [{}])[0].get("network") if isinstance(checkout, dict) else None}))

    status, dashboard = request("GET", "/dashboard", api_key=api_key)
    dashboard_ok = status == 200 and isinstance(dashboard, str) and "Autonomous QA Agent" in dashboard
    checks.append(check("dashboard", dashboard_ok, {"status": status, "contains_title": dashboard_ok}))

    ok = all(item["ok"] for item in checks)
    result = {"base_url": BASE_URL, "started_at": started, "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ok": ok, "checks": checks}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
