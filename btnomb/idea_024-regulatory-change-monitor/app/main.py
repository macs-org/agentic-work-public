from __future__ import annotations

import html
import json
import os
import smtplib
import sqlite3
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, HttpUrl

APP_NAME = "Regulatory Change Monitor"
DEFAULT_WALLET = "0x23bB05603A980C2915FC3B9D5D4a475993b666DE"
FEDERAL_REGISTER_API = "https://www.federalregister.gov/api/v1/documents.json"
AGENCY_MAP = {
    "SEC": "securities-and-exchange-commission",
    "FDA": "food-and-drug-administration",
    "FCC": "federal-communications-commission",
    "CFTC": "commodity-futures-trading-commission",
}


class SubscriberCreate(BaseModel):
    email: str | None = None
    webhook_url: HttpUrl | None = None
    agencies: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)


class RegulatoryDocument(BaseModel):
    source_id: str
    agency: str
    title: str
    body: str = ""
    document_type: str = "notice"
    publication_date: str = ""
    effective_date: str = ""
    url: str = ""
    topics: list[str] = Field(default_factory=list)


class Store:
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
                CREATE TABLE IF NOT EXISTS subscribers (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT,
                  webhook_url TEXT,
                  agencies TEXT NOT NULL,
                  topics TEXT NOT NULL,
                  industries TEXT NOT NULL,
                  active INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                  source_id TEXT PRIMARY KEY,
                  agency TEXT NOT NULL,
                  title TEXT NOT NULL,
                  document_type TEXT,
                  publication_date TEXT,
                  effective_date TEXT,
                  url TEXT,
                  topics TEXT NOT NULL,
                  affected_industries TEXT NOT NULL,
                  summary TEXT NOT NULL,
                  action_required TEXT NOT NULL,
                  impact_score INTEGER NOT NULL,
                  impact_level TEXT NOT NULL,
                  first_seen_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS deliveries (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  subscriber_id INTEGER NOT NULL,
                  source_id TEXT NOT NULL,
                  channel TEXT NOT NULL,
                  destination TEXT,
                  status TEXT NOT NULL,
                  detail TEXT,
                  created_at TEXT NOT NULL,
                  UNIQUE(subscriber_id, source_id, channel)
                );
                """
            )

    def add_subscriber(self, sub: SubscriberCreate) -> dict[str, Any]:
        if not sub.email and not sub.webhook_url:
            raise HTTPException(status_code=400, detail="email or webhook_url required")
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO subscribers(email,webhook_url,agencies,topics,industries,created_at) VALUES(?,?,?,?,?,?)",
                (
                    sub.email,
                    str(sub.webhook_url) if sub.webhook_url else None,
                    json.dumps([a.upper() for a in sub.agencies]),
                    json.dumps(sub.topics),
                    json.dumps(sub.industries),
                    utcnow(),
                ),
            )
            return dict(conn.execute("SELECT * FROM subscribers WHERE id=?", (cur.lastrowid,)).fetchone())

    def subscribers(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM subscribers WHERE active=1 ORDER BY id DESC")]
        for row in rows:
            for key in ["agencies", "topics", "industries"]:
                row[key] = json.loads(row[key] or "[]")
        return rows

    def upsert_alert(self, doc: RegulatoryDocument, summary: dict[str, Any]) -> bool:
        with self.connect() as conn:
            before = conn.total_changes
            conn.execute(
                """
                INSERT OR IGNORE INTO alerts(source_id,agency,title,document_type,publication_date,effective_date,url,topics,
                  affected_industries,summary,action_required,impact_score,impact_level,first_seen_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    doc.source_id, doc.agency, doc.title, doc.document_type, doc.publication_date, doc.effective_date, doc.url,
                    json.dumps(summary["topics"]), json.dumps(summary["affected_industries"]), summary["summary"],
                    summary["action_required"], int(summary["impact_score"]), summary["impact_level"], utcnow()
                ),
            )
            return conn.total_changes > before

    def alerts(self, q: str | None = None, agency: str | None = None, topic: str | None = None, industry: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        where, params = [], []
        if q:
            where.append("lower(title || ' ' || summary || ' ' || agency || ' ' || topics || ' ' || affected_industries) LIKE ?")
            params.append(f"%{q.lower()}%")
        if agency:
            where.append("agency = ?")
            params.append(agency.upper())
        if topic:
            where.append("lower(topics) LIKE ?")
            params.append(f"%{topic.lower()}%")
        if industry:
            where.append("lower(affected_industries) LIKE ?")
            params.append(f"%{industry.lower()}%")
        sql = "SELECT * FROM alerts" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY first_seen_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, params)]
        for row in rows:
            row["topics"] = json.loads(row["topics"] or "[]")
            row["affected_industries"] = json.loads(row["affected_industries"] or "[]")
        return rows

    def add_delivery(self, subscriber_id: int, source_id: str, channel: str, destination: str | None, status: str, detail: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO deliveries(subscriber_id,source_id,channel,destination,status,detail,created_at) VALUES(?,?,?,?,?,?,?)",
                (subscriber_id, source_id, channel, destination, status, detail, utcnow()),
            )

    def deliveries(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM deliveries ORDER BY id DESC LIMIT ?", (limit,))]

    def trend_counts(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                """
                SELECT agency, impact_level, substr(COALESCE(NULLIF(publication_date,''), first_seen_at),1,7) AS month, COUNT(*) AS alerts
                FROM alerts GROUP BY agency, impact_level, month ORDER BY alerts DESC, month DESC LIMIT 30
                """
            )]


class FederalRegisterSource:
    def __init__(self, agency: str, slug: str, api_url: str | None = None):
        self.agency = agency
        self.slug = slug
        self.api_url = api_url or os.getenv("FEDERAL_REGISTER_API", FEDERAL_REGISTER_API)

    def fetch(self, limit: int = 10) -> list[RegulatoryDocument]:
        params = {
            "conditions[agencies][]": self.slug,
            "per_page": str(limit),
            "order": "newest",
            "fields[]": ["document_number", "title", "abstract", "type", "publication_date", "effective_on", "html_url"],
        }
        r = requests.get(self.api_url, params=params, headers={"User-Agent": "AgenticWorkRegMonitor/1.0", "Accept": "application/json"}, timeout=25)
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("results", payload if isinstance(payload, list) else [])
        docs = []
        for row in rows:
            source_id = f"{self.agency}:{row.get('document_number') or row.get('id') or row.get('title')}"
            docs.append(RegulatoryDocument(
                source_id=source_id,
                agency=self.agency,
                title=str(row.get("title") or "Untitled regulatory document"),
                body=str(row.get("abstract") or row.get("body") or ""),
                document_type=str(row.get("type") or "notice"),
                publication_date=str(row.get("publication_date") or ""),
                effective_date=str(row.get("effective_on") or ""),
                url=str(row.get("html_url") or row.get("url") or ""),
            ))
        return docs


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_sources() -> list[FederalRegisterSource]:
    return [FederalRegisterSource(agency, slug) for agency, slug in AGENCY_MAP.items()]


def summarize_document(doc: RegulatoryDocument) -> dict[str, Any]:
    text = f"{doc.title}. {doc.body}".lower()
    topic_keywords = {
        "AI": ["artificial intelligence", "machine learning", "algorithm", "automated", "model"],
        "crypto": ["crypto", "digital asset", "blockchain", "token", "stablecoin"],
        "privacy": ["privacy", "data", "cyber", "security"],
        "healthcare": ["drug", "medical", "clinical", "device", "patient"],
        "telecom": ["spectrum", "broadband", "wireless", "communications"],
        "markets": ["securities", "swap", "futures", "exchange", "clearing"],
    }
    topics = [name for name, kws in topic_keywords.items() if any(k in text for k in kws)] or [doc.document_type]
    industry_map = {
        "fintech": ["crypto", "securities", "futures", "swap", "exchange", "bank"],
        "healthcare": ["drug", "medical", "clinical", "device", "patient", "food"],
        "telecom": ["fcc", "spectrum", "broadband", "wireless", "communications"],
        "AI/software": ["artificial intelligence", "algorithm", "software", "automated", "cyber"],
        "consumer products": ["label", "safety", "consumer", "food"],
    }
    industries = [name for name, kws in industry_map.items() if any(k in text for k in kws)] or ["general counsel"]
    major_terms = ["final rule", "proposed rule", "enforcement", "penalty", "compliance", "effective", "ban", "mandatory"]
    impact_score = min(100, 25 + 15 * sum(1 for term in major_terms if term in text) + (10 if doc.effective_date else 0))
    impact_level = "major rule change" if impact_score >= 65 else "moderate update" if impact_score >= 40 else "minor update"
    compact = " ".join(f"{doc.title}. {doc.body}".split()[:42])
    if len(f"{doc.title}. {doc.body}".split()) > 42:
        compact += "..."
    action_required = "Review applicability, assign owner, and check whether comment/effective dates create a compliance deadline."
    if doc.effective_date:
        action_required = f"Assess obligations before effective date {doc.effective_date}; assign legal/compliance owner."
    return {
        "summary": compact,
        "affected_industries": industries,
        "topics": topics,
        "effective_date": doc.effective_date,
        "action_required": action_required,
        "impact_score": impact_score,
        "impact_level": impact_level,
    }


def subscriber_matches(sub: dict[str, Any], alert: dict[str, Any]) -> bool:
    agencies = [a.upper() for a in sub.get("agencies", [])]
    topics = [t.lower() for t in sub.get("topics", [])]
    industries = [i.lower() for i in sub.get("industries", [])]
    if agencies and alert["agency"].upper() not in agencies:
        return False
    if topics and not any(t in [x.lower() for x in alert["topics"]] or t in alert["summary"].lower() for t in topics):
        return False
    if industries and not any(i in [x.lower() for x in alert["affected_industries"]] or i in alert["summary"].lower() for i in industries):
        return False
    return True


def send_email(to_addr: str, subject: str, body: str) -> tuple[str, str]:
    host = os.getenv("SMTP_HOST")
    if not host:
        return "stored", "SMTP_HOST not set; alert stored in development outbox"
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", "regulatory-alerts@agentic-work.local")
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=20) as smtp:
        if os.getenv("SMTP_USER"):
            smtp.starttls()
            smtp.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
    return "sent", f"sent via {host}"


def send_webhook(url: str, payload: dict[str, Any]) -> tuple[str, str]:
    try:
        r = requests.post(url, json=payload, timeout=15, headers={"User-Agent": "AgenticWorkRegMonitor/1.0"})
        return ("sent", f"HTTP {r.status_code}") if 200 <= r.status_code < 300 else ("failed", f"HTTP {r.status_code}: {r.text[:160]}")
    except Exception as exc:
        return "failed", str(exc)


def x402_requirements() -> dict[str, Any]:
    return {
        "network": "base",
        "asset": "USDC",
        "amount": "99.00",
        "pay_to": os.getenv("X402_PAY_TO", DEFAULT_WALLET),
        "product": "Regulatory Change Monitor Starter monthly access",
        "header": "X-PAYMENT",
    }


def require_paid(x_payment: str | None = Header(default=None), x_plan: str | None = Header(default=None)) -> None:
    if x_payment or (x_plan and x_plan.lower() in {"pro", "enterprise"}):
        return
    raise HTTPException(status_code=402, detail={"error": "payment_required", "payment": x402_requirements()})


store = Store(os.getenv("REG_MONITOR_DB", "/tmp/regulatory_change_monitor.db"))
app = FastAPI(title=APP_NAME, version="1.0.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": APP_NAME, "sources": list(AGENCY_MAP), "poll_interval_seconds": int(os.getenv("POLL_INTERVAL_SECONDS", "900"))}


@app.get("/api/payments/x402/requirements")
def payment_requirements() -> dict[str, Any]:
    return x402_requirements()


@app.post("/api/subscribers")
def create_subscriber(sub: SubscriberCreate) -> dict[str, Any]:
    return store.add_subscriber(sub)


@app.get("/api/subscribers")
def list_subscribers() -> list[dict[str, Any]]:
    return store.subscribers()


@app.post("/api/poll")
def poll(limit_per_source: int = Query(default=5, ge=1, le=25)) -> dict[str, Any]:
    new_alerts = 0
    seen = 0
    errors: list[dict[str, str]] = []
    for source in get_sources():
        try:
            docs = source.fetch(limit=limit_per_source)
        except Exception as exc:
            errors.append({"agency": source.agency, "error": str(exc)})
            continue
        for doc in docs:
            seen += 1
            summary = summarize_document(doc)
            is_new = store.upsert_alert(doc, summary)
            if not is_new:
                continue
            new_alerts += 1
            alert = store.alerts(q=doc.source_id, limit=1)[0] if store.alerts(q=doc.source_id, limit=1) else {
                "source_id": doc.source_id, "agency": doc.agency, "title": doc.title, "summary": summary["summary"],
                "topics": summary["topics"], "affected_industries": summary["affected_industries"], "url": doc.url,
            }
            for sub in store.subscribers():
                if not subscriber_matches(sub, alert):
                    continue
                body = f"{alert['agency']}: {alert['title']}\n\n{alert['summary']}\n\nAction required: {summary['action_required']}\nImpact: {summary['impact_level']} ({summary['impact_score']}/100)\n{doc.url}"
                if sub.get("email"):
                    status, detail = send_email(sub["email"], f"Regulatory alert: {doc.agency} {doc.title[:70]}", body)
                    store.add_delivery(sub["id"], doc.source_id, "email", sub["email"], status, detail)
                if sub.get("webhook_url"):
                    status, detail = send_webhook(sub["webhook_url"], {"subscriber_id": sub["id"], "alert": alert})
                    store.add_delivery(sub["id"], doc.source_id, "webhook", sub["webhook_url"], status, detail)
    return {"sources": list(AGENCY_MAP), "documents_seen": seen, "new_alerts": new_alerts, "errors": errors, "summaries_generated_immediately": True}


@app.get("/api/alerts")
def alerts(q: str | None = None, agency: str | None = None, topic: str | None = None, industry: str | None = None, limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return store.alerts(q=q, agency=agency, topic=topic, industry=industry, limit=limit)


@app.get("/api/deliveries")
def deliveries() -> list[dict[str, Any]]:
    return store.deliveries()


@app.get("/api/trends")
def trends() -> list[dict[str, Any]]:
    return store.trend_counts()


@app.get("/api/scheduler/status")
def scheduler_status() -> dict[str, Any]:
    interval = int(os.getenv("POLL_INTERVAL_SECONDS", "900"))
    return {"poll_interval_seconds": interval, "meets_five_minute_sla": interval <= 300, "cron_command": "POST /api/poll"}


@app.get("/api/export", dependencies=[Depends(require_paid)])
def export_archive() -> dict[str, Any]:
    return {"alerts": store.alerts(limit=200), "trends": store.trend_counts(), "exported_at": utcnow()}


@app.get("/", response_class=HTMLResponse)
def dashboard(q: str | None = None, agency: str | None = None, topic: str | None = None, industry: str | None = None) -> str:
    rows = store.alerts(q=q, agency=agency, topic=topic, industry=industry, limit=30)
    subs = store.subscribers()
    trend_rows = store.trend_counts()[:12]
    alert_rows = "".join(
        f"<tr><td>{html.escape(r['publication_date'] or r['first_seen_at'][:10])}</td><td>{html.escape(r['agency'])}</td>"
        f"<td><strong>{html.escape(r['title'])}</strong><br><small>{html.escape(r['summary'])}</small></td>"
        f"<td>{html.escape(r['impact_level'])}<br><small>{r['impact_score']}/100</small></td>"
        f"<td>{html.escape(', '.join(r['affected_industries']))}</td></tr>"
        for r in rows
    ) or "<tr><td colspan='5'>No alerts yet. Add subscriber and POST /api/poll.</td></tr>"
    trend_items = "".join(f"<li>{html.escape(t['agency'])} / {html.escape(t['impact_level'])} / {html.escape(t['month'])}: {t['alerts']}</li>" for t in trend_rows) or "<li>No trend data yet</li>"
    sub_items = "".join(f"<li>#{s['id']} {html.escape(str(s.get('email') or s.get('webhook_url')))} — {html.escape(','.join(s['agencies']) or 'all agencies')}</li>" for s in subs) or "<li>No subscribers yet</li>"
    return f"""
    <!doctype html><html><head><title>{APP_NAME}</title>
    <style>body{{font-family:Inter,system-ui,sans-serif;margin:32px;background:#10131f;color:#eef}} .card{{background:#181d2e;padding:18px;border-radius:14px;margin:16px 0}} input,select,button{{padding:9px;border-radius:8px;border:1px solid #334;background:#0f1322;color:#eef}} table{{width:100%;border-collapse:collapse}} td,th{{border-bottom:1px solid #334;padding:10px;text-align:left;vertical-align:top}} small{{color:#aeb6d8}}</style></head>
    <body><h1>Regulatory Change Monitor</h1><p>SEC, FDA, FCC, and CFTC monitoring with summaries, impact scores, alerts, and x402 export.</p>
    <div class='card'><h2>Filters</h2><form><input name='q' value='{html.escape(q or '')}' placeholder='search'><input name='agency' value='{html.escape(agency or '')}' placeholder='SEC/FDA/FCC/CFTC'><input name='topic' value='{html.escape(topic or '')}' placeholder='topic'><input name='industry' value='{html.escape(industry or '')}' placeholder='industry'><button>Filter</button></form></div>
    <div class='card'><h2>Subscribers</h2><ul>{sub_items}</ul></div>
    <div class='card'><h2>Recent alerts</h2><table><tr><th>Date</th><th>Agency</th><th>Document</th><th>Impact</th><th>Industries</th></tr>{alert_rows}</table></div>
    <div class='card'><h2>Trend counts</h2><ul>{trend_items}</ul></div>
    <div class='card'><h2>Payment</h2><p>Starter $99/mo, Pro $299/mo, Enterprise $999/mo. Export endpoint requires <code>X-PAYMENT</code>.</p></div>
    </body></html>
    """
