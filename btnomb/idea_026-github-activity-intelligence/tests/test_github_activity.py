from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


def seed(client, full_name, stars, forks, contributors, commits, description="FastAPI AI developer tool", language="Python"):
    response = client.post(
        "/repos/seed",
        headers=HEADERS,
        json={
            "full_name": full_name,
            "description": description,
            "language": language,
            "stars": stars,
            "forks": forks,
            "open_issues": 20,
            "watchers": stars,
            "contributors": contributors,
            "commits": commits,
        },
    )
    assert response.status_code == 201
    return response.json()


def add_snapshot(client, full_name, days_ago, stars, forks, contributors, commits, open_issues=20):
    response = client.post(
        "/snapshots",
        headers=HEADERS,
        json={
            "full_name": full_name,
            "stars": stars,
            "forks": forks,
            "open_issues": open_issues,
            "contributors": contributors,
            "commits": commits,
            "created_at": (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


def test_momentum_scoring_search_and_filters_rank_hot_repo():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    seed(client, "acme/hot-ai", stars=100, forks=10, contributors=5, commits=50, description="LLM agent inference toolkit", language="Python")
    add_snapshot(client, "acme/hot-ai", 30, stars=100, forks=10, contributors=5, commits=50, open_issues=25)
    add_snapshot(client, "acme/hot-ai", 7, stars=130, forks=14, contributors=8, commits=75, open_issues=22)
    add_snapshot(client, "acme/hot-ai", 0, stars=250, forks=35, contributors=20, commits=160, open_issues=10)

    seed(client, "acme/slow-css", stars=1000, forks=200, contributors=40, commits=500, description="CSS component library", language="TypeScript")
    add_snapshot(client, "acme/slow-css", 30, stars=990, forks=198, contributors=40, commits=495)
    add_snapshot(client, "acme/slow-css", 0, stars=1000, forks=200, contributors=40, commits=500)

    repos = client.get("/repos", params={"category": "AI/ML", "q": "agent", "min_score": 1})

    assert repos.status_code == 200
    body = repos.json()
    assert body["count"] == 1
    assert body["repos"][0]["full_name"] == "acme/hot-ai"
    assert body["repos"][0]["momentum_score"] > 100
    assert body["repos"][0]["category"] == "AI/ML"


def test_watchlist_alerts_and_digest_generation_work():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    seed(client, "nous/rising-devtool", 50, 5, 3, 20, description="CLI automation and developer observability", language="Go")
    add_snapshot(client, "nous/rising-devtool", 30, 50, 5, 3, 20)
    add_snapshot(client, "nous/rising-devtool", 0, 140, 20, 10, 95)

    watch = client.post("/watchlist", headers=HEADERS, json={"email": "founder@example.com", "repo_full_name": "nous/rising-devtool", "threshold": 10})
    assert watch.status_code == 201

    alerts = client.post("/alerts/evaluate", headers=HEADERS)
    assert alerts.status_code == 200
    assert alerts.json()["alerts_created"] == 1

    listed = client.get("/alerts", headers=HEADERS, params={"email": "founder@example.com"})
    assert listed.status_code == 200
    assert listed.json()["alerts"][0]["repo_full_name"] == "nous/rising-devtool"
    assert listed.json()["alerts"][0]["delivered"] is True

    digest = client.post("/digest/weekly", headers=HEADERS)
    assert digest.status_code == 200
    assert "DevTools" in digest.json()["digests"]
    assert "nous/rising-devtool" in digest.json()["digests"]["DevTools"]


def test_dashboard_auth_openapi_checkout_and_persistence(tmp_path):
    db_path = tmp_path / "activity.db"
    database_url = f"sqlite:///{db_path}"
    first = TestClient(create_app(database_url=database_url))

    unauthorized = first.post("/repos/seed", json={"full_name": "x/y", "stars": 1, "forks": 0})
    assert unauthorized.status_code == 401

    seed(first, "open/dashboard", 10, 1, 2, 5, description="React frontend dashboard", language="TypeScript")
    docs = first.get("/openapi.json")
    assert docs.status_code == 200
    assert "/poll" in docs.json()["paths"]

    paid = first.post("/plans/checkout", json={"plan": "pro"})
    assert paid.status_code == 402
    assert paid.json()["accepts"][0]["network"] == "base"
    free = first.post("/plans/checkout", json={"plan": "free"})
    assert free.status_code == 200

    second = TestClient(create_app(database_url=database_url))
    dashboard = second.get("/dashboard", params={"q": "dashboard"})
    assert dashboard.status_code == 200
    assert "open/dashboard" in dashboard.text

    detail = second.get("/repos/open/dashboard")
    assert detail.status_code == 200
    assert len(detail.json()["snapshots"]) >= 1


def test_health_and_readiness_endpoints_expose_production_checks():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["service"] == "github-activity-intelligence"

    ready = client.get("/readyz")
    assert ready.status_code == 200
    body = ready.json()
    assert body["status"] == "ok"
    assert body["production_ready"] is True
    assert body["checks"]["database_query"] is True
    assert body["checks"]["schema_initialized"] is True
    assert body["checks"]["pay_to_configured"] is True
    assert body["counts"]["repos"] == 0
    assert body["database_url_kind"] == "sqlite"
