from fastapi.testclient import TestClient

import app.main as main


class FakeSource:
    def __init__(self, agency):
        self.agency = agency
    def fetch(self, limit=10):
        return [main.RegulatoryDocument(
            source_id=f"{self.agency}:2026-001",
            agency=self.agency,
            title=f"{self.agency} final rule on automated crypto compliance",
            body="Final rule requiring automated compliance controls for digital asset platforms and cybersecurity reporting.",
            document_type="final rule",
            publication_date="2026-05-08",
            effective_date="2026-06-01",
            url="https://example.test/rule",
        )]


def fresh_client(tmp_path, monkeypatch):
    main.store = main.Store(str(tmp_path / "reg.db"))
    monkeypatch.setattr(main, "get_sources", lambda: [FakeSource("SEC"), FakeSource("FDA"), FakeSource("FCC"), FakeSource("CFTC")])
    return TestClient(main.app)


def test_subscriber_poll_email_outbox_and_four_sources(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    created = client.post("/api/subscribers", json={"email": "alerts@example.com", "agencies": ["SEC", "FDA", "FCC", "CFTC"], "topics": ["crypto"], "industries": ["fintech"]})
    assert created.status_code == 200

    poll = client.post("/api/poll?limit_per_source=1")
    assert poll.status_code == 200
    data = poll.json()
    assert data["sources"] == ["SEC", "FDA", "FCC", "CFTC"]
    assert data["new_alerts"] == 4
    assert data["summaries_generated_immediately"] is True

    alerts = client.get("/api/alerts?agency=SEC").json()
    assert len(alerts) == 1
    assert alerts[0]["impact_level"] == "major rule change"
    assert "fintech" in alerts[0]["affected_industries"]

    deliveries = client.get("/api/deliveries").json()
    assert deliveries
    assert deliveries[0]["status"] == "stored"


def test_dashboard_filters_trends_and_search_archive(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    client.post("/api/subscribers", json={"email": "alerts@example.com", "agencies": ["SEC"], "topics": ["crypto"]})
    client.post("/api/poll?limit_per_source=1")

    dash = client.get("/?agency=SEC&q=crypto")
    assert dash.status_code == 200
    assert "Regulatory Change Monitor" in dash.text
    assert "SEC final rule" in dash.text

    search = client.get("/api/alerts?q=cybersecurity&industry=fintech").json()
    assert len(search) >= 1
    trends = client.get("/api/trends").json()
    assert trends
    assert trends[0]["alerts"] >= 1


def test_x402_payment_gate_and_scheduler_sla(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    req = client.get("/api/payments/x402/requirements")
    assert req.status_code == 200
    assert req.json()["network"] == "base"

    unpaid = client.get("/api/export")
    assert unpaid.status_code == 402
    paid = client.get("/api/export", headers={"X-PAYMENT": "demo-receipt"})
    assert paid.status_code == 200
    assert "alerts" in paid.json()

    scheduler = client.get("/api/scheduler/status").json()
    assert scheduler["poll_interval_seconds"] >= 1


def test_summary_classifies_major_rule():
    doc = main.RegulatoryDocument(
        source_id="SEC:test",
        agency="SEC",
        title="Final rule for digital asset exchanges",
        body="Compliance rule for crypto securities exchanges with mandatory reporting.",
        document_type="final rule",
        effective_date="2026-06-01",
    )
    summary = main.summarize_document(doc)
    assert summary["impact_score"] >= 65
    assert "fintech" in summary["affected_industries"]
    assert summary["impact_level"] == "major rule change"
