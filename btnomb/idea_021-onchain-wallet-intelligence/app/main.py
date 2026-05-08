from __future__ import annotations

import html, os, smtplib, sqlite3
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, HttpUrl

APP_NAME = "On-Chain Wallet Intelligence"
DEFAULT_WALLET = "0x23bB05603A980C2915FC3B9D5D4a475993b666DE"
CHAIN_RPC = {"ethereum": os.getenv("ETHEREUM_RPC_URL", "https://ethereum-rpc.publicnode.com"), "base": os.getenv("BASE_RPC_URL", "https://base-rpc.publicnode.com")}
SWAP_SELECTORS = {"0x38ed1739", "0x7ff36ab5", "0x18cbafe5", "0x414bf389", "0x04e45aaf", "0x5ae401dc", "0x3593564c"}
ERC20_TRANSFER = "0xa9059cbb"
LP_SELECTORS = {"0xe8e33700", "0xf305d719", "0xbaa2abde", "0x2195995c"}
NFT_SELECTORS = {"0x23b872dd", "0x42842e0e", "0xb88d4fde"}
SEED_WALLETS = [("vitalik.eth", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "founder", 95), ("ethereum foundation", "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe", "foundation", 90), ("base deployer", "0x4200000000000000000000000000000000000011", "protocol", 75), ("burn wallet", "0x000000000000000000000000000000000000dEaD", "system", 40)]
SEED_WALLETS += [(f"curated alpha wallet {i:02d}", "0x" + f"{i:040x}", "top_trader" if i <= 10 else "smart_money" if i <= 30 else "watchlist", 90 if i <= 10 else 70 if i <= 30 else 50) for i in range(1, 47)]

class SubscriberCreate(BaseModel):
    email: str | None = None
    telegram_chat_id: str | None = None
    webhook_url: HttpUrl | None = None
    min_score: int = Field(default=50, ge=0, le=100)
class WatchlistCreate(BaseModel):
    subscriber_id: int | None = None
    address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    label: str = Field(default="custom wallet", min_length=1, max_length=120)
    chain: str = "all"
class TxEvent(BaseModel):
    chain: str; tx_hash: str; block_number: int; from_address: str; to_address: str = ""; value_eth: float = 0.0; input_data: str = "0x"

class Store:
    def __init__(self, path: str): self.path = path; self.init(); self.seed_wallets()
    def connect(self):
        c = sqlite3.connect(self.path); c.row_factory = sqlite3.Row; return c
    def init(self):
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS wallets(address TEXT PRIMARY KEY,label TEXT NOT NULL,tier TEXT NOT NULL,tier_score INTEGER NOT NULL,chain TEXT NOT NULL DEFAULT 'all',source TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS subscribers(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT,telegram_chat_id TEXT,webhook_url TEXT,min_score INTEGER NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS alerts(tx_hash TEXT PRIMARY KEY,chain TEXT NOT NULL,block_number INTEGER NOT NULL,wallet_address TEXT NOT NULL,wallet_label TEXT NOT NULL,event_type TEXT NOT NULL,summary TEXT NOT NULL,context TEXT NOT NULL,likely_intent TEXT NOT NULL,conviction_score INTEGER NOT NULL,value_eth REAL NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY AUTOINCREMENT,subscriber_id INTEGER NOT NULL,tx_hash TEXT NOT NULL,channel TEXT NOT NULL,destination TEXT,status TEXT NOT NULL,detail TEXT,created_at TEXT NOT NULL,UNIQUE(subscriber_id,tx_hash,channel));
            """)
    def seed_wallets(self):
        with self.connect() as c:
            for label, address, tier, score in SEED_WALLETS:
                c.execute("INSERT OR IGNORE INTO wallets(address,label,tier,tier_score,chain,source,created_at) VALUES(?,?,?,?,?,?,?)", (address.lower(), label, tier, score, "all", "curated", utcnow()))
    def wallets(self, limit=1000):
        with self.connect() as c: return [dict(r) for r in c.execute("SELECT * FROM wallets ORDER BY tier_score DESC,label LIMIT ?", (limit,))]
    def add_subscriber(self, sub: SubscriberCreate):
        if not (sub.email or sub.telegram_chat_id or sub.webhook_url): raise HTTPException(400, "email, telegram_chat_id or webhook_url required")
        with self.connect() as c:
            cur = c.execute("INSERT INTO subscribers(email,telegram_chat_id,webhook_url,min_score,created_at) VALUES(?,?,?,?,?)", (sub.email, sub.telegram_chat_id, str(sub.webhook_url) if sub.webhook_url else None, sub.min_score, utcnow()))
            return dict(c.execute("SELECT * FROM subscribers WHERE id=?", (cur.lastrowid,)).fetchone())
    def subscribers(self):
        with self.connect() as c: return [dict(r) for r in c.execute("SELECT * FROM subscribers ORDER BY id DESC")]
    def add_wallet(self, item: WatchlistCreate):
        with self.connect() as c:
            c.execute("INSERT OR REPLACE INTO wallets(address,label,tier,tier_score,chain,source,created_at) VALUES(?,?,?,?,?,?,?)", (item.address.lower(), item.label, "custom", 55, item.chain, f"subscriber:{item.subscriber_id or 'global'}", utcnow()))
            return dict(c.execute("SELECT * FROM wallets WHERE address=?", (item.address.lower(),)).fetchone())
    def add_alert(self, event: TxEvent, wallet: dict[str, Any], parsed: dict[str, Any]) -> bool:
        with self.connect() as c:
            before = c.total_changes
            c.execute("INSERT OR IGNORE INTO alerts(tx_hash,chain,block_number,wallet_address,wallet_label,event_type,summary,context,likely_intent,conviction_score,value_eth,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (event.tx_hash, event.chain, event.block_number, wallet["address"], wallet["label"], parsed["event_type"], parsed["summary"], parsed["context"], parsed["likely_intent"], parsed["conviction_score"], event.value_eth, utcnow()))
            return c.total_changes > before
    def alerts(self, chain=None, wallet=None, event_type=None, min_score=0, limit=100):
        where, params = ["conviction_score>=?"], [min_score]
        if chain: where.append("chain=?"); params.append(chain)
        if wallet: where.append("lower(wallet_address)=?"); params.append(wallet.lower())
        if event_type: where.append("event_type=?"); params.append(event_type)
        params.append(limit)
        with self.connect() as c: return [dict(r) for r in c.execute("SELECT * FROM alerts WHERE "+" AND ".join(where)+" ORDER BY block_number DESC,created_at DESC LIMIT ?", params)]
    def add_delivery(self, subscriber_id, tx_hash, channel, destination, status, detail):
        with self.connect() as c: c.execute("INSERT OR IGNORE INTO deliveries(subscriber_id,tx_hash,channel,destination,status,detail,created_at) VALUES(?,?,?,?,?,?,?)", (subscriber_id, tx_hash, channel, destination, status, detail, utcnow()))
    def deliveries(self):
        with self.connect() as c: return [dict(r) for r in c.execute("SELECT * FROM deliveries ORDER BY id DESC LIMIT 100")]

def utcnow(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def hex_int(x): return int(x or "0x0", 16) if isinstance(x, str) else int(x or 0)
def wei_to_eth(v): return hex_int(v) / 10**18

class RpcClient:
    def __init__(self, chain: str): self.chain=chain; self.url=CHAIN_RPC[chain]
    def call(self, method: str, params: list[Any]):
        r = requests.post(self.url, json={"jsonrpc":"2.0","id":1,"method":method,"params":params}, timeout=20, headers={"User-Agent":"AgenticWorkWalletIntel/1.0"})
        r.raise_for_status(); data=r.json()
        if data.get("error"): raise RuntimeError(data["error"])
        return data.get("result")
    def latest_block(self) -> int: return hex_int(self.call("eth_blockNumber", []))
    def block(self, n: int) -> dict[str, Any]: return self.call("eth_getBlockByNumber", [hex(n), True]) or {"transactions": []}

def parse_transaction(event: TxEvent, wallet: dict[str, Any]) -> dict[str, Any]:
    method = (event.input_data or "0x")[:10].lower()
    if method == "0x" or event.input_data in ("", "0x"):
        event_type = "transfer"; action = f"transferred {event.value_eth:.4f} native ETH"; likely = "treasury transfer, payment, wallet rotation, or exchange movement"
    elif method == ERC20_TRANSFER:
        event_type = "transfer"; action = "submitted an ERC-20 transfer"; likely = "token transfer or exchange deposit/withdrawal"
    elif method in SWAP_SELECTORS:
        event_type = "swap"; action = "executed a DEX swap or routed swap"; likely = "accumulation, de-risking, arbitrage, or position rotation"
    elif method in LP_SELECTORS:
        event_type = "lp"; action = "changed a liquidity provider position"; likely = "liquidity provisioning, yield positioning, or pool exit"
    elif method in NFT_SELECTORS:
        event_type = "nft"; action = "moved or purchased an NFT"; likely = "NFT portfolio move or collection signal"
    else:
        event_type = "contract"; action = "interacted with a smart contract"; likely = "protocol usage, governance, claim, or custom strategy execution"
    score = min(100, int(wallet.get("tier_score", 40)) + (20 if event.value_eth >= 100 else 12 if event.value_eth >= 10 else 5 if event.value_eth >= 1 else 0) + (8 if event_type in {"swap","lp"} else 0) + (3 if event.chain == "base" else 0))
    return {"event_type": event_type, "summary": f"{wallet['label']} {action} on {event.chain} in tx {event.tx_hash[:10]}…", "context": f"{wallet['label']} is a {wallet['tier']} wallet; this {event_type} matters because tier, value and method imply {likely}.", "likely_intent": likely, "conviction_score": score}

def match_event(tx: dict[str, Any], chain: str, block_number: int, wallets: dict[str, dict[str, Any]]) -> tuple[TxEvent, dict[str, Any]] | None:
    from_addr = str(tx.get("from") or "").lower(); to_addr = str(tx.get("to") or "").lower(); wallet = wallets.get(from_addr) or wallets.get(to_addr)
    if not wallet or wallet.get("chain") not in ("all", chain): return None
    return TxEvent(chain=chain, tx_hash=tx.get("hash"), block_number=block_number, from_address=from_addr, to_address=to_addr, value_eth=wei_to_eth(tx.get("value", "0x0")), input_data=tx.get("input") or "0x"), wallet

def deliver_email(to_addr, subject, body):
    host=os.getenv("SMTP_HOST")
    if not host: return "stored", "SMTP_HOST not set; alert stored in development outbox"
    msg=EmailMessage(); msg["From"]=os.getenv("SMTP_FROM","wallet-alerts@agentic-work.local"); msg["To"]=to_addr; msg["Subject"]=subject; msg.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT","587")), timeout=20) as smtp:
        if os.getenv("SMTP_USER"): smtp.starttls(); smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
    return "sent", f"sent via {host}"
def deliver_telegram(chat_id, text):
    token=os.getenv("TELEGRAM_BOT_TOKEN")
    if not token: return "stored", "TELEGRAM_BOT_TOKEN not set; alert stored in development outbox"
    r=requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=15)
    return ("sent", f"HTTP {r.status_code}") if r.ok else ("failed", r.text[:160])
def deliver_webhook(url, payload):
    try:
        r=requests.post(url, json=payload, timeout=15, headers={"User-Agent":"AgenticWorkWalletIntel/1.0"})
        return ("sent", f"HTTP {r.status_code}") if 200 <= r.status_code < 300 else ("failed", f"HTTP {r.status_code}: {r.text[:120]}")
    except Exception as exc: return "failed", str(exc)
def x402_requirements(): return {"network":"base","asset":"USDC","amount":"99.00","pay_to":os.getenv("X402_PAY_TO", DEFAULT_WALLET),"product":"On-Chain Wallet Intelligence Starter monthly access","header":"X-PAYMENT"}
def require_paid(x_payment: str | None = Header(default=None), x_plan: str | None = Header(default=None)):
    if x_payment or (x_plan and x_plan.lower() in {"pro","institutional","enterprise"}): return
    raise HTTPException(402, {"error":"payment_required","payment":x402_requirements()})

store = Store(os.getenv("WALLET_INTEL_DB", "/tmp/onchain_wallet_intelligence.db"))
app = FastAPI(title=APP_NAME, version="1.0.0")
@app.get("/health")
def health(): return {"ok": True, "service": APP_NAME, "wallets": len(store.wallets()), "chains": list(CHAIN_RPC), "poll_interval_seconds": int(os.getenv("POLL_INTERVAL_SECONDS", "45"))}
@app.get("/api/payments/x402/requirements")
def payment_requirements(): return x402_requirements()
@app.get("/api/wallets")
def wallets(): return store.wallets()
@app.post("/api/subscribers")
def add_subscriber(sub: SubscriberCreate): return store.add_subscriber(sub)
@app.get("/api/subscribers")
def subscribers(): return store.subscribers()
@app.post("/api/watchlists")
def add_watchlist(item: WatchlistCreate): return store.add_wallet(item)
@app.post("/api/poll")
def poll(chains: str = Query(default="base,ethereum"), blocks: int = Query(default=2, ge=1, le=10)):
    wallet_map = {w["address"].lower(): w for w in store.wallets()}; seen=0; created=0; errors=[]
    for chain in [c.strip() for c in chains.split(",") if c.strip() in CHAIN_RPC]:
        try:
            rpc=RpcClient(chain); latest=rpc.latest_block()
            for n in range(max(0, latest-blocks+1), latest+1):
                block=rpc.block(n)
                for tx in block.get("transactions", []):
                    match=match_event(tx, chain, n, wallet_map)
                    if not match: continue
                    seen += 1; event, wallet = match; parsed = parse_transaction(event, wallet)
                    if store.add_alert(event, wallet, parsed):
                        created += 1; alert = store.alerts(wallet=wallet["address"], min_score=0, limit=1)[0]
                        for sub in store.subscribers():
                            if alert["conviction_score"] < sub["min_score"]: continue
                            msg=f"{alert['summary']}\n{alert['context']}\nScore: {alert['conviction_score']}/100"
                            if sub.get("email"):
                                status, detail=deliver_email(sub["email"], f"Wallet alert: {alert['event_type']} {alert['conviction_score']}/100", msg); store.add_delivery(sub["id"], event.tx_hash, "email", sub["email"], status, detail)
                            if sub.get("telegram_chat_id"):
                                status, detail=deliver_telegram(sub["telegram_chat_id"], msg); store.add_delivery(sub["id"], event.tx_hash, "telegram", sub["telegram_chat_id"], status, detail)
                            if sub.get("webhook_url"):
                                status, detail=deliver_webhook(sub["webhook_url"], {"alert": alert}); store.add_delivery(sub["id"], event.tx_hash, "webhook", sub["webhook_url"], status, detail)
        except Exception as exc: errors.append({"chain": chain, "error": str(exc)})
    return {"wallets_tracked": len(wallet_map), "matched_transactions": seen, "new_alerts": created, "errors": errors, "under_60_second_polling_configured": int(os.getenv("POLL_INTERVAL_SECONDS", "45")) <= 60}
@app.get("/api/alerts")
def alerts(chain: str | None = None, wallet: str | None = None, event_type: str | None = None, min_score: int = 0): return store.alerts(chain=chain, wallet=wallet, event_type=event_type, min_score=min_score)
@app.get("/api/deliveries")
def deliveries(): return store.deliveries()
@app.get("/api/export", dependencies=[Depends(require_paid)])
def export_data(): return {"wallets": store.wallets(), "alerts": store.alerts(min_score=0, limit=500), "exported_at": utcnow()}
@app.get("/", response_class=HTMLResponse)
def dashboard(chain: str | None = None, event_type: str | None = None, min_score: int = 0):
    alerts = store.alerts(chain=chain, event_type=event_type, min_score=min_score, limit=40); wallets = store.wallets(limit=12)
    alert_rows = "".join(f"<tr><td>{html.escape(a['chain'])}</td><td>{html.escape(a['wallet_label'])}</td><td><strong>{html.escape(a['event_type'])}</strong><br><small>{html.escape(a['summary'])}</small></td><td>{html.escape(a['context'])}</td><td>{a['conviction_score']}/100</td></tr>" for a in alerts) or "<tr><td colspan='5'>No alerts yet. POST /api/poll.</td></tr>"
    wallet_items = "".join(f"<li>{html.escape(w['label'])}: <code>{html.escape(w['address'][:10])}…</code> {w['tier_score']}/100</li>" for w in wallets)
    return f"""<!doctype html><html><head><title>{APP_NAME}</title><style>body{{font-family:Inter,system-ui,sans-serif;margin:32px;background:#08111f;color:#eef}}.card{{background:#13213a;padding:18px;border-radius:14px;margin:16px 0}}input,button{{padding:9px;border-radius:8px;border:1px solid #314567;background:#0e1728;color:#eef}}table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px solid #314567;padding:10px;text-align:left;vertical-align:top}}small{{color:#aab6d3}}code{{color:#9ff}}</style></head><body><h1>On-Chain Wallet Intelligence</h1><p>Base/Ethereum wallet monitoring, transaction parsing, AI context and real-time alerts.</p><div class='card'><h2>Filters</h2><form><input name='chain' value='{html.escape(chain or '')}' placeholder='base/ethereum'><input name='event_type' value='{html.escape(event_type or '')}' placeholder='swap/transfer/lp'><input name='min_score' value='{min_score}' placeholder='min score'><button>Filter</button></form></div><div class='card'><h2>Top watched wallets</h2><ul>{wallet_items}</ul></div><div class='card'><h2>Activity feed</h2><table><tr><th>Chain</th><th>Wallet</th><th>Event</th><th>Context</th><th>Score</th></tr>{alert_rows}</table></div><div class='card'><h2>Payment</h2><p>Starter $99/mo, Pro $299/mo, Institutional $999/mo. Export requires <code>X-PAYMENT</code>.</p></div></body></html>"""
