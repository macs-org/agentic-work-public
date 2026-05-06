#!/usr/bin/env python3
"""Summarize Agentic Work earnings ledger."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "earnings" / "ledger.jsonl"


def load_entries() -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []
    entries = []
    for line in LEDGER.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def normalize_status(status: str) -> str:
    s = (status or "unknown").upper()
    if s in {"PAID", "ACCEPTED", "COMPLETED"}:
        return "realized"
    if s in {"SUBMITTED", "IN_PROGRESS", "CLAIMED"}:
        return "pending"
    if s in {"REJECTED", "REOPENED", "CANCELLED", "LOST"}:
        return "lost"
    return "other"


def cmd_status(args: argparse.Namespace) -> int:
    entries = load_entries()
    if args.platform:
        entries = [e for e in entries if e.get("platform") == args.platform]
    buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "gross": 0.0, "net_expected": 0.0, "realized": 0.0})
    for e in entries:
        b = normalize_status(e.get("status", ""))
        buckets[b]["count"] += 1
        buckets[b]["gross"] += float(e.get("gross_usdc") or 0)
        buckets[b]["net_expected"] += float(e.get("net_expected_usdc") or 0)
        buckets[b]["realized"] += float(e.get("realized_usdc") or 0)
    print(f"Ledger: {LEDGER}")
    for b in ["pending", "realized", "lost", "other"]:
        row = buckets[b]
        print(f"{b}: count={int(row['count'])} gross={row['gross']:.2f} net_expected={row['net_expected']:.2f} realized={row['realized']:.2f}")
    if args.details:
        print("\nEntries:")
        for e in entries:
            print(f"- {e.get('bounty_id') or e.get('id')}: {e.get('status')} | gross={e.get('gross_usdc')} | net={e.get('net_expected_usdc')} | {e.get('title')}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Agentic Work earnings tracker")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--platform")
    s.add_argument("--details", action="store_true")
    s.set_defaults(func=cmd_status)
    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
