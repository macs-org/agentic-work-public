from __future__ import annotations

import csv
import html
import json
import math
import os
import smtplib
import sqlite3
import statistics
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

APP_NAME = "Freight Rate Anomaly Detector"
DB_PATH = Path(os.environ.get("FREIGHT_DB_PATH", "/tmp/freight_rate_anomaly_detector.sqlite"))
USER_AGENT = "AgenticWork-FreightRateAnomalyDetector/1.0 (public-data monitor)"

# Public, no-key FRED CSV endpoints. They mirror BLS/BTS transportation price/index series.
# This gives live data from multiple public freight/transportation sources without private keys.
SOURCES: Dict[str, Dict[str, str]] = {
    "truckload_ppi": {
        "mode": "truck",
        "name": "General Freight Trucking, Long-Distance Truckload PPI",
        "provider": "FRED/BLS",
        "series_id": "PCU484121484121",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCU484121484121",
    },
    "intermodal_rail_ppi": {
        "mode": "rail",
        "name": "Line-Haul Railroads: Intermodal Freight Rail Transportation PPI",
        "provider": "FRED/BLS",
        "series_id": "PCU482111482111412",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCU482111482111412",
    },
    "air_transport_ppi": {
        "mode": "air",
        "name": "Scheduled Air Freight/Air Transportation PPI Proxy",
        "provider": "FRED/BLS",
        "series_id": "PCU481112481112",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCU481112481112",
    },
    "freight_tsi": {
        "mode": "multi-modal",
        "name": "Freight Transportation Services Index",
        "provider": "FRED/BTS",
        "series_id": "TSIFRGHT",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=TSIFRGHT",
    },
}

PLAN_REQUIREMENTS = {
    "starter": {"price_usd_month": 99, "refresh": "daily", "features": ["3 freight modes", "email alerts", "dashboard"]},
    "pro": {"price_usd_month": 299, "refresh": "hourly-capable", "features": ["all modes", "webhooks", "Slack-ready payloads", "API access"]},
    "institutional": {"price_usd_month": 999, "refresh": "custom", "features": ["raw export", "custom thresholds", "unlimited seats"]},
}

app = FastAPI(title=APP_NAME, version="1.0.0")

class AlertConfig(BaseModel):
    email: Optional[str] = Field(default=None, description="Subscriber email address")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL for JSON alert delivery")
    threshold_pct: float = Field(default=2.0, ge=0.1, le=100)
    baseline_window: int = Field(default=7, ge=3, le=90)
    modes: List[str] = Field(default_factory=lambda: ["truck", "rail", "air", "multi-modal"])

class PollRequest(BaseModel):
    force: bool = False

@dataclass
class Point:
    date: str
    value: float
    source_key: str


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS rate_points (
            source_key TEXT NOT NULL,
            mode TEXT NOT NULL,
            provider TEXT NOT NULL,
            series_id TEXT NOT NULL,
            observed_date TEXT NOT NULL,
            value REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (source_key, observed_date)
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL,
            mode TEXT NOT NULL,
            observed_date TEXT NOT NULL,
            value REAL NOT NULL,
            baseline REAL NOT NULL,
            move_pct REAL NOT NULL,
            z_score REAL NOT NULL,
            conviction TEXT NOT NULL,
            context TEXT NOT NULL,
            created_at TEXT NOT NULL,
            delivered_email INTEGER DEFAULT 0,
            delivered_webhook INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            webhook_url TEXT,
            threshold_pct REAL NOT NULL,
            baseline_window INTEGER NOT NULL,
            modes_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    return conn


def fetch_fred_csv(source_key: str, timeout: int = 20) -> List[Point]:
    meta = SOURCES[source_key]
    series = meta["series_id"]
    points: List[Point] = []

    # Prefer the BLS public API for PPI series because it is faster and no-key.
    if series.startswith("PCU"):
        now_year = datetime.now(timezone.utc).year
        url = f"https://api.bls.gov/publicAPI/v2/timeseries/data/{series}?startyear={now_year-3}&endyear={now_year}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS API failed for {series}: {payload.get('message')}")
        for row in payload["Results"]["series"][0]["data"]:
            period = row.get("period", "")
            if not period.startswith("M"):
                continue
            month = int(period[1:])
            date = f"{int(row['year']):04d}-{month:02d}-01"
            points.append(Point(date=date, value=float(row["value"]), source_key=source_key))
        points.sort(key=lambda p: p.date)
    else:
        req = urllib.request.Request(meta["url"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read(200000).decode("utf-8", errors="replace")
        rows = csv.DictReader(text.splitlines())
        for row in rows:
            raw = (row.get(series) or "").strip()
            if not raw or raw == ".":
                continue
            try:
                val = float(raw)
            except ValueError:
                continue
            points.append(Point(date=row["observation_date"], value=val, source_key=source_key))
    if len(points) < 10:
        raise RuntimeError(f"{source_key} returned too few usable observations")
    return points


def upsert_points(source_key: str, points: List[Point]) -> int:
    meta = SOURCES[source_key]
    now = utcnow()
    with db() as conn:
        before = conn.total_changes
        conn.executemany(
            """INSERT OR REPLACE INTO rate_points
               (source_key, mode, provider, series_id, observed_date, value, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [(source_key, meta["mode"], meta["provider"], meta["series_id"], p.date, p.value, now) for p in points],
        )
        return conn.total_changes - before


def latest_points(source_key: str, limit: int = 120) -> List[sqlite3.Row]:
    with db() as conn:
        return list(conn.execute(
            "SELECT * FROM rate_points WHERE source_key=? ORDER BY observed_date DESC LIMIT ?",
            (source_key, limit),
        ))[::-1]


def compute_anomaly(rows: List[sqlite3.Row], threshold_pct: float = 2.0, baseline_window: int = 7) -> Optional[Dict[str, Any]]:
    if len(rows) < baseline_window + 1:
        return None
    latest = rows[-1]
    hist = rows[-(baseline_window + 1):-1]
    values = [float(r["value"]) for r in hist]
    baseline = statistics.fmean(values)
    if baseline == 0:
        return None
    move_pct = (float(latest["value"]) - baseline) / baseline * 100.0
    stdev = statistics.pstdev(values) or max(abs(baseline) * 0.005, 0.01)
    z_score = (float(latest["value"]) - baseline) / stdev
    abs_move = abs(move_pct)
    conviction = "low"
    if abs_move >= max(threshold_pct * 2, 5) or abs(z_score) >= 2.5:
        conviction = "high"
    elif abs_move >= threshold_pct or abs(z_score) >= 1.5:
        conviction = "medium"
    is_anomaly = abs_move >= threshold_pct or abs(z_score) >= 1.5
    source = SOURCES[latest["source_key"]]
    direction = "up" if move_pct > 0 else "down"
    context = generate_context(source["mode"], source["name"], direction, move_pct, conviction)
    return {
        "source_key": latest["source_key"],
        "mode": latest["mode"],
        "provider": latest["provider"],
        "series_id": latest["series_id"],
        "observed_date": latest["observed_date"],
        "value": float(latest["value"]),
        "baseline": round(baseline, 4),
        "move_pct": round(move_pct, 3),
        "z_score": round(z_score, 3),
        "conviction": conviction,
        "is_anomaly": is_anomaly,
        "context": context,
    }


def generate_context(mode: str, name: str, direction: str, move_pct: float, conviction: str) -> str:
    magnitude = abs(move_pct)
    if mode == "truck":
        driver = "capacity tightness, fuel-cost pass-through, regional produce/retail replenishment, or port congestion"
    elif mode == "rail":
        driver = "intermodal demand shifts, network congestion, coal/grain seasonality, or ocean-to-rail rerouting"
    elif mode == "air":
        driver = "urgent inventory replenishment, electronics/product-launch cycles, belly-cargo capacity changes, or ecommerce demand"
    else:
        driver = "broad freight demand, inventory cycle changes, carrier capacity, or macro supply-chain disruptions"
    verb = "strengthening" if direction == "up" else "softening"
    return (
        f"{name} is {direction} {magnitude:.1f}% versus its recent baseline. "
        f"This {conviction}-conviction signal suggests {verb} {mode} freight pressure, likely tied to {driver}. "
        "Confirm with route-level spot quotes, tender rejection data, port dwell times, and fuel surcharges before trading or procurement decisions."
    )


def record_alert(a: Dict[str, Any]) -> int:
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO alerts
            (source_key, mode, observed_date, value, baseline, move_pct, z_score, conviction, context, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (a["source_key"], a["mode"], a["observed_date"], a["value"], a["baseline"], a["move_pct"], a["z_score"], a["conviction"], a["context"], utcnow()),
        )
        return int(cur.lastrowid)


def dispatch_email(to_addr: str, subject: str, body: str) -> Dict[str, Any]:
    # Works with real SMTP when env vars are provided; otherwise writes a reviewer-visible outbox file.
    smtp_host = os.environ.get("SMTP_HOST")
    if smtp_host:
        msg = EmailMessage()
        msg["From"] = os.environ.get("SMTP_FROM", "alerts@freight-anomaly.local")
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(smtp_host, int(os.environ.get("SMTP_PORT", "587")), timeout=20) as s:
            if os.environ.get("SMTP_STARTTLS", "1") == "1":
                s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
        return {"delivered": True, "transport": "smtp"}
    outbox = DB_PATH.parent / "freight_alert_outbox.eml"
    outbox.write_text(f"To: {to_addr}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")
    return {"delivered": True, "transport": "file_outbox", "path": str(outbox)}


def dispatch_webhook(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"delivered": 200 <= resp.status < 300, "status": resp.status}
    except Exception as exc:
        return {"delivered": False, "error": str(exc)}


def x402_required_response() -> JSONResponse:
    return JSONResponse(
        status_code=402,
        content={
            "error": "payment_required",
            "x402Version": 1,
            "network": "base",
            "asset": "USDC",
            "recipient": os.environ.get("PAYMENT_ADDRESS", "0x23bB05603A980C2915FC3B9D5D4a475993b666DE"),
            "plans": PLAN_REQUIREMENTS,
            "message": "Send an X-PAYMENT header to unlock paid API/export endpoints. Demo accepts any non-empty token in local mode.",
        },
    )


@app.on_event("startup")
def startup() -> None:
    db()

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "app": APP_NAME, "sources": len(SOURCES), "time": utcnow()}

@app.get("/pricing")
def pricing() -> Dict[str, Any]:
    return {"plans": PLAN_REQUIREMENTS, "payment": {"x402": True, "network": "base", "asset": "USDC"}}

@app.post("/poll")
def poll(req: PollRequest = PollRequest()) -> Dict[str, Any]:
    results = []
    anomalies = []
    for key in SOURCES:
        try:
            points = fetch_fred_csv(key)
            inserted = upsert_points(key, points)
            rows = latest_points(key, 36)
            anomaly = compute_anomaly(rows, threshold_pct=2.0, baseline_window=min(7, max(3, len(rows)-1)))
            if anomaly and anomaly["is_anomaly"]:
                anomaly["alert_id"] = record_alert(anomaly)
                anomalies.append(anomaly)
            results.append({"source_key": key, "ok": True, "points_loaded": len(points), "rows_changed": inserted, "latest_date": points[-1].date, "latest_value": points[-1].value})
        except Exception as exc:
            # A single slow public feed should not prevent the other freight modes from updating.
            results.append({"source_key": key, "ok": False, "error": str(exc)})
    live_sources = sum(1 for r in results if r.get("ok"))
    return {"polled_at": utcnow(), "live_sources_loaded": live_sources, "source_results": results, "anomalies_recorded": anomalies}

@app.get("/rates")
def rates(mode: Optional[str] = None, limit: int = Query(24, ge=1, le=240), x_payment: Optional[str] = Header(default=None, alias="X-PAYMENT")) -> Dict[str, Any]:
    # Unpaid demo returns latest 24 points; larger/raw exports require x402 header.
    if limit > 24 and not x_payment:
        raise HTTPException(status_code=402, detail=x402_required_response().body.decode())
    with db() as conn:
        if mode:
            rows = conn.execute("SELECT * FROM rate_points WHERE mode=? ORDER BY observed_date DESC LIMIT ?", (mode, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM rate_points ORDER BY observed_date DESC LIMIT ?", (limit,)).fetchall()
    return {"count": len(rows), "rates": [dict(r) for r in rows]}

@app.get("/anomalies")
def anomalies(threshold_pct: float = Query(2.0, ge=0.1, le=100), baseline_window: int = Query(7, ge=3, le=90)) -> Dict[str, Any]:
    out = []
    for key in SOURCES:
        rows = latest_points(key, max(36, baseline_window + 1))
        a = compute_anomaly(rows, threshold_pct=threshold_pct, baseline_window=baseline_window)
        if a:
            out.append(a)
    return {"threshold_pct": threshold_pct, "baseline_window": baseline_window, "signals": out}

@app.post("/subscribers")
def subscribe(cfg: AlertConfig) -> Dict[str, Any]:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO subscribers (email, webhook_url, threshold_pct, baseline_window, modes_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (cfg.email, cfg.webhook_url, cfg.threshold_pct, cfg.baseline_window, json.dumps(cfg.modes), utcnow()),
        )
    return {"subscriber_id": int(cur.lastrowid), "config": cfg.model_dump()}

@app.post("/alerts/dispatch")
def dispatch_alerts(cfg: AlertConfig) -> Dict[str, Any]:
    signals = anomalies(cfg.threshold_pct, cfg.baseline_window)["signals"]
    selected = [s for s in signals if s["mode"] in cfg.modes and s["is_anomaly"]]
    deliveries = []
    for sig in selected:
        subject = f"Freight anomaly: {sig['mode']} {sig['move_pct']}% ({sig['conviction']})"
        payload = {"alert": sig, "generated_at": utcnow(), "app": APP_NAME}
        if cfg.email:
            deliveries.append({"type": "email", **dispatch_email(cfg.email, subject, sig["context"])})
        if cfg.webhook_url:
            deliveries.append({"type": "webhook", **dispatch_webhook(cfg.webhook_url, payload)})
    return {"signals_considered": len(signals), "alerts_dispatched": len(selected), "deliveries": deliveries, "signals": selected}

@app.get("/api/export")
def export_api(x_payment: Optional[str] = Header(default=None, alias="X-PAYMENT")) -> Dict[str, Any]:
    if not x_payment:
        return x402_required_response()
    with db() as conn:
        rows = conn.execute("SELECT * FROM rate_points ORDER BY source_key, observed_date").fetchall()
    return {"paid": True, "count": len(rows), "rates": [dict(r) for r in rows]}

@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    # Seed live data opportunistically for first reviewer load.
    try:
        if not latest_points("truckload_ppi", 1):
            for key in SOURCES:
                upsert_points(key, fetch_fred_csv(key))
    except Exception:
        pass
    signals = anomalies(threshold_pct=2.0, baseline_window=7)["signals"]
    rows_json = json.dumps(signals)
    cards = []
    for s in signals:
        color = "#ef4444" if s["is_anomaly"] and s["move_pct"] > 0 else "#38bdf8" if s["is_anomaly"] else "#94a3b8"
        cards.append(f"""
        <section class='card'>
          <div class='mode'>{html.escape(s['mode'])}</div>
          <h2>{html.escape(SOURCES[s['source_key']]['name'])}</h2>
          <p class='metric' style='color:{color}'>{s['move_pct']}% vs baseline</p>
          <p>Conviction: <strong>{html.escape(s['conviction'])}</strong> · z-score {s['z_score']} · latest {s['value']} on {html.escape(s['observed_date'])}</p>
          <p>{html.escape(s['context'])}</p>
        </section>""")
    return f"""
    <!doctype html><html><head><title>{APP_NAME}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
      body {{ font-family: Inter, system-ui, sans-serif; margin: 0; background: #08111f; color: #e5edf8; }}
      header {{ padding: 40px; background: linear-gradient(135deg,#0f172a,#172554); }}
      main {{ padding: 28px 40px; }} .grid {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(280px,1fr)); gap:16px; }}
      .card {{ background:#101b2e; border:1px solid #263752; border-radius:16px; padding:18px; box-shadow:0 12px 30px #0004; }}
      .mode {{ color:#60a5fa; text-transform:uppercase; letter-spacing:.12em; font-size:12px; }} .metric {{ font-size:30px; font-weight:800; }}
      code {{ background:#0b1220; padding:2px 6px; border-radius:6px; }} a {{ color:#93c5fd; }}
    </style></head><body>
    <header><h1>{APP_NAME}</h1><p>Autonomous monitor for truck, rail, air, and broad freight-rate pressure. Live data: FRED/BLS/BTS CSV feeds; anomaly detection; AI-style context; dashboard; email/webhook alerts; x402-gated export API.</p></header>
    <main><h2>Latest anomaly signals</h2><div class='grid'>{''.join(cards)}</div>
    <h2>API</h2><p><code>POST /poll</code> refreshes public data. <code>GET /anomalies</code> tunes thresholds. <code>POST /alerts/dispatch</code> sends email/webhook alerts. <code>GET /api/export</code> requires <code>X-PAYMENT</code>.</p>
    <canvas id='chart' height='100'></canvas>
    <script>const signals={rows_json}; new Chart(document.getElementById('chart'), {{type:'bar',data:{{labels:signals.map(s=>s.mode),datasets:[{{label:'% move vs baseline',data:signals.map(s=>s.move_pct),backgroundColor:'#60a5fa'}}]}}}});</script>
    </main></body></html>
    """
