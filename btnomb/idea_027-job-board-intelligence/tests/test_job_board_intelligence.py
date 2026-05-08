from fastapi.testclient import TestClient

import app.main as main


class FakeClient:
    def fetch(self, company):
        if company["name"] not in {"OpenAI", "Stripe"}:
            return []
        return [
            main.JobPosting(external_id=f"fake:{company['name']}:1", company=company["name"], title="Senior Python Platform Engineer", location="San Francisco", url="https://example.test/1", source="fake", **main.tag_role("Senior Python Platform Engineer", "San Francisco")),
            main.JobPosting(external_id=f"fake:{company['name']}:2", company=company["name"], title="Machine Learning Engineer, LLM Agents", location="Remote", url="https://example.test/2", source="fake", **main.tag_role("Machine Learning Engineer, LLM Agents", "Remote")),
            main.JobPosting(external_id=f"fake:{company['name']}:3", company=company["name"], title="Product Manager, Developer Platform", location="New York", url="https://example.test/3", source="fake", **main.tag_role("Product Manager, Developer Platform", "New York")),
        ]


def fresh_client(tmp_path, monkeypatch):
    main.store = main.Store(str(tmp_path / "jobs.db"))
    monkeypatch.setattr(main, "JobBoardClient", lambda: FakeClient())
    return TestClient(main.app)


def test_seeds_50_companies_and_polls_public_board_clients(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    companies = client.get("/api/companies").json()
    assert len(companies) >= 50

    sub = client.post("/api/subscribers", json={"email":"alerts@example.com", "companies":["OpenAI"], "departments":["engineering"], "real_time": True})
    assert sub.status_code == 200

    poll = client.post("/api/poll?limit_companies=50")
    assert poll.status_code == 200
    body = poll.json()
    assert body["tracked_companies"] >= 50
    assert body["new_jobs"] >= 6
    assert body["signals_created"] >= 2

    jobs = client.get("/api/jobs?department=engineering&tech=python").json()
    assert any(j["company"] == "OpenAI" for j in jobs)
    deliveries = client.get("/api/deliveries").json()
    assert deliveries
    assert deliveries[0]["status"] == "stored"


def test_dashboard_signals_digest_and_filters(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    client.post("/api/subscribers", json={"email":"alerts@example.com", "companies":["Stripe"]})
    client.post("/api/poll?limit_companies=50")

    dash = client.get("/?company=Stripe&department=engineering")
    assert dash.status_code == 200
    assert "Job Board Intelligence" in dash.text
    assert "Senior Python Platform Engineer" in dash.text

    signals = client.get("/api/signals?company=Stripe").json()
    assert signals
    assert {s["kind"] for s in signals} & {"baseline", "new_roles"}

    digest = client.post("/api/digest/send").json()
    assert digest["signals_considered"] >= 1


def test_x402_payment_gate_and_role_tagging(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    req = client.get("/api/payments/x402/requirements")
    assert req.status_code == 200
    assert req.json()["network"] == "base"

    assert client.get("/api/export").status_code == 402
    assert client.get("/api/export", headers={"X-PAYMENT":"demo-receipt"}).status_code == 200

    tags = main.tag_role("Principal Rust Backend Engineer, Kubernetes", "Remote")
    assert tags["department"] == "engineering"
    assert tags["seniority"] == "lead"
    assert "rust" in tags["tech_stack"]
    assert "kubernetes" in tags["tech_stack"]


def test_trend_drop_detection(tmp_path, monkeypatch):
    client = fresh_client(tmp_path, monkeypatch)
    company = {"name": "OpenAI", "source": "fake", "slug": "openai"}
    jobs = [main.JobPosting(external_id=f"x:{i}", company="OpenAI", title=f"Engineer {i}", source="fake", **main.tag_role("Engineer")) for i in range(10)]
    main.store.upsert_jobs_for_company("OpenAI", jobs)
    main.store.snapshot_and_detect("OpenAI", 10, 0)
    main.store.upsert_jobs_for_company("OpenAI", jobs[:3])
    signals = main.store.snapshot_and_detect("OpenAI", 0, 7)
    assert any(s["kind"] == "drop" for s in signals)
