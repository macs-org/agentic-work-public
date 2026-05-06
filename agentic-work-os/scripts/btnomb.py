#!/usr/bin/env python3
"""BTNOMB automation helper for Agentic Work.

Money-first workflow primitives for BTNOMB bounties:
- discover/list open bounties
- query submission/claim/counter status
- unlock full briefs via x402 using the Agentic Work project wallet
- validate public submission folders before claim/submit
- claim and submit with EIP-191 personal_sign signatures
- publish local deliverable folders to the public submissions repo
- track submission state and earnings ledger updates

The script intentionally avoids printing private keys, x402 payment payloads, or
raw signatures unless explicitly required for an API request.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
BTNOMB_BASE = "https://bounty.btnomb.com"
API_BASE = f"{BTNOMB_BASE}/api"
DEFAULT_UA = "Mozilla/5.0 (compatible; AgenticWorkBTNOMB/1.0)"
PROJECT_WALLET_PATH = Path.home() / ".config" / "agentic-work" / "wallet.json"
PUBLIC_REPO = "macs-org/agentic-work-public"
PUBLIC_REPO_URL = "https://github.com/macs-org/agentic-work-public"
STATE_PATH = ROOT / "state" / "btnomb_submissions.json"
LEDGER_PATH = ROOT / "earnings" / "ledger.jsonl"
EXCLUDE_NAMES = {
    ".venv",
    "venv",
    ".pytest_cache",
    "__pycache__",
    ".DS_Store",
    ".mypy_cache",
    ".ruff_cache",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def short_wallet(address: str) -> str:
    if len(address) >= 12:
        return f"{address[:6]}...{address[-4:]}"
    return address


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return re.sub(r"-+", "-", slug) or "untitled"


def http() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": DEFAULT_UA, "Accept": "application/json"})
    return s


def request_json(method: str, path: str, *, session: requests.Session | None = None, **kwargs: Any) -> tuple[int, Any]:
    sess = session or http()
    headers = kwargs.pop("headers", {}) or {}
    merged_headers = {"User-Agent": DEFAULT_UA, "Accept": "application/json", **headers}
    url = path if path.startswith("http") else f"{BTNOMB_BASE}{path}"
    r = sess.request(method, url, timeout=60, headers=merged_headers, **kwargs)
    try:
        body: Any = r.json()
    except Exception:
        body = r.text
    return r.status_code, body


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def load_wallet() -> tuple[str, str]:
    data = read_json(PROJECT_WALLET_PATH, {})
    key = data.get("private_key") or data.get("privateKey")
    address = data.get("wallet_address") or data.get("address")
    if not key:
        raise RuntimeError(f"No private key found in {PROJECT_WALLET_PATH}")
    from eth_account import Account

    acct = Account.from_key(key)
    if address and acct.address.lower() != str(address).lower():
        raise RuntimeError("Project wallet private key does not match wallet_address")
    return acct.address, key


def sign_personal_message(private_key: str, message: str) -> str:
    from eth_account import Account
    from eth_account.messages import encode_defunct

    acct = Account.from_key(private_key)
    sig = acct.sign_message(encode_defunct(text=message)).signature.hex()
    return sig if sig.startswith("0x") else "0x" + sig


def state_load() -> dict[str, Any]:
    data = read_json(STATE_PATH, {"submissions": {}})
    if "submissions" not in data or not isinstance(data["submissions"], dict):
        data["submissions"] = {}
    return data


def state_save(data: dict[str, Any]) -> None:
    write_json(STATE_PATH, data)


def state_upsert(bid: str, **fields: Any) -> dict[str, Any]:
    data = state_load()
    record = data["submissions"].setdefault(bid, {"id": bid})
    record.update(fields)
    record["last_updated_at"] = now_iso()
    state_save(data)
    return record


def list_bounties(status: str | None = None) -> list[dict[str, Any]]:
    params = {}
    if status:
        params["status"] = status
    code, body = request_json("GET", "/api/bounties", params=params)
    if code != 200 or not isinstance(body, list):
        raise RuntimeError(f"BTNOMB list failed HTTP {code}: {str(body)[:500]}")
    return body


def bounty_detail(bid: str) -> dict[str, Any]:
    code, body = request_json("GET", f"/api/bounties/{bid}")
    if code != 200 or not isinstance(body, dict):
        raise RuntimeError(f"BTNOMB detail failed for {bid} HTTP {code}: {str(body)[:500]}")
    return body


def claim_status(bid: str) -> dict[str, Any]:
    code, body = request_json("GET", f"/api/bounties/{bid}/claim-status")
    if code != 200 or not isinstance(body, dict):
        raise RuntimeError(f"BTNOMB claim-status failed for {bid} HTTP {code}: {str(body)[:500]}")
    return body


def counter_status(bid: str) -> tuple[int, Any]:
    return request_json("GET", f"/api/bounties/{bid}/counter")


def unlock_full_brief(bid: str, out_path: Path) -> dict[str, Any]:
    """Unlock a paid full brief via x402 and save it."""
    _, private_key = load_wallet()
    from eth_account import Account
    from x402 import x402ClientSync
    from x402.http.x402_http_client import x402HTTPClientSync
    from x402.mechanisms.evm.exact import register_exact_evm_client
    from x402.mechanisms.evm.signers import EthAccountSigner

    acct = Account.from_key(private_key)
    signer = EthAccountSigner(acct)
    x402_client = x402ClientSync()
    try:
        register_exact_evm_client(x402_client, signer, networks="eip155:8453")
    except TypeError:
        register_exact_evm_client(x402_client, signer)
    http_x402 = x402HTTPClientSync(x402_client)

    with requests.Session() as sess:
        sess.headers.update({"User-Agent": DEFAULT_UA, "Accept": "application/json"})
        first = sess.get(f"{API_BASE}/bounties/{bid}/full", timeout=60)
        if first.status_code == 200:
            data = first.json()
        elif first.status_code == 402:
            challenge = first.json()
            payreq = {"x402Version": challenge.get("x402Version", 1), "accepts": challenge.get("accepts") or []}
            pr_header = base64.b64encode(json.dumps(payreq).encode()).decode()
            payment_headers, _payload = http_x402.handle_402_response({"PAYMENT-REQUIRED": pr_header}, None)
            if "PAYMENT" in payment_headers and "X-PAYMENT" not in payment_headers:
                payment_headers["X-PAYMENT"] = payment_headers["PAYMENT"]
            paid = sess.get(f"{API_BASE}/bounties/{bid}/full", headers={"Accept": "application/json", **payment_headers}, timeout=60)
            if paid.status_code != 200:
                raise RuntimeError(f"Paid full-brief unlock failed HTTP {paid.status_code}: {paid.text[:1000]}")
            data = paid.json()
        else:
            raise RuntimeError(f"Full-brief unlock failed HTTP {first.status_code}: {first.text[:1000]}")
    write_json(out_path, data)
    state_upsert(
        bid,
        title=data.get("title"),
        gross_usdc=data.get("bountyUsd"),
        status=data.get("status"),
        full_brief_path=str(out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path),
    )
    return data


def should_exclude(path: Path) -> bool:
    return any(part in EXCLUDE_NAMES for part in path.parts) or path.suffix in EXCLUDE_SUFFIXES


def iter_payload_files(source: Path) -> list[Path]:
    files: list[Path] = []
    for path in source.rglob("*"):
        if path.is_dir() or should_exclude(path.relative_to(source)):
            continue
        # Skip binary-ish files.
        data = path.read_bytes()
        if b"\x00" in data[:1024]:
            continue
        files.append(path)
    return sorted(files)


def validate_source(source: Path) -> tuple[bool, list[str]]:
    messages: list[str] = []
    fatal = False
    if not source.exists() or not source.is_dir():
        return False, [f"source directory missing: {source}"]
    for required in ["README.md", "Dockerfile", "requirements.txt", "app/main.py"]:
        if not (source / required).exists():
            fatal = True
            messages.append(f"missing {required}")
    if not any((source / "tests").glob("test_*.py")):
        fatal = True
        messages.append("missing pytest tests under tests/test_*.py")
    bad = [p for p in source.rglob("*") if p.is_file() and should_exclude(p.relative_to(source))]
    if bad:
        # Non-fatal because publish excludes these automatically.
        messages.append(f"warning: local generated artifacts present: {len(bad)} files (run cleanup before committing)")
    return not fatal, messages


def run_tests(source: Path) -> tuple[bool, str]:
    python = source / ".venv" / "bin" / "python"
    cmd = [str(python if python.exists() else sys.executable), "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"]
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(cmd, cwd=source, env=env, text=True, capture_output=True, timeout=300)
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, output


def github_token() -> str:
    # Prefer GitHub App installation token.
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        for raw in env_path.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    if os.getenv("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    app_id = os.environ.get("GITHUB_APP_ID")
    inst = os.environ.get("GITHUB_APP_INSTALLATION_ID")
    key_path = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH")
    if not (app_id and inst and key_path):
        raise RuntimeError("No GITHUB_TOKEN or GitHub App env vars available")
    import jwt

    key = Path(os.path.expanduser(key_path)).read_text()
    now = int(time.time())
    encoded = jwt.encode({"iat": now - 60, "exp": now + 540, "iss": str(app_id)}, key, algorithm="RS256")
    r = requests.post(
        f"https://api.github.com/app/installations/{inst}/access_tokens",
        headers={"Authorization": f"Bearer {encoded}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["token"]


def gh_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def publish_public(source: Path, dest: str, branch: str | None = None, repo: str = PUBLIC_REPO, merge: bool = True) -> str:
    ok, errors = validate_source(source)
    # Generated artifacts are non-fatal because we exclude them; everything else is fatal.
    fatal = [e for e in errors if not e.startswith("local generated artifacts present")]
    if fatal:
        raise RuntimeError("validation failed before publish: " + "; ".join(fatal))
    token = github_token()
    h = gh_headers(token)
    branch = branch or f"publish-{slugify(dest)}-{int(time.time())}"
    base = requests.get(f"https://api.github.com/repos/{repo}/git/ref/heads/main", headers=h, timeout=60)
    base.raise_for_status()
    base_sha = base.json()["object"]["sha"]
    refs_url = f"https://api.github.com/repos/{repo}/git/refs"
    rr = requests.post(refs_url, headers=h, json={"ref": f"refs/heads/{branch}", "sha": base_sha}, timeout=60)
    if rr.status_code == 422:
        rr = requests.patch(f"{refs_url}/heads/{branch}", headers=h, json={"sha": base_sha, "force": True}, timeout=60)
    rr.raise_for_status()
    latest = requests.get(f"https://api.github.com/repos/{repo}/git/ref/heads/{branch}", headers=h, timeout=60)
    latest.raise_for_status()
    latest_sha = latest.json()["object"]["sha"]
    base_commit = requests.get(f"https://api.github.com/repos/{repo}/git/commits/{latest_sha}", headers=h, timeout=60)
    base_commit.raise_for_status()
    base_tree = base_commit.json()["tree"]["sha"]
    tree_items: list[dict[str, str]] = []
    for path in iter_payload_files(source):
        data = path.read_bytes()
        br = requests.post(
            f"https://api.github.com/repos/{repo}/git/blobs",
            headers=h,
            json={"content": base64.b64encode(data).decode(), "encoding": "base64"},
            timeout=60,
        )
        br.raise_for_status()
        rel = path.relative_to(source).as_posix()
        tree_items.append({"path": f"{dest.rstrip('/')}/{rel}", "mode": "100644", "type": "blob", "sha": br.json()["sha"]})
    tr = requests.post(f"https://api.github.com/repos/{repo}/git/trees", headers=h, json={"base_tree": base_tree, "tree": tree_items}, timeout=60)
    tr.raise_for_status()
    commit_msg = f"feat: publish {dest}"
    cr = requests.post(
        f"https://api.github.com/repos/{repo}/git/commits",
        headers=h,
        json={"message": commit_msg, "tree": tr.json()["sha"], "parents": [latest_sha]},
        timeout=60,
    )
    cr.raise_for_status()
    commit_sha = cr.json()["sha"]
    up = requests.patch(f"https://api.github.com/repos/{repo}/git/refs/heads/{branch}", headers=h, json={"sha": commit_sha, "force": False}, timeout=60)
    up.raise_for_status()
    prr = requests.post(
        f"https://api.github.com/repos/{repo}/pulls",
        headers=h,
        json={"title": commit_msg, "head": branch, "base": "main", "body": f"Publishes `{dest}` from `{source}`."},
        timeout=60,
    )
    if prr.status_code == 422:
        prs = requests.get(f"https://api.github.com/repos/{repo}/pulls?head={repo.split('/')[0]}:{branch}&state=open", headers=h, timeout=60)
        prs.raise_for_status()
        pr = prs.json()[0]
    else:
        prr.raise_for_status()
        pr = prr.json()
    if merge:
        mr = requests.put(
            f"https://api.github.com/repos/{repo}/pulls/{pr['number']}/merge",
            headers=h,
            json={"merge_method": "squash", "commit_title": f"{commit_msg} (#{pr['number']})"},
            timeout=60,
        )
        mr.raise_for_status()
    public_url = f"{PUBLIC_REPO_URL}/tree/main/{quote(dest.strip('/'))}"
    # Verify no-auth access.
    verify = requests.get(f"https://api.github.com/repos/{repo}/contents/{quote(dest.strip('/'), safe='/')}?ref=main", timeout=60)
    if verify.status_code != 200:
        raise RuntimeError(f"public verify failed HTTP {verify.status_code}: {verify.text[:500]}")
    return public_url


def claim(bid: str) -> dict[str, Any]:
    address, private_key = load_wallet()
    message = f"Claim bounty {bid} on BTNOMB Bounty Board"
    payload = {"wallet": address, "message": message, "signature": sign_personal_message(private_key, message)}
    code, body = request_json("POST", f"/api/bounties/{bid}/claim", json=payload, headers={"Content-Type": "application/json"})
    if code not in {200, 201}:
        raise RuntimeError(f"claim failed HTTP {code}: {str(body)[:1000]}")
    state_upsert(bid, wallet=address, status=body.get("status"), claim_deadline=body.get("claim_deadline"), last_claim_response=body)
    return body


def submit(bid: str, submission_url: str) -> dict[str, Any]:
    address, private_key = load_wallet()
    message = f"Submit work for bounty {bid} on BTNOMB Bounty Board"
    payload = {"wallet": address, "submissionUrl": submission_url, "message": message, "signature": sign_personal_message(private_key, message)}
    code, body = request_json("POST", f"/api/bounties/{bid}/submit", json=payload, headers={"Content-Type": "application/json"})
    if code not in {200, 201}:
        raise RuntimeError(f"submit failed HTTP {code}: {str(body)[:1000]}")
    detail = bounty_detail(bid)
    state_upsert(bid, wallet=address, status=body.get("status"), submission_url=submission_url, last_submit_response=body, title=detail.get("title"), gross_usdc=detail.get("bountyUsd"))
    append_ledger_once(bid, detail, submission_url, status=body.get("status", "SUBMITTED"))
    return body


def append_ledger_once(bid: str, detail: dict[str, Any], submission_url: str, status: str) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = LEDGER_PATH.read_text() if LEDGER_PATH.exists() else ""
    if bid in existing:
        return
    gross = float(detail.get("bountyUsd") or 0)
    cut = float(detail.get("platformCutPct") or 5)
    entry = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "platform": "btnomb",
        "bounty_id": bid,
        "title": detail.get("title"),
        "status": status,
        "gross_usdc": gross,
        "net_expected_usdc": round(gross * (100 - cut) / 100, 2),
        "submission_url": submission_url,
    }
    with LEDGER_PATH.open("a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def cleanup(root: Path) -> tuple[int, int]:
    removed_files = 0
    removed_dirs = 0
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        rel = path.relative_to(root)
        if path.is_dir() and any(part in EXCLUDE_NAMES for part in rel.parts):
            shutil.rmtree(path, ignore_errors=True)
            removed_dirs += 1
        elif path.is_file() and should_exclude(rel):
            path.unlink(missing_ok=True)
            removed_files += 1
    return removed_files, removed_dirs


def cmd_list(args: argparse.Namespace) -> int:
    rows = []
    for b in list_bounties(args.status):
        if args.open_only and b.get("status") != "OPEN":
            continue
        if args.min_usd and float(b.get("bountyUsd") or 0) < args.min_usd:
            continue
        rows.append(b)
    rows.sort(key=lambda b: (float(b.get("bountyUsd") or 0), int(b.get("votes") or 0)), reverse=True)
    for b in rows[: args.limit]:
        print(f"{b.get('id')} | {b.get('status')} | ${b.get('bountyUsd')} | votes={b.get('votes')} | {b.get('title')}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    ids = args.ids or list(state_load().get("submissions", {}).keys())
    total_gross = 0.0
    pending = accepted = action = 0
    for bid in ids:
        detail = bounty_detail(bid)
        cs = claim_status(bid)
        cc, cb = counter_status(bid)
        status = cs.get("status") or detail.get("status")
        gross = float(detail.get("bountyUsd") or 0)
        total_gross += gross
        if status in {"SUBMITTED", "IN_PROGRESS"}:
            pending += 1
        elif status in {"ACCEPTED", "PAID", "COMPLETED"}:
            accepted += 1
        else:
            action += 1
        counter = cb if cc == 200 else None
        state_upsert(bid, title=detail.get("title"), status=status, gross_usdc=gross, claim_status=cs, counter=counter, last_checked_at=now_iso())
        print(f"{bid}: {status} | ${gross:g} | builder={cs.get('claimedBy')} | hours_remaining={cs.get('hours_remaining')} | counter={'yes' if counter else 'no'}")
    print(f"Totals: {len(ids)} tracked | pending={pending} | accepted_or_paid={accepted} | action_needed={action} | gross=${total_gross:g} | net_expected=${round(total_gross*0.95,2):g}")
    return 0


def cmd_unlock(args: argparse.Namespace) -> int:
    data = unlock_full_brief(args.id, Path(args.out))
    print(json.dumps({k: data.get(k) for k in ["id", "title", "bountyUsd", "status", "claimedBy", "platformCutPct"]}, indent=2, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    source = Path(args.source)
    ok, errors = validate_source(source)
    tests_ok, test_out = run_tests(source) if args.tests else (True, "tests skipped")
    print(f"source={source}")
    print(f"structure_ok={ok}")
    for e in errors:
        print(f"- {e}")
    print(f"tests_ok={tests_ok}")
    print(test_out[-2000:])
    return 0 if ok and tests_ok else 1


def cmd_publish(args: argparse.Namespace) -> int:
    url = publish_public(Path(args.source), args.dest, branch=args.branch, merge=not args.no_merge)
    print(url)
    return 0


def cmd_claim_submit(args: argparse.Namespace) -> int:
    if args.claim:
        print(json.dumps(claim(args.id), indent=2, ensure_ascii=False))
    if args.submit_url:
        print(json.dumps(submit(args.id, args.submit_url), indent=2, ensure_ascii=False))
    if not args.claim and not args.submit_url:
        raise SystemExit("Pass --claim and/or --submit-url")
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    files, dirs = cleanup(Path(args.path))
    print(f"removed_files={files} removed_dirs={dirs}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="BTNOMB automation for Agentic Work")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list", help="List bounties")
    s.add_argument("--status")
    s.add_argument("--open-only", action="store_true")
    s.add_argument("--min-usd", type=float, default=0)
    s.add_argument("--limit", type=int, default=25)
    s.set_defaults(func=cmd_list)
    s = sub.add_parser("status", help="Check tracked or specified bounty statuses")
    s.add_argument("ids", nargs="*")
    s.set_defaults(func=cmd_status)
    s = sub.add_parser("unlock", help="Unlock full brief via x402")
    s.add_argument("id")
    s.add_argument("out")
    s.set_defaults(func=cmd_unlock)
    s = sub.add_parser("validate", help="Validate deliverable folder")
    s.add_argument("source")
    s.add_argument("--tests", action="store_true")
    s.set_defaults(func=cmd_validate)
    s = sub.add_parser("publish", help="Publish deliverable folder to public repo")
    s.add_argument("source")
    s.add_argument("dest")
    s.add_argument("--branch")
    s.add_argument("--no-merge", action="store_true")
    s.set_defaults(func=cmd_publish)
    s = sub.add_parser("claim-submit", help="Claim and/or submit a bounty")
    s.add_argument("id")
    s.add_argument("--claim", action="store_true")
    s.add_argument("--submit-url")
    s.set_defaults(func=cmd_claim_submit)
    s = sub.add_parser("cleanup", help="Remove generated artifacts")
    s.add_argument("path", nargs="?", default="platforms/agent-native/btnomb/jobs")
    s.set_defaults(func=cmd_cleanup)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
