from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Keep sample generation isolated from any reviewer or developer DB.
os.environ.setdefault("JOB_INTEL_DB", str(Path(tempfile.gettempdir()) / "job_board_intelligence_samples.db"))

from fastapi.testclient import TestClient

import app.main as main


SAMPLES = ROOT / "samples"
SAMPLES.mkdir(parents=True, exist_ok=True)


class DeterministicJobBoardClient:
    def fetch(self, company: dict[str, Any]) -> list[main.JobPosting]:
        fixtures = {
            "OpenAI": [
                ("openai-platform-1", "Senior Python Platform Engineer", "San Francisco", "https://example.test/openai/platform-1"),
                ("openai-ml-2", "Machine Learning Engineer, LLM Agents", "Remote", "https://example.test/openai/ml-2"),
                ("openai-product-3", "Product Manager, Developer Platform", "New York", "https://example.test/openai/product-3"),
                ("openai-security-4", "Staff Security Engineer, Kubernetes", "Remote", "https://example.test/openai/security-4"),
                ("openai-sales-5", "Enterprise Account Executive", "London", "https://example.test/openai/sales-5"),
                ("openai-data-6", "Data Scientist, AI Safety", "San Francisco", "https://example.test/openai/data-6"),
            ],
            "Stripe": [
                ("stripe-python-1", "Senior Backend Engineer, Python Payments", "Remote", "https://example.test/stripe/python-1"),
                ("stripe-go-2", "Go Platform Engineer", "Dublin", "https://example.test/stripe/go-2"),
                ("stripe-design-3", "Product Designer, Dashboard", "New York", "https://example.test/stripe/design-3"),
            ],
            "Anthropic": [
                ("anthropic-ai-1", "Research Engineer, LLM Evaluation", "San Francisco", "https://example.test/anthropic/ai-1"),
            ],
        }
        rows = fixtures.get(company["name"], [])
        return [
            main.JobPosting(
                external_id=f"demo:{company['name']}:{external_id}",
                company=company["name"],
                title=title,
                location=location,
                url=url,
                source="deterministic-demo",
                **main.tag_role(title, location),
            )
            for external_id, title, location, url in rows
        ]


def write_json(name: str, payload: Any) -> None:
    (SAMPLES / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main_flow() -> None:
    db_path = SAMPLES / "sample-demo.sqlite"
    if db_path.exists():
        db_path.unlink()
    main.store = main.Store(str(db_path))
    main.JobBoardClient = DeterministicJobBoardClient
    client = TestClient(main.app)

    health = client.get("/health")
    companies = client.get("/api/companies")
    subscriber = client.post(
        "/api/subscribers",
        json={
            "email": "reviewer@example.com",
            "companies": ["OpenAI", "Stripe"],
            "departments": [],
            "tech_stacks": [],
            "real_time": True,
        },
    )
    poll = client.post("/api/poll?limit_companies=50")
    jobs_python = client.get("/api/jobs?department=engineering&tech=python")
    signals = client.get("/api/signals")
    deliveries = client.get("/api/deliveries")
    digest = client.post("/api/digest/send")
    payment_requirements = client.get("/api/payments/x402/requirements")
    unpaid_export = client.get("/api/export")
    paid_export = client.get("/api/export", headers={"X-PAYMENT": "demo-reviewer-receipt"})
    dashboard = client.get("/?company=OpenAI&department=engineering")

    companies_body = companies.json()
    paid_export_body = paid_export.json()
    signals_body = signals.json()
    jobs_body = jobs_python.json()
    deliveries_body = deliveries.json()

    write_json(
        "00_evidence_summary.json",
        {
            "bounty_id": "idea_027",
            "product": "Job Board Intelligence",
            "checks": {
                "health_ok": health.status_code == 200 and health.json().get("ok") is True,
                "seeded_companies": len(companies_body),
                "seeded_companies_at_least_50": len(companies_body) >= 50,
                "poll_created_signals": poll.json().get("signals_created", 0),
                "python_engineering_jobs": len(jobs_body),
                "deliveries_recorded": len(deliveries_body),
                "x402_unpaid_export_status": unpaid_export.status_code,
                "x402_paid_export_status": paid_export.status_code,
                "dashboard_status": dashboard.status_code,
            },
            "sample_files": [
                "01_health_response.json",
                "02_companies_sample_response.json",
                "03_subscriber_response.json",
                "04_poll_response.json",
                "05_jobs_filter_response.json",
                "06_signals_response.json",
                "07_deliveries_response.json",
                "08_weekly_digest_response.json",
                "09_x402_payment_requirements.json",
                "10_export_payment_required_response.json",
                "11_export_paid_summary.json",
                "12_dashboard_snippet.html",
                "test-output.txt",
            ],
        },
    )
    write_json("01_health_response.json", {"status_code": health.status_code, "body": health.json()})
    write_json("02_companies_sample_response.json", {"count": len(companies_body), "first_10": companies_body[:10]})
    write_json("03_subscriber_response.json", {"status_code": subscriber.status_code, "body": subscriber.json()})
    write_json("04_poll_response.json", {"status_code": poll.status_code, "body": poll.json()})
    write_json("05_jobs_filter_response.json", {"status_code": jobs_python.status_code, "body": jobs_body})
    write_json("06_signals_response.json", {"status_code": signals.status_code, "body": signals_body})
    write_json("07_deliveries_response.json", {"status_code": deliveries.status_code, "body": deliveries_body})
    write_json("08_weekly_digest_response.json", {"status_code": digest.status_code, "body": digest.json()})
    write_json("09_x402_payment_requirements.json", {"status_code": payment_requirements.status_code, "body": payment_requirements.json()})
    write_json("10_export_payment_required_response.json", {"status_code": unpaid_export.status_code, "body": unpaid_export.json()})
    write_json(
        "11_export_paid_summary.json",
        {
            "status_code": paid_export.status_code,
            "company_count": len(paid_export_body.get("companies", [])),
            "job_count": len(paid_export_body.get("jobs", [])),
            "signal_count": len(paid_export_body.get("signals", [])),
            "sample_jobs": paid_export_body.get("jobs", [])[:5],
            "sample_signals": paid_export_body.get("signals", [])[:5],
            "exported_at": paid_export_body.get("exported_at"),
        },
    )
    (SAMPLES / "12_dashboard_snippet.html").write_text(dashboard.text[:4000])
    if db_path.exists():
        db_path.unlink()


if __name__ == "__main__":
    main_flow()
