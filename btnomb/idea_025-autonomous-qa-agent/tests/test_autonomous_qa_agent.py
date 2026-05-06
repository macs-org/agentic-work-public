from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def make_client_and_key() -> tuple[TestClient, str]:
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    agent = client.post("/agents", json={"name": "qa-owner", "plan": "starter"}).json()
    return client, agent["api_key"]


def test_yaml_suite_is_parsed_and_manual_run_executes_all_assertion_types():
    client, api_key = make_client_and_key()
    yaml_definition = """
name: Demo QA Suite
schedule:
  interval: daily
alerts:
  emails:
    - qa@example.com
cases:
  - id: exact_case
    input: Say hello
    expected: hello world
    mock_response: hello world
    assertions:
      - type: exact
        value: hello world
  - id: contains_case
    input: Summarize pricing
    expected: Starter costs $49/mo
    mock_response: "Pricing: Starter costs $49/mo and Pro costs $149/mo."
    assertions:
      - type: contains
        value: Starter costs $49/mo
  - id: regex_case
    input: Return ticket number
    expected: TICKET-123
    mock_response: Created ticket TICKET-123 successfully.
    assertions:
      - type: regex
        pattern: "TICKET-[0-9]+"
  - id: semantic_case
    input: Explain refund policy
    expected: Refunds are processed quickly for failed runs
    mock_response: Failed QA runs get quick refunds
    assertions:
      - type: similarity
        value: Refunds are processed quickly for failed runs
        threshold: 0.3
"""

    suite_response = client.post(
        "/suites",
        headers={"X-API-Key": api_key},
        json={"definition": yaml_definition},
    )

    assert suite_response.status_code == 201
    suite = suite_response.json()
    assert suite["name"] == "Demo QA Suite"
    assert suite["schedule_interval"] == "daily"
    assert suite["case_count"] == 4
    assert suite["next_run_at"] is not None

    run_response = client.post(f"/suites/{suite['suite_id']}/run", headers={"X-API-Key": api_key})

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "passed"
    assert run["total"] == 4
    assert run["passed"] == 4
    assert run["pass_rate"] == 1.0
    assert {result["case_id"] for result in run["results"]} == {"exact_case", "contains_case", "regex_case", "semantic_case"}


def test_regression_detection_creates_dashboard_alert_when_previously_passing_case_fails():
    client, api_key = make_client_and_key()
    definition = {
        "name": "Regression suite",
        "schedule": {"interval": "manual"},
        "cases": [
            {
                "id": "stable_answer",
                "input": "What is the status?",
                "expected": "ok",
                "mock_responses": ["ok", "broken"],
                "assertions": [{"type": "exact", "value": "ok"}],
            }
        ],
    }
    suite = client.post("/suites", headers={"X-API-Key": api_key}, json={"definition": definition}).json()

    first = client.post(f"/suites/{suite['suite_id']}/run", headers={"X-API-Key": api_key})
    second = client.post(f"/suites/{suite['suite_id']}/run", headers={"X-API-Key": api_key})

    assert first.status_code == 201
    assert first.json()["status"] == "passed"
    assert second.status_code == 201
    body = second.json()
    assert body["status"] == "failed"
    assert body["regression_count"] == 1
    assert body["results"][0]["diff"].startswith("--- expected")

    alerts = client.get("/alerts", headers={"X-API-Key": api_key}).json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "regression"
    assert alerts[0]["channel"] == "dashboard"
    assert alerts[0]["status"] == "captured:dashboard"


def test_scheduler_tick_runs_due_suite_and_schedule_endpoint_represents_history():
    client, api_key = make_client_and_key()
    definition = {
        "name": "Hourly suite",
        "schedule": {"interval": "hourly"},
        "cases": [
            {
                "id": "contains",
                "input": "Ping",
                "expected": "pong",
                "mock_response": "agent says pong",
                "assertions": [{"type": "contains", "value": "pong"}],
            }
        ],
    }
    suite = client.post("/suites", headers={"X-API-Key": api_key}, json={"definition": definition}).json()

    schedules_before = client.get("/schedules", headers={"X-API-Key": api_key}).json()["schedules"]
    assert schedules_before[0]["due"] is True

    tick = client.post("/scheduler/tick", headers={"X-API-Key": api_key})

    assert tick.status_code == 200
    assert tick.json()["triggered"] == 1
    schedules_after = client.get("/schedules", headers={"X-API-Key": api_key}).json()["schedules"]
    assert schedules_after[0]["last_run_at"] is not None
    assert schedules_after[0]["due"] is False
    runs = client.get(f"/runs?suite_id={suite['suite_id']}", headers={"X-API-Key": api_key}).json()["runs"]
    assert len(runs) == 1
    assert runs[0]["trigger"] == "scheduler"


def test_drift_detection_alerts_when_semantic_similarity_drops():
    client, api_key = make_client_and_key()
    definition = {
        "name": "Drift suite",
        "drift_threshold": 0.2,
        "alerts": {"webhooks": ["capture-only"]},
        "cases": [
            {
                "id": "meaning",
                "input": "Describe uptime",
                "expected": "service uptime reliable green",
                "mock_responses": ["service uptime reliable green", "invoice banana truck"],
                "assertions": [
                    {"type": "similarity", "value": "service uptime reliable green", "threshold": 0.0}
                ],
            }
        ],
    }
    suite = client.post("/suites", headers={"X-API-Key": api_key}, json={"definition": definition}).json()

    assert client.post(f"/suites/{suite['suite_id']}/run", headers={"X-API-Key": api_key}).json()["drift_count"] == 0
    second = client.post(f"/suites/{suite['suite_id']}/run", headers={"X-API-Key": api_key}).json()

    assert second["status"] == "passed"
    assert second["drift_count"] == 1
    alerts = client.get("/alerts", headers={"X-API-Key": api_key}).json()["alerts"]
    assert alerts[0]["alert_type"] == "drift"
    assert alerts[0]["channel"] == "webhook"
    assert alerts[0]["status"] == "captured:non_http_webhook"


def test_dashboard_reports_deploy_webhook_and_x402_plan_checkout():
    client, api_key = make_client_and_key()
    suite = client.post(
        "/suites",
        headers={"X-API-Key": api_key},
        json={
            "definition": {
                "name": "Deploy suite",
                "schedule": "on_deploy",
                "cases": [
                    {
                        "id": "deploy",
                        "input": "Check deploy",
                        "expected": "ready",
                        "mock_response": "ready",
                        "assertion": "exact",
                    }
                ],
            }
        },
    ).json()

    deploy_run = client.post(f"/webhooks/deploy/{suite['suite_id']}", headers={"X-API-Key": api_key})
    summary = client.get("/reports/summary", headers={"X-API-Key": api_key})
    checkout = client.post("/plans/checkout", headers={"X-API-Key": api_key}, json={"plan": "pro"})
    dashboard = client.get("/dashboard", headers={"X-API-Key": api_key})

    assert deploy_run.status_code == 201
    assert deploy_run.json()["trigger"] == "deploy_webhook"
    assert summary.json()["suites"][0]["latest_pass_rate"] == 1.0
    assert checkout.status_code == 402
    assert checkout.json()["x402Version"] == 1
    assert checkout.json()["accepts"][0]["maxAmountRequired"] == str(14900 * 10_000)
    assert dashboard.status_code == 200
    assert "Autonomous QA Agent" in dashboard.text
    assert "Deploy suite" in dashboard.text


def test_api_key_auth_required_for_protected_endpoints():
    client, _api_key = make_client_and_key()

    response = client.get("/suites")

    assert response.status_code == 401
    assert response.json()["detail"] == "missing_or_invalid_api_key"
