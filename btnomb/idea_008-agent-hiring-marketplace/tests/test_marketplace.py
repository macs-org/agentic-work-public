from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app


API_KEY = "dev-marketplace-key"
HEADERS = {"X-API-Key": API_KEY}


def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def auth_post(c: TestClient, path: str, payload: dict):
    return c.post(path, json=payload, headers=HEADERS)


def auth_get(c: TestClient, path: str):
    return c.get(path, headers=HEADERS)


def future_deadline(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_task_posting_feed_bidding_matching_and_award_flow():
    with TestClient(app) as c:
        task_payload = {
            "title": "Summarize protocol repo",
            "requirements": {"language": "python", "deliverable": "markdown audit notes"},
            "acceptance_criteria": ["find risks", "include reproducible commands"],
            "deadline": future_deadline(),
            "budget_usdc": 250,
            "category": "code_generation",
        }
        task = auth_post(c, "/tasks", task_payload).json()
        assert task["status"] == "OPEN"
        assert task["escrow"]["state"] == "AWAITING_BID_ACCEPTANCE"
        assert task["escrow"]["network"] == "base"
        assert task["escrow"]["asset"] == "USDC"

        agent_a = auth_post(c, "/agents", {
            "name": "Fast Python Fixer",
            "wallet": "0x1111111111111111111111111111111111111111",
            "capabilities": ["python", "code_generation"],
            "completed_tasks": 14,
            "approved_tasks": 13,
            "average_completion_hours": 5,
            "base_l2_attestation": "eas:base:0xaaa",
        }).json()
        agent_b = auth_post(c, "/agents", {
            "name": "Cheap Writer",
            "wallet": "0x2222222222222222222222222222222222222222",
            "capabilities": ["content_writing"],
            "completed_tasks": 30,
            "approved_tasks": 29,
            "average_completion_hours": 12,
            "base_l2_attestation": "eas:base:0xbbb",
        }).json()

        feed = auth_get(c, f"/agents/{agent_a['id']}/tasks").json()
        assert feed[0]["id"] == task["id"]
        assert feed[0]["capability_match"] > 0

        bid_a = auth_post(c, f"/tasks/{task['id']}/bids", {
            "agent_id": agent_a["id"],
            "cost_usdc": 190,
            "estimated_hours": 6,
            "proposal": "I will inspect the repo, run tests, and deliver risk notes.",
        }).json()
        bid_b = auth_post(c, f"/tasks/{task['id']}/bids", {
            "agent_id": agent_b["id"],
            "cost_usdc": 120,
            "estimated_hours": 30,
            "proposal": "Cheap generic summary.",
        }).json()
        assert bid_a["rank_score"] > bid_b["rank_score"]

        ranked = auth_get(c, f"/tasks/{task['id']}/bids/ranked").json()
        assert [b["id"] for b in ranked] == [bid_a["id"], bid_b["id"]]

        accepted = auth_post(c, f"/bids/{bid_a['id']}/accept", {}).json()
        assert accepted["status"] == "ASSIGNED"
        assert accepted["winning_bid_id"] == bid_a["id"]
        assert accepted["escrow"]["state"] == "HELD"
        assert accepted["escrow"]["amount_usdc"] == 190
        assert accepted["assigned_agent"]["full_spec_visible"] is True


def test_submission_approval_releases_escrow_and_updates_reputation_stats():
    with TestClient(app) as c:
        agent = auth_post(c, "/agents", {
            "name": "Audit Agent",
            "wallet": "0x3333333333333333333333333333333333333333",
            "capabilities": ["smart_contract_review", "solidity"],
            "completed_tasks": 4,
            "approved_tasks": 3,
            "average_completion_hours": 9,
            "base_l2_attestation": "eas:base:0xccc",
        }).json()
        task = auth_post(c, "/tasks", {
            "title": "Review escrow contract",
            "requirements": {"language": "solidity", "deliverable": "findings"},
            "acceptance_criteria": ["severity labels", "patch suggestions"],
            "deadline": future_deadline(),
            "budget_usdc": 400,
            "category": "smart_contract_review",
        }).json()
        bid = auth_post(c, f"/tasks/{task['id']}/bids", {
            "agent_id": agent["id"],
            "cost_usdc": 300,
            "estimated_hours": 10,
            "proposal": "Static review plus exploit sketches.",
        }).json()
        auth_post(c, f"/bids/{bid['id']}/accept", {})

        submission = auth_post(c, f"/tasks/{task['id']}/submissions", {
            "agent_id": agent["id"],
            "artifact_url": "https://example.com/review.md",
            "summary": "Found two medium severity escrow edge cases.",
        }).json()
        assert submission["status"] == "SUBMITTED"

        approved = auth_post(c, f"/submissions/{submission['id']}/approve", {"approved": True}).json()
        assert approved["task_status"] == "APPROVED"
        assert approved["escrow"]["state"] == "RELEASED"
        assert approved["escrow"]["released_to"] == agent["wallet"]
        updated = auth_get(c, f"/agents/{agent['id']}").json()
        assert updated["completed_tasks"] == 5
        assert updated["approved_tasks"] == 4
        assert updated["reputation_score"] > agent["reputation_score"]


def test_rejected_submission_refunds_poster_minus_arbitration_fee():
    with TestClient(app) as c:
        agent = auth_post(c, "/agents", {
            "name": "Slow Analyst",
            "wallet": "0x4444444444444444444444444444444444444444",
            "capabilities": ["data_analysis"],
            "completed_tasks": 5,
            "approved_tasks": 2,
            "average_completion_hours": 40,
            "base_l2_attestation": "eas:base:0xddd",
        }).json()
        task = auth_post(c, "/tasks", {
            "title": "Analyze CSV",
            "requirements": {"tool": "python", "deliverable": "notebook"},
            "acceptance_criteria": ["charts", "source citations"],
            "deadline": future_deadline(),
            "budget_usdc": 100,
            "category": "data_analysis",
        }).json()
        bid = auth_post(c, f"/tasks/{task['id']}/bids", {
            "agent_id": agent["id"],
            "cost_usdc": 80,
            "estimated_hours": 36,
            "proposal": "Notebook with plots.",
        }).json()
        auth_post(c, f"/bids/{bid['id']}/accept", {})
        sub = auth_post(c, f"/tasks/{task['id']}/submissions", {
            "agent_id": agent["id"],
            "artifact_url": "https://example.com/incomplete.ipynb",
            "summary": "Missing charts.",
        }).json()
        rejected = auth_post(c, f"/submissions/{sub['id']}/approve", {"approved": False}).json()
        assert rejected["task_status"] == "REJECTED"
        assert rejected["escrow"]["state"] == "REFUNDED"
        assert rejected["escrow"]["arbitration_fee_usdc"] == 2
        assert rejected["escrow"]["refund_to_poster_usdc"] == 78


def test_dashboard_and_stats_support_100_registered_concurrent_agents():
    with TestClient(app) as c:
        for i in range(100):
            completed = (i % 20) + 1
            approved = max(0, completed - 1)
            res = auth_post(c, "/agents", {
                "name": f"Worker {i}",
                "wallet": "0x" + f"{i + 1:040x}",
                "capabilities": ["code_generation" if i % 2 == 0 else "content_writing"],
                "completed_tasks": completed,
                "approved_tasks": approved,
                "average_completion_hours": 2 + (i % 12),
                "base_l2_attestation": f"eas:base:0x{i:064x}",
            },)
            assert res.status_code == 200
        task = auth_post(c, "/tasks", {
            "title": "Generate SDK sample",
            "requirements": {"language": "typescript"},
            "acceptance_criteria": ["compiles", "has examples"],
            "deadline": future_deadline(48),
            "budget_usdc": 150,
            "category": "code_generation",
        }).json()
        stats = auth_get(c, "/dashboard/stats").json()
        assert stats["agents_total"] == 100
        assert stats["tasks_total"] == 1
        assert stats["open_tasks"] == 1
        assert stats["registered_capabilities"]["code_generation"] == 50
        html = c.get("/dashboard").text
        assert "Agent Hiring Marketplace" in html
        assert task["title"] in html


def test_requires_api_key_for_mutating_and_private_read_endpoints():
    with TestClient(app) as c:
        assert c.post("/tasks", json={}).status_code == 401
        assert c.get("/dashboard/stats").status_code == 401
        assert c.get("/health").status_code == 200
        assert c.get("/openapi.json").status_code == 200


def test_dashboard_escapes_task_fields_before_rendering_html():
    with TestClient(app) as c:
        auth_post(c, "/tasks", {
            "title": "<script>alert('xss')</script> Review",
            "requirements": {"language": "python"},
            "acceptance_criteria": ["no script execution"],
            "deadline": future_deadline(),
            "budget_usdc": 125,
            "category": "code_generation",
        })
        html = c.get("/dashboard").text
        assert "<script>alert('xss')</script>" not in html
        assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt; Review" in html
