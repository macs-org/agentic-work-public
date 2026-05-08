#!/usr/bin/env python3
"""Generate deterministic reviewer evidence for the Patent Filing Tracker MVP.

The samples use FastAPI TestClient, a temporary SQLite database, and deterministic
PatentsView fixtures. They do not require network access, SMTP credentials, wallet
keys, or a live x402 facilitator.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import app.main as main  # noqa: E402

SAMPLES = ROOT / "samples"


class FakePatentsViewClient:
    def search(self, kind: str, value: str, per_page: int = 10) -> list[main.PatentFiling]:
        safe_value = "".join(ch for ch in value.upper() if ch.isalnum())[:12] or "WATCH"
        assignee = value if kind == "company" else "Example Labs"
        return [
            main.PatentFiling(
                patent_id=f"{kind.upper()}-{safe_value}-001",
                title=f"Autonomous patent intelligence system for {value}",
                abstract=(
                    "A machine learning platform monitors patent publications, "
                    "summarizes filings, and routes competitive intelligence alerts."
                ),
                assignee=assignee,
                publication_date="2026-05-01",
                filing_date="2025-11-01",
                cpc_category="G06N",
                source_url=f"https://patents.google.com/patent/US{kind.upper()}{safe_value}001",
            )
        ][:per_page]


def fake_deliver_webhook(url: str, payload: dict[str, Any]) -> tuple[str, str]:
    return "sent", f"deterministic reviewer webhook to {url}; payload keys={','.join(sorted(payload))}"


def write_json(name: str, payload: Any) -> None:
    (SAMPLES / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main_run() -> None:
    SAMPLES.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="patent-tracker-samples-") as tmpdir:
        main.store = main.PatentStore(str(Path(tmpdir) / "reviewer.db"))
        main.PatentsViewClient = FakePatentsViewClient  # type: ignore[assignment]
        main.deliver_webhook = fake_deliver_webhook  # type: ignore[assignment]
        client = TestClient(main.app)

        health = client.get("/health")
        company_watchlist = client.post(
            "/api/watchlists",
            json={"kind": "company", "value": "OpenAI", "email": "reviewer@example.com"},
        )
        keyword_watchlist = client.post(
            "/api/watchlists",
            json={"kind": "keyword", "value": "agentic AI", "webhook_url": "https://example.com/patent-alerts"},
        )
        poll = client.post("/api/poll?per_watchlist=5")
        filings = client.get("/api/filings?q=agentic")
        alerts = client.get("/api/alerts")
        trends = client.get("/api/trends")
        payment_requirements = client.get("/api/payments/x402/requirements")
        unpaid_export = client.get("/api/export")
        paid_export = client.get("/api/export", headers={"X-PAYMENT": "demo-reviewer-receipt"})
        dashboard = client.get("/")

        write_json(
            "00_evidence_summary.json",
            {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "checks": {
                    "health_ok": health.status_code == 200 and health.json().get("ok") is True,
                    "company_watchlist_created": company_watchlist.status_code == 200,
                    "keyword_watchlist_created": keyword_watchlist.status_code == 200,
                    "poll_created_filings": poll.json().get("new_filings"),
                    "email_alert_recorded": any(a.get("channel") == "email" for a in alerts.json()),
                    "webhook_alert_recorded": any(a.get("channel") == "webhook" for a in alerts.json()),
                    "dashboard_live": dashboard.status_code == 200 and "Patent Filing Tracker" in dashboard.text,
                    "x402_unpaid_returns_402": unpaid_export.status_code == 402,
                    "x402_paid_export_ok": paid_export.status_code == 200,
                },
                "artifact_files": [
                    "01_health_response.json",
                    "02_company_watchlist_response.json",
                    "03_keyword_watchlist_response.json",
                    "04_poll_response.json",
                    "05_filings_search_response.json",
                    "06_alerts_response.json",
                    "07_trends_response.json",
                    "08_x402_payment_requirements.json",
                    "09_export_payment_required_response.json",
                    "10_export_paid_response.json",
                    "11_dashboard_snippet.html",
                    "test-output.txt",
                ],
            },
        )
        write_json("01_health_response.json", health.json())
        write_json("02_company_watchlist_response.json", company_watchlist.json())
        write_json("03_keyword_watchlist_response.json", keyword_watchlist.json())
        write_json("04_poll_response.json", poll.json())
        write_json("05_filings_search_response.json", filings.json())
        write_json("06_alerts_response.json", alerts.json())
        write_json("07_trends_response.json", trends.json())
        write_json("08_x402_payment_requirements.json", payment_requirements.json())
        write_json("09_export_payment_required_response.json", {"status_code": unpaid_export.status_code, "body": unpaid_export.json()})
        write_json("10_export_paid_response.json", paid_export.json())
        (SAMPLES / "11_dashboard_snippet.html").write_text(dashboard.text[:5000], encoding="utf-8")

        print(f"wrote reviewer samples to {SAMPLES}")
        print(json.dumps(json.loads((SAMPLES / "00_evidence_summary.json").read_text()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main_run()
