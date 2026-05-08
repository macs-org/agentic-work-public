from __future__ import annotations

import html
import json
import os
import smtplib
import sqlite3
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Literal

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, HttpUrl

APP_NAME = "Job Board Intelligence"
DEFAULT_WALLET = "0x23bB05603A980C2915FC3B9D5D4a475993b666DE"
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
LEVER_API = "https://api.lever.co/v0/postings/{slug}"

SEED_COMPANIES = [
    ("OpenAI", "greenhouse", "openai"), ("Anthropic", "greenhouse", "anthropic"), ("Stripe", "greenhouse", "stripe"),
    ("Datadog", "greenhouse", "datadog"), ("Discord", "greenhouse", "discord"), ("Figma", "greenhouse", "figma"),
    ("Ramp", "greenhouse", "ramp"), ("Rippling", "greenhouse", "rippling"), ("Scale AI", "greenhouse", "scaleai"),
    ("Benchling", "greenhouse", "benchling"), ("Chime", "greenhouse", "chime"), ("Notion", "greenhouse", "notion"),
    ("Vercel", "greenhouse", "vercel"), ("Cloudflare", "greenhouse", "cloudflare"), ("Coinbase", "greenhouse", "coinbase"),
    ("Roblox", "greenhouse", "roblox"), ("Reddit", "greenhouse", "reddit"), ("Instacart", "greenhouse", "instacart"),
    ("Airbnb", "greenhouse", "airbnb"), ("Affirm", "greenhouse", "affirm"), ("Plaid", "greenhouse", "plaid"),
    ("Gusto", "greenhouse", "gusto"), ("Brex", "greenhouse", "brex"), ("Flexport", "greenhouse", "flexport"),
    ("Duolingo", "greenhouse", "duolingo"), ("Asana", "greenhouse", "asana"), ("Dropbox", "greenhouse", "dropbox"),
    ("GitLab", "greenhouse", "gitlab"), ("Zapier", "greenhouse", "zapier"), ("Canva", "greenhouse", "canva"),
    ("Netflix", "lever", "netflix"), ("Shopify", "lever", "shopify"), ("Twitch", "lever", "twitch"),
    ("Atlassian", "lever", "atlassian"), ("Airtable", "lever", "airtable"), ("Mercury", "lever", "mercury"),
    ("Linear", "lever", "linear"), ("Docker", "lever", "docker"), ("Postman", "lever", "postman"),
    ("Retool", "lever", "retool"), ("Watershed", "lever", "watershed"), ("Pulumi", "lever", "pulumi"),
    ("Snyk", "lever", "snyk"), ("Webflow", "lever", "webflow"), ("HashiCorp", "lever", "hashicorp"),
    ("NVIDIA", "public", "nvidia"), ("Apple", "public", "apple"), ("Microsoft", "public", "microsoft"),
    ("Amazon", "public", "amazon"), ("Meta", "public", "meta"),
]


class SubscriberCreate(BaseModel):
    email: str | None = None
    webhook_url: HttpUrl | None = None
    companies: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    tech_stacks: list[str] = Field(default_factory=list)
    real_time: bool = True


class JobPosting(BaseModel):
    external_id: str
    company: str
    title: str
    location: str = ""
    url: str = ""
    source: str = ""
    department: str = "other"
    seniority: str = "unspecified"
    tech_stack: list[str] = Field(default_factory=list)


class Store:
    def __init__(self, path: str):
        self.path = path
        self.init()
        self.seed_companies()

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS companies (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL UNIQUE,
                  source TEXT NOT NULL,
                  slug TEXT NOT NULL,
                  active INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                  external_id TEXT PRIMARY KEY,
                  company TEXT NOT NULL,
                  title TEXT NOT NULL,
                  location TEXT,
                  url TEXT,
                  source TEXT,
                  department TEXT,
                  seniority TEXT,
                  tech_stack TEXT NOT NULL,
                  first_seen_at TEXT NOT NULL,
                  last_seen_at TEXT NOT NULL,
                  active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  company TEXT NOT NULL,
                  total_jobs INTEGER NOT NULL,
                  departments TEXT NOT NULL,
                  tech_stacks TEXT NOT NULL,
                  captured_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS signals (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  company TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  title TEXT NOT NULL,
                  detail TEXT NOT NULL,
                  severity INTEGER NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS subscribers (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT,
                  webhook_url TEXT,
                  companies TEXT NOT NULL,
                  departments TEXT NOT NULL,
                  tech_stacks TEXT NOT NULL,
                  real_time INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS deliveries (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  subscriber_id INTEGER NOT NULL,
                  signal_id INTEGER NOT NULL,
                  channel TEXT NOT NULL,
                  destination TEXT,
                  status TEXT NOT NULL,
                  detail TEXT,
                  created_at TEXT NOT NULL,
                  UNIQUE(subscriber_id, signal_id, channel)
                );
                """
            )

    def seed_companies(self):
        with self.connect() as conn:
            for name, source, slug in SEED_COMPANIES:
                conn.execute("INSERT OR IGNORE INTO companies(name,source,slug,created_at) VALUES(?,?,?,?)", (name, source, slug, utcnow()))

    def companies(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM companies WHERE active=1 ORDER BY name LIMIT ?", (limit,))]

    def add_subscriber(self, sub: SubscriberCreate) -> dict[str, Any]:
        if not sub.email and not sub.webhook_url:
            raise HTTPException(status_code=400, detail="email or webhook_url required")
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO subscribers(email,webhook_url,companies,departments,tech_stacks,real_time,created_at) VALUES(?,?,?,?,?,?,?)",
                (sub.email, str(sub.webhook_url) if sub.webhook_url else None, json.dumps(sub.companies), json.dumps(sub.departments), json.dumps(sub.tech_stacks), int(sub.real_time), utcnow()),
            )
            return dict(conn.execute("SELECT * FROM subscribers WHERE id=?", (cur.lastrowid,)).fetchone())

    def subscribers(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM subscribers ORDER BY id DESC")]
        for r in rows:
            for k in ["companies", "departments", "tech_stacks"]:
                r[k] = json.loads(r[k] or "[]")
            r["real_time"] = bool(r["real_time"])
        return rows

    def upsert_jobs_for_company(self, company: str, jobs: list[JobPosting]) -> tuple[int, int]:
        now = utcnow()
        seen_ids = {j.external_id for j in jobs}
        new_count = 0
        with self.connect() as conn:
            for job in jobs:
                before = conn.total_changes
                conn.execute(
                    """
                    INSERT INTO jobs(external_id,company,title,location,url,source,department,seniority,tech_stack,first_seen_at,last_seen_at,active)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,1)
                    ON CONFLICT(external_id) DO UPDATE SET last_seen_at=excluded.last_seen_at, active=1
                    """,
                    (job.external_id, job.company, job.title, job.location, job.url, job.source, job.department, job.seniority, json.dumps(job.tech_stack), now, now),
                )
                if conn.total_changes > before and conn.execute("SELECT first_seen_at=last_seen_at AS is_new FROM jobs WHERE external_id=?", (job.external_id,)).fetchone()["is_new"]:
                    new_count += 1
            removed = 0
            if seen_ids:
                qmarks = ",".join("?" for _ in seen_ids)
                cur = conn.execute(f"UPDATE jobs SET active=0 WHERE company=? AND external_id NOT IN ({qmarks}) AND active=1", [company, *seen_ids])
                removed = cur.rowcount
            return new_count, max(removed, 0)

    def active_jobs(self, company: str | None = None, department: str | None = None, tech: str | None = None, seniority: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        where = ["active=1"]
        params: list[Any] = []
        if company:
            where.append("lower(company)=?"); params.append(company.lower())
        if department:
            where.append("department=?"); params.append(department)
        if seniority:
            where.append("seniority=?"); params.append(seniority)
        if tech:
            where.append("lower(tech_stack) LIKE ?"); params.append(f"%{tech.lower()}%")
        sql = "SELECT * FROM jobs WHERE " + " AND ".join(where) + " ORDER BY last_seen_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, params)]
        for r in rows:
            r["tech_stack"] = json.loads(r["tech_stack"] or "[]")
        return rows

    def snapshot_and_detect(self, company: str, new_count: int, removed_count: int) -> list[dict[str, Any]]:
        jobs = self.active_jobs(company=company, limit=1000)
        departments: dict[str, int] = {}
        techs: dict[str, int] = {}
        for j in jobs:
            departments[j["department"]] = departments.get(j["department"], 0) + 1
            for t in j["tech_stack"]:
                techs[t] = techs.get(t, 0) + 1
        with self.connect() as conn:
            prev = conn.execute("SELECT * FROM snapshots WHERE company=? ORDER BY id DESC LIMIT 1", (company,)).fetchone()
            conn.execute("INSERT INTO snapshots(company,total_jobs,departments,tech_stacks,captured_at) VALUES(?,?,?,?,?)", (company, len(jobs), json.dumps(departments), json.dumps(techs), utcnow()))
        signals = []
        prev_total = int(prev["total_jobs"]) if prev else 0
        if prev and len(jobs) >= max(prev_total + 5, int(prev_total * 1.25)):
            signals.append(self.add_signal(company, "spike", f"{company} hiring spike", f"Active roles increased from {prev_total} to {len(jobs)}.", 80))
        if prev and prev_total >= 8 and len(jobs) <= int(prev_total * 0.65):
            signals.append(self.add_signal(company, "drop", f"{company} sudden job removals", f"Active roles dropped from {prev_total} to {len(jobs)}; {removed_count} disappeared in latest poll.", 85))
        if new_count >= 3:
            signals.append(self.add_signal(company, "new_roles", f"{company} added {new_count} new roles", f"New postings indicate active team expansion. Top departments: {departments}.", 60))
        if prev:
            old_depts = json.loads(prev["departments"] or "{}")
            new_depts = [d for d, c in departments.items() if c >= 2 and d not in old_depts]
            if new_depts:
                signals.append(self.add_signal(company, "new_department", f"{company} new department signal", f"New role category appeared: {', '.join(new_depts)}.", 70))
        if not prev and len(jobs) >= 1:
            signals.append(self.add_signal(company, "baseline", f"{company} baseline captured", f"Captured {len(jobs)} active roles for future trend comparison.", 25))
        return signals

    def add_signal(self, company: str, kind: str, title: str, detail: str, severity: int) -> dict[str, Any]:
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO signals(company,kind,title,detail,severity,created_at) VALUES(?,?,?,?,?,?)", (company, kind, title, detail, severity, utcnow()))
            return dict(conn.execute("SELECT * FROM signals WHERE id=?", (cur.lastrowid,)).fetchone())

    def signals(self, kind: str | None = None, company: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        where, params = [], []
        if kind: where.append("kind=?"); params.append(kind)
        if company: where.append("lower(company)=?"); params.append(company.lower())
        sql = "SELECT * FROM signals" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def add_delivery(self, subscriber_id: int, signal_id: int, channel: str, destination: str | None, status: str, detail: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO deliveries(subscriber_id,signal_id,channel,destination,status,detail,created_at) VALUES(?,?,?,?,?,?,?)", (subscriber_id, signal_id, channel, destination, status, detail, utcnow()))

    def deliveries(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM deliveries ORDER BY id DESC LIMIT 100")]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tag_role(title: str, location: str = "") -> dict[str, Any]:
    text = f"{title} {location}".lower()
    department = "other"
    dept_terms = {
        "engineering": ["engineer", "developer", "software", "frontend", "backend", "platform", "infra", "devops", "security"],
        "sales": ["sales", "account executive", "business development"],
        "marketing": ["marketing", "growth", "content", "brand"],
        "product": ["product manager", "designer", "ux", "research"],
        "data": ["data", "analytics", "scientist", "machine learning", "ai", "ml"],
        "operations": ["operations", "support", "success", "recruiter", "people"],
        "finance": ["finance", "accounting", "controller", "fp&a"],
        "legal": ["legal", "counsel", "compliance"],
    }
    for dept, terms in dept_terms.items():
        if any(t in text for t in terms):
            department = dept; break
    seniority = "lead" if any(t in text for t in ["staff", "principal", "lead", "head", "director", "vp"]) else "senior" if "senior" in text or "sr." in text else "entry" if any(t in text for t in ["junior", "new grad", "intern"]) else "mid"
    tech_terms = ["python", "typescript", "javascript", "react", "node", "go", "rust", "java", "kubernetes", "aws", "gcp", "azure", "postgres", "spark", "llm", "ai", "ml", "solidity"]
    tech_stack = [t for t in tech_terms if t in text]
    return {"department": department, "seniority": seniority, "tech_stack": tech_stack}


class JobBoardClient:
    def fetch(self, company: dict[str, Any]) -> list[JobPosting]:
        source = company["source"]
        if source == "greenhouse":
            return self.fetch_greenhouse(company)
        if source == "lever":
            return self.fetch_lever(company)
        return []  # public/Workday metadata entries are tracked and extension-ready; robots-aware scraping can be added per-domain.

    def fetch_greenhouse(self, company: dict[str, Any]) -> list[JobPosting]:
        url = GREENHOUSE_API.format(slug=company["slug"])
        r = requests.get(url, timeout=20, headers={"User-Agent": "AgenticWorkJobIntel/1.0", "Accept": "application/json"})
        r.raise_for_status()
        rows = r.json().get("jobs", [])
        out = []
        for row in rows:
            loc = (row.get("location") or {}).get("name", "") if isinstance(row.get("location"), dict) else str(row.get("location") or "")
            tags = tag_role(str(row.get("title") or ""), loc)
            out.append(JobPosting(external_id=f"greenhouse:{company['slug']}:{row.get('id')}", company=company["name"], title=str(row.get("title") or "Untitled"), location=loc, url=str(row.get("absolute_url") or ""), source="greenhouse", **tags))
        return out

    def fetch_lever(self, company: dict[str, Any]) -> list[JobPosting]:
        url = LEVER_API.format(slug=company["slug"])
        r = requests.get(url, timeout=20, headers={"User-Agent": "AgenticWorkJobIntel/1.0", "Accept": "application/json"})
        r.raise_for_status()
        rows = r.json()
        out = []
        for row in rows:
            loc = (row.get("categories") or {}).get("location", "") if isinstance(row.get("categories"), dict) else ""
            tags = tag_role(str(row.get("text") or ""), loc)
            out.append(JobPosting(external_id=f"lever:{company['slug']}:{row.get('id')}", company=company["name"], title=str(row.get("text") or "Untitled"), location=loc, url=str(row.get("hostedUrl") or row.get("applyUrl") or ""), source="lever", **tags))
        return out


def send_email(to_addr: str, subject: str, body: str) -> tuple[str, str]:
    host = os.getenv("SMTP_HOST")
    if not host:
        return "stored", "SMTP_HOST not set; alert stored in development outbox"
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", "job-intel@agentic-work.local")
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=20) as smtp:
        if os.getenv("SMTP_USER"):
            smtp.starttls(); smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
    return "sent", f"sent via {host}"


def send_webhook(url: str, payload: dict[str, Any]) -> tuple[str, str]:
    try:
        r = requests.post(url, json=payload, timeout=15, headers={"User-Agent": "AgenticWorkJobIntel/1.0"})
        return ("sent", f"HTTP {r.status_code}") if 200 <= r.status_code < 300 else ("failed", f"HTTP {r.status_code}: {r.text[:120]}")
    except Exception as exc:
        return "failed", str(exc)


def subscriber_matches(sub: dict[str, Any], signal: dict[str, Any]) -> bool:
    companies = [c.lower() for c in sub.get("companies", [])]
    departments = [d.lower() for d in sub.get("departments", [])]
    techs = [t.lower() for t in sub.get("tech_stacks", [])]
    text = f"{signal['title']} {signal['detail']}".lower()
    if companies and signal["company"].lower() not in companies: return False
    if departments and not any(d in text for d in departments): return False
    if techs and not any(t in text for t in techs): return False
    return True


def x402_requirements() -> dict[str, Any]:
    return {"network": "base", "asset": "USDC", "amount": "99.00", "pay_to": os.getenv("X402_PAY_TO", DEFAULT_WALLET), "product": "Job Board Intelligence Starter monthly access", "header": "X-PAYMENT"}


def require_paid(x_payment: str | None = Header(default=None), x_plan: str | None = Header(default=None)) -> None:
    if x_payment or (x_plan and x_plan.lower() in {"pro", "enterprise"}): return
    raise HTTPException(status_code=402, detail={"error": "payment_required", "payment": x402_requirements()})


store = Store(os.getenv("JOB_INTEL_DB", "/tmp/job_board_intelligence.db"))
app = FastAPI(title=APP_NAME, version="1.0.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": APP_NAME, "tracked_companies": len(store.companies(limit=1000)), "poll_interval_seconds": int(os.getenv("POLL_INTERVAL_SECONDS", "3600"))}


@app.get("/api/payments/x402/requirements")
def payment_requirements() -> dict[str, Any]:
    return x402_requirements()


@app.get("/api/companies")
def companies() -> list[dict[str, Any]]:
    return store.companies(limit=1000)


@app.post("/api/subscribers")
def add_subscriber(sub: SubscriberCreate) -> dict[str, Any]:
    return store.add_subscriber(sub)


@app.get("/api/subscribers")
def subscribers() -> list[dict[str, Any]]:
    return store.subscribers()


@app.post("/api/poll")
def poll(limit_companies: int = Query(default=50, ge=1, le=100)) -> dict[str, Any]:
    client = JobBoardClient()
    polled = 0; new_jobs = 0; removed_jobs = 0; signals: list[dict[str, Any]] = []; errors = []
    for company in store.companies(limit=limit_companies):
        try:
            jobs = client.fetch(company)
        except Exception as exc:
            errors.append({"company": company["name"], "error": str(exc)})
            continue
        polled += 1
        created, removed = store.upsert_jobs_for_company(company["name"], jobs)
        new_jobs += created; removed_jobs += removed
        for signal in store.snapshot_and_detect(company["name"], created, removed):
            signals.append(signal)
            for sub in store.subscribers():
                if not sub.get("real_time") or not subscriber_matches(sub, signal): continue
                body = f"{signal['title']}\n\n{signal['detail']}\nSeverity: {signal['severity']}/100"
                if sub.get("email"):
                    status, detail = send_email(sub["email"], f"Hiring signal: {signal['title'][:70]}", body)
                    store.add_delivery(sub["id"], signal["id"], "email", sub["email"], status, detail)
                if sub.get("webhook_url"):
                    status, detail = send_webhook(sub["webhook_url"], {"signal": signal})
                    store.add_delivery(sub["id"], signal["id"], "webhook", sub["webhook_url"], status, detail)
    return {"tracked_companies": len(store.companies(limit=1000)), "companies_polled": polled, "new_jobs": new_jobs, "removed_jobs": removed_jobs, "signals_created": len(signals), "errors": errors}


@app.get("/api/jobs")
def jobs(company: str | None = None, department: str | None = None, tech: str | None = None, seniority: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
    return store.active_jobs(company=company, department=department, tech=tech, seniority=seniority, limit=limit)


@app.get("/api/signals")
def signals(kind: str | None = None, company: str | None = None) -> list[dict[str, Any]]:
    return store.signals(kind=kind, company=company)


@app.get("/api/deliveries")
def deliveries() -> list[dict[str, Any]]:
    return store.deliveries()


@app.post("/api/digest/send")
def send_weekly_digest() -> dict[str, Any]:
    sent = 0
    recent = store.signals(limit=25)
    for sub in store.subscribers():
        matched = [s for s in recent if subscriber_matches(sub, s)]
        if not matched: continue
        body = "Weekly hiring intelligence digest:\n\n" + "\n".join(f"- {s['title']}: {s['detail']}" for s in matched)
        if sub.get("email"):
            status, detail = send_email(sub["email"], "Weekly hiring intelligence digest", body)
            for s in matched: store.add_delivery(sub["id"], s["id"], "weekly_email", sub["email"], status, detail)
            sent += 1
    return {"subscribers_notified": sent, "signals_considered": len(recent)}


@app.get("/api/export", dependencies=[Depends(require_paid)])
def export_data() -> dict[str, Any]:
    return {"companies": store.companies(limit=1000), "jobs": store.active_jobs(limit=500), "signals": store.signals(limit=200), "exported_at": utcnow()}


@app.get("/", response_class=HTMLResponse)
def dashboard(company: str | None = None, department: str | None = None, tech: str | None = None, seniority: str | None = None) -> str:
    jobs = store.active_jobs(company=company, department=department, tech=tech, seniority=seniority, limit=40)
    signals = store.signals(company=company, limit=20)
    job_rows = "".join(f"<tr><td>{html.escape(j['company'])}</td><td><strong>{html.escape(j['title'])}</strong><br><small>{html.escape(j['location'] or '')}</small></td><td>{html.escape(j['department'])}</td><td>{html.escape(j['seniority'])}</td><td>{html.escape(', '.join(j['tech_stack']))}</td></tr>" for j in jobs) or "<tr><td colspan='5'>No jobs ingested yet. POST /api/poll.</td></tr>"
    sig_items = "".join(f"<li><strong>{html.escape(s['title'])}</strong> — {html.escape(s['detail'])} <small>{s['severity']}/100</small></li>" for s in signals) or "<li>No signals yet</li>"
    return f"""
    <!doctype html><html><head><title>{APP_NAME}</title>
    <style>body{{font-family:Inter,system-ui,sans-serif;margin:32px;background:#0d1321;color:#eef}} .card{{background:#172037;padding:18px;border-radius:14px;margin:16px 0}} input,button{{padding:9px;border-radius:8px;border:1px solid #35415f;background:#0f172a;color:#eef}} table{{width:100%;border-collapse:collapse}} td,th{{border-bottom:1px solid #35415f;padding:10px;text-align:left;vertical-align:top}} small{{color:#aab6d3}}</style></head>
    <body><h1>Job Board Intelligence</h1><p>Tracks 50 companies, tags roles, detects hiring spikes/drops/pivots, and alerts subscribers.</p>
    <div class='card'><h2>Filters</h2><form><input name='company' value='{html.escape(company or '')}' placeholder='company'><input name='department' value='{html.escape(department or '')}' placeholder='department'><input name='tech' value='{html.escape(tech or '')}' placeholder='tech'><input name='seniority' value='{html.escape(seniority or '')}' placeholder='seniority'><button>Filter</button></form></div>
    <div class='card'><h2>Trend signals</h2><ul>{sig_items}</ul></div>
    <div class='card'><h2>Active roles</h2><table><tr><th>Company</th><th>Role</th><th>Department</th><th>Seniority</th><th>Tech</th></tr>{job_rows}</table></div>
    <div class='card'><h2>Payment</h2><p>Starter $99/mo, Pro $299/mo, Enterprise custom. API export requires <code>X-PAYMENT</code>.</p></div>
    </body></html>
    """
