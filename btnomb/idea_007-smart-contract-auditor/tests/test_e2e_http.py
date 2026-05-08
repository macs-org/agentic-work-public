from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_KEY = "e2e-secret-key"
PAY_TO = "0x23bB05603A980C2915FC3B9D5D4a475993b666DE"

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


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request(method: str, url: str, *, headers: dict[str, str] | None = None, body: dict | None = None) -> tuple[int, dict | str]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, method=method, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def wait_for_ready(base_url: str, timeout_seconds: int = 20) -> dict:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, body = request("GET", f"{base_url}/ready")
            if status == 200 and isinstance(body, dict):
                return body
        except Exception as exc:  # noqa: BLE001 - startup polling diagnostic
            last_error = exc
        time.sleep(0.25)
    raise AssertionError(f"server did not become ready; last_error={last_error}")


def test_real_http_end_to_end_flow(tmp_path: Path):
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update({
        "AUDITOR_API_KEY": API_KEY,
        "X402_PAY_TO": PAY_TO,
        "AUDIT_HISTORY_PATH": str(tmp_path / "audit_history.jsonl"),
        "PYTHONPATH": ".",
    })
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        ready = wait_for_ready(base_url)
        assert ready["status"] == "ready"
        assert ready["checks"]["production_ready"] is True
        assert ready["checks"]["api_key_configured"] is True
        assert ready["checks"]["x402_pay_to_configured"] is True

        start = time.perf_counter()
        preview_status, preview = request(
            "POST",
            f"{base_url}/audit",
            headers={"X-API-Key": API_KEY},
            body={"contract_name": "Vault", "source": VULNERABLE_SOURCE, "preview": True},
        )
        assert preview_status == 200
        assert isinstance(preview, dict)
        assert preview["preview"] is True
        assert preview["findings"] == []

        payment_status, payment_required = request(
            "POST",
            f"{base_url}/audit",
            headers={"X-API-Key": API_KEY},
            body={"contract_name": "Vault", "source": VULNERABLE_SOURCE},
        )
        assert payment_status == 402
        assert isinstance(payment_required, dict)
        assert payment_required["accepts"][0]["payTo"] == PAY_TO

        audit_status, audit = request(
            "POST",
            f"{base_url}/audit",
            headers={"X-API-Key": API_KEY, "X-PAYMENT": "demo-e2e-proof"},
            body={"contract_name": "Vault", "source": VULNERABLE_SOURCE},
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 90
        assert audit_status == 200
        assert isinstance(audit, dict)
        assert audit["findings"][0]["severity"] == "Critical"
        audit_id = audit["audit_id"]

        for suffix in ["", ".md", ".html", ".pdf"]:
            status, report = request("GET", f"{base_url}/reports/{audit_id}{suffix}", headers={"X-API-Key": API_KEY})
            assert status == 200
            assert report

        history_status, history = request("GET", f"{base_url}/history", headers={"X-API-Key": API_KEY})
        assert history_status == 200
        assert isinstance(history, dict)
        assert history["audits"][0]["audit_id"] == audit_id
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        if proc.returncode not in {0, -15, -9}:  # pragma: no cover - failure diagnostics
            output = proc.stdout.read() if proc.stdout else ""
            raise AssertionError(f"server exited unexpectedly rc={proc.returncode}\n{output}")
