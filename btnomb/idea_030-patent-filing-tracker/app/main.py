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

APP_NAME = "Patent Filing Tracker"
DEFAULT_PATENTSVIEW_API = "https://search.patentsview.org/api/v1/patent/"
DEFAULT_WALLET = "0x23bB05603A980C2915FC3B9D5D4a475993b666DE"


class WatchlistCreate(BaseModel):
    kind: Literal["company", "keyword"]
    value: str = Field(min_length=2, max_length=200)
    email: str | None = None
    webhook_url: HttpUrl | None = None


class PatentFiling(BaseModel):
    patent_id: str
    title: str
    abstract: str = ""
    assignee: str = ""
    publication_date: str = ""
    filing_date: str = ""
    cpc_category: str = ""
    source_url: str = ""


class PatentStore:
    def __init__(self, path: str):
        self.path = path
        self.init()

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS watchlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL CHECK(kind IN ('company', 'keyword')),
                    value TEXT NOT NULL,
                    email TEXT,
                    webhook_url TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS filings (
                    patent_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT,
                    assignee TEXT,
                    publication_date TEXT,
                    filing_date TEXT,
                    cpc_category TEXT,
                    source_url TEXT,
                    summary TEXT NOT NULL,
                    strategic_implication TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    watchlist_id INTEGER NOT NULL,
                    patent_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    destination TEXT,
                    status TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(watchlist_id, patent_id, channel)
                );
                """
            )

    def add_watchlist(self, item: WatchlistCreate) -> dict[str, Any]:
        now = utcnow()
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO watchlists(kind,value,email,webhook_url,created_at) VALUES(?,?,?,?,?)",
                (item.kind, item.value.strip(), item.email, str(item.webhook_url) if item.webhook_url else None, now),
            )
            row = conn.execute("SELECT * FROM watchlists WHERE id=?", (cur.lastrowid,)).fetchone()
            return dict(row)

    def list_watchlists(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM watchlists WHERE active=1 ORDER BY id DESC")]

    def upsert_filing(self, filing: PatentFiling, summary: dict[str, str]) -> bool:
        now = utcnow()
        with self.connect() as conn:
            before = conn.total_changes
            conn.execute(
                """
                INSERT OR IGNORE INTO filings(
                    patent_id,title,abstract,assignee,publication_date,filing_date,cpc_category,source_url,
                    summary,strategic_implication,first_seen_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    filing.patent_id,
                    filing.title,
                    filing.abstract,
                    filing.assignee,
                    filing.publication_date,
                    filing.filing_date,
                    filing.cpc_category,
                    filing.source_url,
                    summary["summary"],
                    summary["strategic_implication"],
                    now,
                ),
            )
            return conn.total_changes > before

    def list_filings(self, q: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = "SELECT * FROM filings"
        params: list[Any] = []
        if q:
            sql += " WHERE lower(title || ' ' || abstract || ' ' || assignee || ' ' || cpc_category) LIKE ?"
            params.append(f"%{q.lower()}%")
        sql += " ORDER BY first_seen_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def add_alert(self, watchlist_id: int, patent_id: str, channel: str, destination: str | None, status: str, detail: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO alerts(watchlist_id,patent_id,channel,destination,status,detail,created_at) VALUES(?,?,?,?,?,?,?)",
                (watchlist_id, patent_id, channel, destination, status, detail, utcnow()),
            )

    def trends(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT COALESCE(NULLIF(assignee,''),'Unknown') AS assignee,
                       COALESCE(NULLIF(cpc_category,''),'Uncategorized') AS category,
                       substr(COALESCE(NULLIF(publication_date,''), first_seen_at),1,7) AS month,
                       COUNT(*) AS filings
                FROM filings
                GROUP BY assignee, category, month
                ORDER BY filings DESC, month DESC
                LIMIT 25
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def list_alerts(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))]


class PatentsViewClient:
    def __init__(self, api_base: str | None = None):
        self.api_base = api_base or os.getenv("PATENTSVIEW_API_BASE", DEFAULT_PATENTSVIEW_API)

    def search(self, kind: str, value: str, per_page: int = 10) -> list[PatentFiling]:
        if kind == "company":
            query = {"_text_any": {"assignees.assignee_organization": value}}
        else:
            query = {"_text_any": {"patent_title": value, "patent_abstract": value}}
        fields = [
            "patent_id",
            "patent_title",
            "patent_abstract",
            "patent_date",
            "patent_application_date",
            "assignees.assignee_organization",
            "cpcs.cpc_group_id",
        ]
        params = {"q": json.dumps(query), "f": json.dumps(fields), "o": json.dumps({"per_page": per_page})}
        resp = requests.get(self.api_base, params=params, headers={"User-Agent": "AgenticWorkPatentTracker/1.0"}, timeout=25)
        resp.raise_for_status()
        if "application/json" not in resp.headers.get("content-type", ""):
            raise RuntimeError(f"PatentsView returned non-JSON response from {self.api_base}")
        payload = resp.json()
        return [normalize_patent(row) for row in extract_patent_rows(payload)]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def extract_patent_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("patents"), list):
        return payload["patents"]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("patents"), list):
        return data["patents"]
    if isinstance(data, list):
        return data
    if isinstance(payload.get("results"), list):
        return payload["results"]
    return []


def first_nested(value: Any, *keys: str) -> str:
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, dict):
        for key in keys:
            if key in value and value[key]:
                return str(value[key])
    return ""


def normalize_patent(row: dict[str, Any]) -> PatentFiling:
    patent_id = str(row.get("patent_id") or row.get("patent_number") or row.get("id") or row.get("application_number") or "unknown")
    assignee = first_nested(row.get("assignees"), "assignee_organization", "organization") or str(row.get("assignee") or "")
    cpc = first_nested(row.get("cpcs"), "cpc_group_id", "cpc_subgroup_id") or str(row.get("cpc_category") or "")
    return PatentFiling(
        patent_id=patent_id,
        title=str(row.get("patent_title") or row.get("title") or "Untitled patent"),
        abstract=str(row.get("patent_abstract") or row.get("abstract") or ""),
        assignee=assignee,
        publication_date=str(row.get("patent_date") or row.get("publication_date") or ""),
        filing_date=str(row.get("patent_application_date") or row.get("filing_date") or ""),
        cpc_category=cpc,
        source_url=f"https://patents.google.com/patent/US{patent_id}" if patent_id != "unknown" else "",
    )


def summarize_filing(filing: PatentFiling) -> dict[str, str]:
    text = f"{filing.title}. {filing.abstract}".strip()
    words = text.split()
    compact = " ".join(words[:34]) + ("..." if len(words) > 34 else "")
    lower = text.lower()
    if any(term in lower for term in ["neural", "model", "machine learning", "artificial intelligence", "agent"]):
        category = "AI / automation"
    elif any(term in lower for term in ["battery", "semiconductor", "chip", "sensor"]):
        category = "deep tech / hardware"
    elif any(term in lower for term in ["drug", "therapy", "medical", "diagnostic"]):
        category = "life sciences"
    else:
        category = filing.cpc_category or "general technology"
    assignee = filing.assignee or "the filer"
    return {
        "summary": compact or filing.title,
        "tech_category": category,
        "strategic_implication": f"{assignee} may be investing in {category}; monitor follow-on filings and competitor overlap.",
    }


def deliver_email(to_addr: str, subject: str, body: str) -> tuple[str, str]:
    host = os.getenv("SMTP_HOST")
    if not host:
        return "stored", "SMTP_HOST not set; alert stored in development outbox"
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", "patents@agentic-work.local")
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        if os.getenv("SMTP_USER"):
            smtp.starttls()
            smtp.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
    return "sent", f"sent via {host}"


def deliver_webhook(url: str, payload: dict[str, Any]) -> tuple[str, str]:
    try:
        r = requests.post(url, json=payload, timeout=15, headers={"User-Agent": "AgenticWorkPatentTracker/1.0"})
        if 200 <= r.status_code < 300:
            return "sent", f"HTTP {r.status_code}"
        return "failed", f"HTTP {r.status_code}: {r.text[:160]}"
    except Exception as exc:  # keep polling resilient
        return "failed", str(exc)


def require_paid_access(x_payment: str | None = Header(default=None), x_plan: str | None = Header(default=None)) -> None:
    if x_payment or (x_plan and x_plan.lower() in {"pro", "enterprise"}):
        return
    raise HTTPException(status_code=402, detail={"error": "payment_required", "payment": x402_requirements()})


def x402_requirements() -> dict[str, Any]:
    return {
        "network": "base",
        "asset": "USDC",
        "amount": "79.00",
        "pay_to": os.getenv("X402_PAY_TO", DEFAULT_WALLET),
        "product": "Patent Filing Tracker Starter monthly access",
        "header": "X-PAYMENT",
    }


db_path = os.getenv("PATENT_TRACKER_DB", "/tmp/patent_tracker.db")
store = PatentStore(db_path)
app = FastAPI(title=APP_NAME, version="1.0.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": APP_NAME, "patentsview_api": os.getenv("PATENTSVIEW_API_BASE", DEFAULT_PATENTSVIEW_API)}


@app.get("/api/payments/x402/requirements")
def payment_requirements() -> dict[str, Any]:
    return x402_requirements()


@app.post("/api/watchlists")
def create_watchlist(item: WatchlistCreate) -> dict[str, Any]:
    return store.add_watchlist(item)


@app.get("/api/watchlists")
def list_watchlists() -> list[dict[str, Any]]:
    return store.list_watchlists()


@app.post("/api/poll")
def poll_patents(per_watchlist: int = Query(default=5, ge=1, le=25)) -> dict[str, Any]:
    client = PatentsViewClient()
    created = 0
    matched = 0
    errors: list[dict[str, str]] = []
    for watch in store.list_watchlists():
        try:
            filings = client.search(watch["kind"], watch["value"], per_page=per_watchlist)
        except Exception as exc:
            errors.append({"watchlist": watch["value"], "error": str(exc)})
            continue
        for filing in filings:
            matched += 1
            summary = summarize_filing(filing)
            is_new = store.upsert_filing(filing, summary)
            if is_new:
                created += 1
                alert_payload = {"watchlist": watch, "filing": filing.model_dump(), "summary": summary}
                if watch.get("email"):
                    subject = f"New patent filing match: {filing.title[:80]}"
                    body = f"{summary['summary']}\n\nStrategic implication: {summary['strategic_implication']}\n\n{filing.source_url}"
                    status, detail = deliver_email(watch["email"], subject, body)
                    store.add_alert(watch["id"], filing.patent_id, "email", watch["email"], status, detail)
                if watch.get("webhook_url"):
                    status, detail = deliver_webhook(watch["webhook_url"], alert_payload)
                    store.add_alert(watch["id"], filing.patent_id, "webhook", watch["webhook_url"], status, detail)
    return {"watchlists": len(store.list_watchlists()), "matched": matched, "new_filings": created, "errors": errors}


@app.get("/api/filings")
def list_filings(q: str | None = None, limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return store.list_filings(q=q, limit=limit)


@app.get("/api/trends")
def trend_charts() -> list[dict[str, Any]]:
    return store.trends()


@app.get("/api/alerts")
def list_alerts() -> list[dict[str, Any]]:
    return store.list_alerts()


@app.get("/api/export", dependencies=[Depends(require_paid_access)])
def export_data() -> dict[str, Any]:
    return {"filings": store.list_filings(limit=200), "trends": store.trends(), "exported_at": utcnow()}


@app.get("/", response_class=HTMLResponse)
def dashboard(q: str | None = None) -> str:
    filings = store.list_filings(q=q, limit=25)
    watchlists = store.list_watchlists()
    trends = store.trends()[:10]
    filing_rows = "".join(
        f"<tr><td>{html.escape(f['publication_date'] or f['first_seen_at'][:10])}</td><td>{html.escape(f['assignee'] or 'Unknown')}</td>"
        f"<td><strong>{html.escape(f['title'])}</strong><br><small>{html.escape(f['summary'])}</small></td>"
        f"<td>{html.escape(f['strategic_implication'])}</td></tr>"
        for f in filings
    ) or "<tr><td colspan='4'>No filings yet. Add a watchlist and POST /api/poll.</td></tr>"
    watch_items = "".join(f"<li>{html.escape(w['kind'])}: {html.escape(w['value'])}</li>" for w in watchlists) or "<li>No watchlists yet</li>"
    trend_items = "".join(f"<li>{html.escape(t['assignee'])} / {html.escape(t['category'])} / {html.escape(t['month'])}: {t['filings']}</li>" for t in trends) or "<li>No trend data yet</li>"
    return f"""
    <!doctype html><html><head><title>{APP_NAME}</title>
    <style>body{{font-family:Inter,system-ui,sans-serif;margin:32px;background:#0b1020;color:#eef}} .card{{background:#151b31;padding:20px;border-radius:14px;margin:16px 0}} input,button{{padding:10px;border-radius:8px;border:1px solid #334}} table{{width:100%;border-collapse:collapse}} td,th{{border-bottom:1px solid #334;padding:10px;text-align:left;vertical-align:top}} small{{color:#aab}}</style></head>
    <body><h1>Patent Filing Tracker</h1><p>USPTO PatentsView watchlists, AI summaries, alerts, and trend intelligence.</p>
    <div class='card'><h2>Search recent filings</h2><form><input name='q' value='{html.escape(q or '')}' placeholder='company, keyword, CPC'><button>Filter</button></form></div>
    <div class='card'><h2>Active watchlists</h2><ul>{watch_items}</ul><p>Create via <code>POST /api/watchlists</code>, poll via <code>POST /api/poll</code>.</p></div>
    <div class='card'><h2>Recent filings</h2><table><tr><th>Date</th><th>Assignee</th><th>Filing</th><th>Strategic implication</th></tr>{filing_rows}</table></div>
    <div class='card'><h2>Trend chart data</h2><ul>{trend_items}</ul></div>
    <div class='card'><h2>Payment</h2><p>Starter $79/mo, Pro $249/mo, Enterprise $799/mo. Export endpoint is x402-gated; see <code>/api/payments/x402/requirements</code>.</p></div>
    </body></html>
    """
