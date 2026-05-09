from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

API_KEY = os.getenv("APP_API_KEY", "dev-api-key")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
DEFAULT_PAY_TO = os.getenv("PAY_TO", "0x9c768177521C9A832B0f8567265ef02E89D0282e")
PLAN_PRICES_CENTS = {"free": 0, "starter": 4900, "pro": 14900, "enterprise": 49900}
STARTED_AT = time.time()
CATEGORY_KEYWORDS = {
    "AI/ML": {"ai", "ml", "llm", "rag", "agent", "model", "neural", "pytorch", "tensorflow", "embedding", "inference"},
    "DevTools": {"cli", "developer", "tool", "sdk", "debug", "lint", "test", "ci", "automation", "observability"},
    "Web3": {"crypto", "ethereum", "solana", "wallet", "defi", "blockchain", "web3", "smart contract", "nft"},
    "Backend": {"api", "server", "database", "postgres", "queue", "worker", "fastapi", "django", "go", "rust"},
    "Frontend": {"react", "vue", "svelte", "css", "ui", "component", "frontend", "nextjs", "tailwind"},
}


class Base(DeclarativeBase):
    pass


class Repo(Base):
    __tablename__ = "repos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False, unique=True, index=True)
    html_url = Column(String, nullable=False)
    description = Column(Text, nullable=False, default="")
    language = Column(String, nullable=True, index=True)
    category = Column(String, nullable=False, index=True, default="Other")
    stars = Column(Integer, nullable=False, default=0)
    forks = Column(Integer, nullable=False, default=0)
    open_issues = Column(Integer, nullable=False, default=0)
    watchers = Column(Integer, nullable=False, default=0)
    contributors = Column(Integer, nullable=False, default=0)
    commits = Column(Integer, nullable=False, default=0)
    momentum_score = Column(Float, nullable=False, default=0.0, index=True)
    last_polled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_full_name = Column(String, nullable=False, index=True)
    stars = Column(Integer, nullable=False)
    forks = Column(Integer, nullable=False)
    open_issues = Column(Integer, nullable=False)
    contributors = Column(Integer, nullable=False)
    commits = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)


class Watchlist(Base):
    __tablename__ = "watchlist"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, index=True)
    repo_full_name = Column(String, nullable=False, index=True)
    threshold = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("email", "repo_full_name", name="uq_watch_email_repo"),)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, index=True)
    repo_full_name = Column(String, nullable=False, index=True)
    momentum_score = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    delivered = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)


class Digest(Base):
    __tablename__ = "digests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String, nullable=False, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class RepoSeed(BaseModel):
    full_name: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")
    description: str = ""
    language: str | None = None
    stars: int = Field(ge=0)
    forks: int = Field(ge=0)
    open_issues: int = Field(ge=0, default=0)
    watchers: int = Field(ge=0, default=0)
    contributors: int = Field(ge=0, default=0)
    commits: int = Field(ge=0, default=0)


class SnapshotCreate(BaseModel):
    full_name: str
    stars: int = Field(ge=0)
    forks: int = Field(ge=0)
    open_issues: int = Field(ge=0, default=0)
    contributors: int = Field(ge=0, default=0)
    commits: int = Field(ge=0, default=0)
    created_at: datetime | None = None


class WatchCreate(BaseModel):
    email: str
    repo_full_name: str
    threshold: float = Field(ge=0)


class PollRequest(BaseModel):
    repos: list[str] = Field(default_factory=list)
    limit: int = Field(default=25, ge=1, le=1000)


class PlanCheckoutRequest(BaseModel):
    plan: str


def make_session_factory(database_url: str):
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    if database_url == "sqlite:///:memory:":
        engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def utcnow() -> datetime:
    # Store naive UTC values for SQLite compatibility while keeping all math in UTC.
    return datetime.utcnow()


def as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def parse_github_datetime(value: str | None) -> datetime:
    if not value:
        return utcnow()
    return as_naive_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="missing_or_invalid_api_key")


def classify_repo(description: str, language: str | None, full_name: str) -> str:
    haystack = f"{full_name} {description} {language or ''}".lower()
    for category, words in CATEGORY_KEYWORDS.items():
        if any(word in haystack for word in words):
            return category
    if language in {"JavaScript", "TypeScript", "HTML", "CSS"}:
        return "Frontend"
    if language in {"Python", "Go", "Rust", "Java", "Ruby", "PHP"}:
        return "Backend"
    return "Other"


def x402_requirements(amount_cents: int, resource: str, description: str) -> dict[str, Any]:
    return {
        "x402Version": 1,
        "error": "X-PAYMENT header is required",
        "description": description,
        "accepts": [
            {
                "scheme": "exact",
                "network": "base",
                "maxAmountRequired": str(amount_cents * 10_000),
                "resource": resource,
                "description": description,
                "mimeType": "application/json",
                "payTo": DEFAULT_PAY_TO,
                "maxTimeoutSeconds": 60,
                "asset": BASE_USDC,
                "outputSchema": {"input": {"type": "http", "method": "POST", "discoverable": True}},
                "extra": {"name": "USD Coin", "version": "2"},
            }
        ],
    }


def repo_to_dict(repo: Repo) -> dict[str, Any]:
    return {
        "full_name": repo.full_name,
        "html_url": repo.html_url,
        "description": repo.description,
        "language": repo.language,
        "category": repo.category,
        "stars": repo.stars,
        "forks": repo.forks,
        "open_issues": repo.open_issues,
        "watchers": repo.watchers,
        "contributors": repo.contributors,
        "commits": repo.commits,
        "momentum_score": round(repo.momentum_score, 2),
        "last_polled_at": repo.last_polled_at.isoformat() if repo.last_polled_at else None,
    }


def upsert_snapshot(db: Session, repo: Repo, when: datetime | None = None) -> Snapshot:
    snap = Snapshot(
        repo_full_name=repo.full_name,
        stars=repo.stars,
        forks=repo.forks,
        open_issues=repo.open_issues,
        contributors=repo.contributors,
        commits=repo.commits,
        created_at=when or utcnow(),
    )
    db.add(snap)
    return snap


def momentum_for_repo(db: Session, repo: Repo, now: datetime | None = None) -> float:
    now = as_naive_utc(now or utcnow())
    current = db.scalar(select(Snapshot).where(Snapshot.repo_full_name == repo.full_name).order_by(Snapshot.created_at.desc()))
    if not current:
        return 0.0
    snapshots = list(db.scalars(select(Snapshot).where(Snapshot.repo_full_name == repo.full_name).order_by(Snapshot.created_at.asc())))

    def baseline(days: int) -> Snapshot:
        cutoff = now - timedelta(days=days)
        older = [s for s in snapshots if s.created_at <= cutoff]
        return older[-1] if older else snapshots[0]

    s7 = baseline(7)
    s30 = baseline(30)
    age_days = max((now - repo.created_at).days, 1)
    star_velocity_7d = max(current.stars - s7.stars, 0) / max(7, min(age_days, 7))
    star_velocity_30d = max(current.stars - s30.stars, 0) / max(30, min(age_days, 30))
    fork_acceleration = max(current.forks - s7.forks, 0) / max(7, min(age_days, 7))
    contributor_growth = max(current.contributors - s30.contributors, 0) / max(s30.contributors, 1)
    commit_velocity = max(current.commits - s7.commits, 0) / 7
    issue_resolution_proxy = max((s30.open_issues - current.open_issues) / max(s30.open_issues, 1), 0)
    score = (
        star_velocity_7d * 8.0
        + star_velocity_30d * 3.0
        + fork_acceleration * 5.0
        + contributor_growth * 25.0
        + commit_velocity * 0.5
        + issue_resolution_proxy * 10.0
    )
    return round(score, 4)


def recompute_scores(db: Session) -> int:
    repos = list(db.scalars(select(Repo)))
    for repo in repos:
        repo.momentum_score = momentum_for_repo(db, repo)
    db.commit()
    return len(repos)


def github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "github-activity-intelligence-mvp"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


async def fetch_github_repo(full_name: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20, headers=github_headers()) as client:
        repo_resp = await client.get(f"https://api.github.com/repos/{full_name}")
        if repo_resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"github_repo_not_found:{full_name}")
        repo_resp.raise_for_status()
        data = repo_resp.json()
        contributors = 0
        commits = 0
        for metric, path in (("contributors", "contributors?per_page=1&anon=true"), ("commits", "commits?per_page=1")):
            resp = await client.get(f"https://api.github.com/repos/{full_name}/{path}")
            link = resp.headers.get("link", "")
            if 'rel="last"' in link:
                try:
                    value = int(link.split("page=")[-1].split(">", 1)[0].split("&", 1)[0])
                except ValueError:
                    value = 1
            else:
                value = len(resp.json()) if resp.status_code == 200 else 0
            if metric == "contributors":
                contributors = value
            else:
                commits = value
        return {
            "full_name": data["full_name"],
            "html_url": data["html_url"],
            "description": data.get("description") or "",
            "language": data.get("language"),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "watchers": data.get("watchers_count", 0),
            "contributors": contributors,
            "commits": commits,
            "created_at": parse_github_datetime(data.get("created_at")),
        }


def save_repo_payload(db: Session, payload: dict[str, Any]) -> Repo:
    full_name = payload["full_name"]
    repo = db.scalar(select(Repo).where(Repo.full_name == full_name))
    if not repo:
        repo = Repo(full_name=full_name, html_url=payload.get("html_url") or f"https://github.com/{full_name}", created_at=payload.get("created_at") or utcnow())
        db.add(repo)
    repo.html_url = payload.get("html_url") or repo.html_url
    repo.description = payload.get("description") or ""
    repo.language = payload.get("language")
    repo.category = classify_repo(repo.description, repo.language, repo.full_name)
    repo.stars = int(payload.get("stars", 0))
    repo.forks = int(payload.get("forks", 0))
    repo.open_issues = int(payload.get("open_issues", 0))
    repo.watchers = int(payload.get("watchers", 0))
    repo.contributors = int(payload.get("contributors", 0))
    repo.commits = int(payload.get("commits", 0))
    repo.last_polled_at = utcnow()
    upsert_snapshot(db, repo)
    db.flush()
    repo.momentum_score = momentum_for_repo(db, repo)
    return repo


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(
        title="GitHub Activity Intelligence",
        description="Monitor GitHub repository momentum, generate rising-star digests, and trigger watchlist alerts.",
        version="0.1.0",
    )
    database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///github_activity.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    SessionLocal = make_session_factory(database_url)
    app.state.database_url = database_url

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def readiness_snapshot(db: Session) -> dict[str, Any]:
        repo_count = db.scalar(select(func.count()).select_from(Repo)) or 0
        snapshot_count = db.scalar(select(func.count()).select_from(Snapshot)) or 0
        watchlist_count = db.scalar(select(func.count()).select_from(Watchlist)) or 0
        api_key_default = API_KEY == "dev-api-key"
        checks = {
            "database_query": True,
            "schema_initialized": True,
            "admin_api_key_configured": bool(API_KEY),
            "admin_api_key_not_default": not api_key_default,
            "pay_to_configured": bool(DEFAULT_PAY_TO),
            "base_usdc_asset_configured": bool(BASE_USDC),
            "github_token_optional": True,
        }
        warnings = []
        if api_key_default:
            warnings.append("APP_API_KEY is using the reviewer default; set a unique secret before public production exposure.")
        if not GITHUB_TOKEN:
            warnings.append("GITHUB_TOKEN is unset; live polling still works at unauthenticated GitHub REST limits.")
        return {
            "status": "ok" if checks["database_query"] and checks["admin_api_key_configured"] else "degraded",
            "production_ready": checks["database_query"] and checks["admin_api_key_configured"] and checks["pay_to_configured"],
            "checks": checks,
            "warnings": warnings,
            "counts": {"repos": int(repo_count), "snapshots": int(snapshot_count), "watchlists": int(watchlist_count)},
            "uptime_seconds": round(time.time() - STARTED_AT, 3),
            "database_url_kind": "sqlite" if app.state.database_url.startswith("sqlite") else "external",
            "service": "github-activity-intelligence",
        }

    @app.get("/health")
    @app.get("/healthz")
    def health(db: Session = Depends(get_db)) -> dict[str, Any]:
        repo_count = db.scalar(select(func.count()).select_from(Repo)) or 0
        return {"status": "ok", "repos": int(repo_count), "service": "github-activity-intelligence"}

    @app.get("/readyz")
    def readyz(db: Session = Depends(get_db)) -> dict[str, Any]:
        snapshot = readiness_snapshot(db)
        if snapshot["status"] != "ok":
            return JSONResponse(status_code=503, content=snapshot)
        return snapshot

    @app.post("/repos/seed", status_code=201, dependencies=[Depends(require_api_key)])
    def seed_repo(payload: RepoSeed, db: Session = Depends(get_db)) -> dict[str, Any]:
        repo_payload = payload.model_dump()
        repo_payload["html_url"] = f"https://github.com/{payload.full_name}"
        repo_payload["created_at"] = utcnow() - timedelta(days=90)
        repo = save_repo_payload(db, repo_payload)
        db.commit()
        db.refresh(repo)
        return repo_to_dict(repo)

    @app.post("/snapshots", status_code=201, dependencies=[Depends(require_api_key)])
    def create_snapshot(payload: SnapshotCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        repo = db.scalar(select(Repo).where(Repo.full_name == payload.full_name))
        if not repo:
            repo = Repo(
                full_name=payload.full_name,
                html_url=f"https://github.com/{payload.full_name}",
                description="",
                category="Other",
                stars=payload.stars,
                forks=payload.forks,
                open_issues=payload.open_issues,
                contributors=payload.contributors,
                commits=payload.commits,
                created_at=as_naive_utc(payload.created_at or utcnow()) - timedelta(days=90),
            )
            db.add(repo)
        snap = Snapshot(
            repo_full_name=payload.full_name,
            stars=payload.stars,
            forks=payload.forks,
            open_issues=payload.open_issues,
            contributors=payload.contributors,
            commits=payload.commits,
            created_at=as_naive_utc(payload.created_at or utcnow()),
        )
        db.add(snap)
        repo.stars = payload.stars
        repo.forks = payload.forks
        repo.open_issues = payload.open_issues
        repo.contributors = payload.contributors
        repo.commits = payload.commits
        repo.momentum_score = momentum_for_repo(db, repo)
        db.commit()
        return {"repo_full_name": snap.repo_full_name, "created_at": snap.created_at.isoformat(), "momentum_score": round(repo.momentum_score, 2)}

    @app.post("/poll", dependencies=[Depends(require_api_key)])
    async def poll_repos(payload: PollRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
        names = payload.repos or [r.full_name for r in db.scalars(select(Repo.full_name).order_by(Repo.momentum_score.desc()).limit(payload.limit))]
        names = names[: payload.limit]
        polled: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for full_name in names:
            try:
                repo_payload = await fetch_github_repo(full_name)
                repo = save_repo_payload(db, repo_payload)
                polled.append(repo_to_dict(repo))
            except Exception as exc:  # compact MVP: continue per-repo and report failures
                errors.append({"repo": full_name, "error": str(exc)})
        db.commit()
        alerts = evaluate_watchlists(db)
        return {"polled": len(polled), "repos": polled, "alerts_created": alerts, "errors": errors}

    @app.post("/scores/recompute", dependencies=[Depends(require_api_key)])
    def recompute(db: Session = Depends(get_db)) -> dict[str, int]:
        return {"repos_scored": recompute_scores(db)}

    @app.get("/repos")
    def list_repos(
        category: str | None = None,
        language: str | None = None,
        q: str | None = None,
        min_score: float = 0,
        limit: int = Query(default=25, ge=1, le=200),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        query = select(Repo).where(Repo.momentum_score >= min_score)
        if category:
            query = query.where(Repo.category == category)
        if language:
            query = query.where(Repo.language == language)
        if q:
            like = f"%{q.lower()}%"
            query = query.where(func.lower(Repo.full_name + " " + Repo.description).like(like))
        repos = list(db.scalars(query.order_by(Repo.momentum_score.desc(), Repo.stars.desc()).limit(limit)))
        return {"count": len(repos), "repos": [repo_to_dict(repo) for repo in repos]}

    @app.get("/repos/{owner}/{name}")
    def repo_detail(owner: str, name: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        full_name = f"{owner}/{name}"
        repo = db.scalar(select(Repo).where(Repo.full_name == full_name))
        if not repo:
            raise HTTPException(status_code=404, detail="repo_not_found")
        snaps = list(db.scalars(select(Snapshot).where(Snapshot.repo_full_name == full_name).order_by(Snapshot.created_at.desc()).limit(30)))
        out = repo_to_dict(repo)
        out["snapshots"] = [
            {
                "stars": s.stars,
                "forks": s.forks,
                "open_issues": s.open_issues,
                "contributors": s.contributors,
                "commits": s.commits,
                "created_at": s.created_at.isoformat(),
            }
            for s in snaps
        ]
        return out

    @app.post("/watchlist", status_code=201, dependencies=[Depends(require_api_key)])
    def create_watch(payload: WatchCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        repo = db.scalar(select(Repo).where(Repo.full_name == payload.repo_full_name))
        if not repo:
            raise HTTPException(status_code=404, detail="repo_not_found")
        watch = db.scalar(select(Watchlist).where(Watchlist.email == payload.email, Watchlist.repo_full_name == payload.repo_full_name))
        if not watch:
            watch = Watchlist(email=payload.email, repo_full_name=payload.repo_full_name, threshold=payload.threshold, created_at=utcnow())
            db.add(watch)
        else:
            watch.threshold = payload.threshold
        db.commit()
        return {"email": watch.email, "repo_full_name": watch.repo_full_name, "threshold": watch.threshold}

    @app.post("/alerts/evaluate", dependencies=[Depends(require_api_key)])
    def evaluate_alerts(db: Session = Depends(get_db)) -> dict[str, int]:
        return {"alerts_created": evaluate_watchlists(db)}

    @app.get("/alerts", dependencies=[Depends(require_api_key)])
    def list_alerts(email: str | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
        query = select(Alert)
        if email:
            query = query.where(Alert.email == email)
        alerts = list(db.scalars(query.order_by(Alert.created_at.desc()).limit(100)))
        return {
            "count": len(alerts),
            "alerts": [
                {
                    "email": a.email,
                    "repo_full_name": a.repo_full_name,
                    "momentum_score": round(a.momentum_score, 2),
                    "threshold": a.threshold,
                    "delivered": bool(a.delivered),
                    "created_at": a.created_at.isoformat(),
                }
                for a in alerts
            ],
        }

    @app.post("/digest/weekly", dependencies=[Depends(require_api_key)])
    def weekly_digest(db: Session = Depends(get_db)) -> dict[str, Any]:
        grouped: dict[str, list[Repo]] = defaultdict(list)
        repos = list(db.scalars(select(Repo).order_by(Repo.category.asc(), Repo.momentum_score.desc())))
        for repo in repos:
            if len(grouped[repo.category]) < 10:
                grouped[repo.category].append(repo)
        digests: dict[str, str] = {}
        for category, items in grouped.items():
            body = render_digest(category, items)
            db.add(Digest(category=category, body=body, created_at=utcnow()))
            digests[category] = body
        db.commit()
        return {"categories": len(digests), "digests": digests}

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(category: str | None = None, q: str | None = None, db: Session = Depends(get_db)) -> str:
        query = select(Repo)
        if category:
            query = query.where(Repo.category == category)
        if q:
            like = f"%{q.lower()}%"
            query = query.where(func.lower(Repo.full_name + " " + Repo.description).like(like))
        repos = list(db.scalars(query.order_by(Repo.momentum_score.desc()).limit(50)))
        rows = "".join(
            f"<tr><td><a href='{r.html_url}'>{r.full_name}</a></td><td>{r.category}</td><td>{r.language or ''}</td>"
            f"<td>{r.stars}</td><td>{r.forks}</td><td>{round(r.momentum_score, 2)}</td><td>{r.description[:120]}</td></tr>"
            for r in repos
        )
        return f"""
        <html><head><title>GitHub Activity Intelligence</title>
        <style>body{{font-family:system-ui;margin:2rem}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:.5rem;text-align:left}}.pill{{background:#eef;border-radius:999px;padding:.2rem .5rem}}</style></head>
        <body><h1>GitHub Activity Intelligence</h1><p class='pill'>{len(repos)} repos shown · filters: category={category or 'any'} q={q or 'any'}</p>
        <form><input name='q' placeholder='search repos or descriptions' value='{q or ''}'><input name='category' placeholder='category' value='{category or ''}'><button>Filter</button></form>
        <table><thead><tr><th>Repo</th><th>Category</th><th>Language</th><th>Stars</th><th>Forks</th><th>Momentum</th><th>Description</th></tr></thead><tbody>{rows}</tbody></table>
        </body></html>
        """

    @app.post("/plans/checkout", response_model=None)
    def plan_checkout(payload: PlanCheckoutRequest, x_payment: str | None = Header(default=None, alias="X-PAYMENT")) -> Any:
        if payload.plan not in PLAN_PRICES_CENTS:
            raise HTTPException(status_code=400, detail="unknown plan")
        amount = PLAN_PRICES_CENTS[payload.plan]
        if amount == 0:
            return {"plan": payload.plan, "status": "active", "amount_cents": 0}
        if not x_payment:
            return JSONResponse(status_code=402, content=x402_requirements(amount, "/plans/checkout", f"Activate {payload.plan} plan"))
        return {"plan": payload.plan, "status": "payment_received_demo", "amount_cents": amount, "receipt_id": "rcpt_" + secrets.token_hex(8)}

    return app


def evaluate_watchlists(db: Session) -> int:
    created = 0
    watches = list(db.scalars(select(Watchlist)))
    for watch in watches:
        repo = db.scalar(select(Repo).where(Repo.full_name == watch.repo_full_name))
        if not repo or repo.momentum_score < watch.threshold:
            continue
        already = db.scalar(select(Alert).where(Alert.email == watch.email, Alert.repo_full_name == watch.repo_full_name, Alert.threshold == watch.threshold))
        if already:
            continue
        db.add(
            Alert(
                email=watch.email,
                repo_full_name=watch.repo_full_name,
                momentum_score=repo.momentum_score,
                threshold=watch.threshold,
                delivered=1,
                created_at=utcnow(),
            )
        )
        created += 1
    db.commit()
    return created


def render_digest(category: str, repos: list[Repo]) -> str:
    lines = [f"Weekly Rising Stars — {category}", "", "Top repositories by composite momentum score:"]
    for idx, repo in enumerate(repos[:10], 1):
        lines.append(f"{idx}. {repo.full_name} — score {repo.momentum_score:.2f}, ⭐ {repo.stars}, forks {repo.forks}, {repo.language or 'unknown'}")
    if not repos:
        lines.append("No repositories yet.")
    return "\n".join(lines)


app = create_app()
