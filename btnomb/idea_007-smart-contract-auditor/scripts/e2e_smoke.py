#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

VULNERABLE_SOURCE = """
pragma solidity ^0.8.20;
contract Vault {
    mapping(address => uint256) public balances;
    address public owner;
    constructor() { owner = msg.sender; }
    function deposit() external payable { balances[msg.sender] += msg.value; }
    function withdraw() external {
        uint256 amount = balances[msg.sender];
        (bool ok, ) = msg.sender.call{value: amount}("");
        balances[msg.sender] = 0;
    }
    function adminSweep(address payable to) external {
        require(tx.origin == owner, "not owner");
        to.transfer(address(this).balance);
    }
    function drawWinner(address[] memory users) external view returns (address) {
        return users[block.timestamp % users.length];
    }
}
"""


def request(method: str, url: str, *, headers: dict[str, str] | None = None, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, method=method, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw[:500]
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw[:500]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live HTTP E2E smoke checks for the smart-contract auditor service.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="dev-audit-key")
    parser.add_argument("--out", default="evidence/e2e-smoke.json")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    headers = {"X-API-Key": args.api_key}
    started = time.time()
    checks: list[dict[str, Any]] = []

    for name, method, path, extra_headers, body, expect in [
        ("health", "GET", "/health", {}, None, 200),
        ("readiness", "GET", "/ready", {}, None, 200),
        ("preview", "POST", "/audit", headers, {"contract_name": "Vault", "source": VULNERABLE_SOURCE, "preview": True}, 200),
        ("payment_required", "POST", "/audit", headers, {"contract_name": "Vault", "source": VULNERABLE_SOURCE}, 402),
        ("paid_audit", "POST", "/audit", {**headers, "X-PAYMENT": "demo-smoke-proof"}, {"contract_name": "Vault", "source": VULNERABLE_SOURCE}, 200),
    ]:
        status, body_out = request(method, f"{base}{path}", headers=extra_headers, body=body)
        check: dict[str, Any] = {"name": name, "method": method, "path": path, "status": status, "expected": expect, "ok": status == expect}
        if isinstance(body_out, dict):
            if name == "paid_audit":
                check["audit_id"] = body_out.get("audit_id")
                check["finding_count"] = len(body_out.get("findings", []))
                check["top_severity"] = (body_out.get("findings") or [{}])[0].get("severity")
            elif name == "readiness":
                check["production_ready"] = body_out.get("checks", {}).get("production_ready")
                check["checks"] = body_out.get("checks", {})
            elif name == "preview":
                check["preview"] = body_out.get("preview")
                check["severity_summary"] = body_out.get("severity_summary")
            elif name == "payment_required":
                check["x402Version"] = body_out.get("x402Version")
                accepts = body_out.get("accepts") or [{}]
                check["network"] = accepts[0].get("network")
                check["amount"] = accepts[0].get("maxAmountRequired")
        checks.append(check)

    audit_id = next((c.get("audit_id") for c in checks if c.get("audit_id")), None)
    if audit_id:
        for suffix in ["", ".md", ".html", ".pdf"]:
            status, report = request("GET", f"{base}/reports/{audit_id}{suffix}", headers=headers)
            checks.append({"name": f"report{suffix or '.json'}", "method": "GET", "path": f"/reports/{audit_id}{suffix}", "status": status, "expected": 200, "ok": status == 200, "body_present": bool(report)})
        status, history = request("GET", f"{base}/history", headers=headers)
        checks.append({"name": "history", "method": "GET", "path": "/history", "status": status, "expected": 200, "ok": status == 200, "audit_seen": isinstance(history, dict) and any(row.get("audit_id") == audit_id for row in history.get("audits", []))})

    result = {
        "base_url": base,
        "elapsed_seconds": round(time.time() - started, 3),
        "under_90_seconds": time.time() - started < 90,
        "passed": all(c.get("ok") for c in checks),
        "checks": checks,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
