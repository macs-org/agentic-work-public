import os
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main


class FakePatentsViewClient:
    def search(self, kind, value, per_page=10):
        return [
            main.PatentFiling(
                patent_id="1234567",
                title=f"Autonomous agent patent for {value}",
                abstract="A machine learning system coordinates autonomous AI agents for competitive intelligence.",
                assignee="OpenAI" if kind == "company" else "Example Labs",
                publication_date="2026-05-01",
                filing_date="2025-11-01",
                cpc_category="G06N",
                source_url="https://patents.google.com/patent/US1234567",
            )
        ]


def fresh_client(tmp_path, monkeypatch):
    main.store = main.PatentStore(str(tmp_path / "test.db"))
    monkeypatch.setattr(main, "PatentsViewClient", lambda: FakePatentsViewClient())
    return TestClient(main.app)


def test_company_watchlist_poll_summary_and_email_outbox(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    created = client.post("/api/watchlists", json={"kind": "company", "value": "OpenAI", "email": "alerts@example.com"})
    assert created.status_code == 200
    assert created.json()["kind"] == "company"

    poll = client.post("/api/poll")
    assert poll.status_code == 200
    assert poll.json()["new_filings"] == 1

    filings = client.get("/api/filings").json()
    assert len(filings) == 1
    assert "autonomous" in filings[0]["summary"].lower()
    assert "strategic_implication" in filings[0]

    alerts = client.get("/api/alerts").json()
    assert alerts[0]["channel"] == "email"
    assert alerts[0]["status"] == "stored"


def test_keyword_watchlist_dashboard_and_trends(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    assert client.post("/api/watchlists", json={"kind": "keyword", "value": "agentic AI"}).status_code == 200
    assert client.post("/api/poll").json()["matched"] == 1
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Patent Filing Tracker" in dashboard.text
    assert "Autonomous agent patent" in dashboard.text
    trends = client.get("/api/trends").json()
    assert trends
    assert trends[0]["filings"] == 1


def test_x402_payment_gate(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    req = client.get("/api/payments/x402/requirements")
    assert req.status_code == 200
    assert req.json()["network"] == "base"

    unpaid = client.get("/api/export")
    assert unpaid.status_code == 402

    paid = client.get("/api/export", headers={"X-PAYMENT": "demo-receipt"})
    assert paid.status_code == 200
    assert "filings" in paid.json()


def test_patentsview_response_normalization():
    payload = {"patents": [{"patent_id": "7654321", "patent_title": "Battery sensor", "assignees": [{"assignee_organization": "Acme"}], "cpcs": [{"cpc_group_id": "H01M"}]}]}
    rows = main.extract_patent_rows(payload)
    filing = main.normalize_patent(rows[0])
    assert filing.patent_id == "7654321"
    assert filing.assignee == "Acme"
    assert filing.cpc_category == "H01M"
