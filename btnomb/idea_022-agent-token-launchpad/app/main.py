
from __future__ import annotations
import hashlib, html, json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

APP='Agent Token Launchpad'
DB_PATH=Path(os.environ.get('LAUNCHPAD_DB_PATH','/tmp/agent_token_launchpad.sqlite'))
TREASURY=os.environ.get('TREASURY_WALLET','0xC7F6C7F6C7F6C7F6C7F6C7F6C7F6C7F6C7F6875e')
GRADUATION_USD=float(os.environ.get('GRADUATION_USD','69000'))
FEE_BPS=100
app=FastAPI(title=APP, version='1.0.0')

class LaunchIn(BaseModel):
    name:str=Field(min_length=2,max_length=64)
    ticker:str=Field(min_length=2,max_length=12)
    description:str=Field(min_length=5,max_length=500)
    image_url:str='https://placehold.co/512x512?text=AI+Token'
    deployer_wallet:str=Field(pattern=r'^0x[a-fA-F0-9]{40}$')
    agent_metadata:Dict[str,Any]={}
class TradeIn(BaseModel):
    trader_wallet:str=Field(pattern=r'^0x[a-fA-F0-9]{40}$')
    side:str=Field(pattern='^(buy|sell)$')
    amount_usdc:float=Field(gt=0,le=100000)

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS launches(id INTEGER PRIMARY KEY AUTOINCREMENT, token_address TEXT UNIQUE, name TEXT, ticker TEXT, description TEXT, image_url TEXT, deployer_wallet TEXT, reserve_usdc REAL DEFAULT 0, supply REAL DEFAULT 0, price REAL DEFAULT 0.001, graduated INTEGER DEFAULT 0, created_at TEXT, agent_metadata TEXT);
    CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY AUTOINCREMENT, token_address TEXT, trader_wallet TEXT, side TEXT, amount_usdc REAL, tokens_delta REAL, fee_usdc REAL, price_after REAL, created_at TEXT);
    """)
    return c
def deterministic_address(seed:str)->str: return '0x'+hashlib.sha256(seed.encode()).hexdigest()[-40:]
def quote(reserve:float, supply:float, amount:float, side:str):
    price=max(0.001, 0.001 + supply/10_000_000 + reserve/6_900_000)
    fee=round(amount*FEE_BPS/10000,6); net=amount-fee
    tokens=net/price
    price_after=max(0.001, 0.001 + (supply + (tokens if side=='buy' else -tokens))/10_000_000 + (reserve + (net if side=='buy' else -net))/6_900_000)
    return {'fee_usdc':fee,'tokens_delta':round(tokens,6),'price_before':round(price,8),'price_after':round(price_after,8),'treasury':TREASURY}

def seed_if_empty():
    with db() as c:
        if c.execute('SELECT COUNT(*) n FROM launches').fetchone()['n']==0:
            for name,ticker,wallet in [('Research Agent Alpha','RAA','0x1111111111111111111111111111111111111111'),('Audit Swarm','AUDIT','0x2222222222222222222222222222222222222222')]:
                addr=deterministic_address(name+ticker)
                c.execute('INSERT OR IGNORE INTO launches(token_address,name,ticker,description,image_url,deployer_wallet,price,created_at,agent_metadata) VALUES(?,?,?,?,?,?,?,?,?)',(addr,name,ticker,'AI agent token launched through the REST API.','https://placehold.co/512x512',wallet,0.001,now(),'{}'))
@app.on_event('startup')
def startup(): db()
@app.get('/health')
def health(): return {'ok':True,'app':APP,'fee_bps':FEE_BPS,'graduation_usd':GRADUATION_USD,'time':now()}
@app.get('/openapi-agent.json')
def openapi_agent(): return app.openapi()
@app.get('/pricing')
def pricing(): return {'revenue_model':'1% fee on every buy/sell','fee_bps':FEE_BPS,'treasury':TREASURY,'payment_network':'Base','x402_exports':True}
@app.post('/launch')
def launch(req:LaunchIn):
    addr=deterministic_address(f"{req.deployer_wallet}:{req.ticker}:{req.name}:{now()}")
    with db() as c:
        c.execute('INSERT INTO launches(token_address,name,ticker,description,image_url,deployer_wallet,price,created_at,agent_metadata) VALUES(?,?,?,?,?,?,?,?,?)',(addr,req.name,req.ticker.upper(),req.description,req.image_url,req.deployer_wallet,0.001,now(),json.dumps(req.agent_metadata)))
    return {'token_address':addr,'contract_address':addr,'landing_page_url':f'/tokens/{addr}','api_url':f'/tokens/{addr}','chain':'base','status':'launched_simulated_testnet_ready'}
@app.get('/tokens')
def tokens(q:Optional[str]=None):
    seed_if_empty()
    with db() as c: rows=c.execute('SELECT * FROM launches ORDER BY id DESC').fetchall()
    out=[dict(r) for r in rows]
    if q: out=[r for r in out if q.lower() in (r['name']+' '+r['ticker']).lower()]
    return {'count':len(out),'tokens':out}
@app.get('/tokens/{token_address}')
def token(token_address:str):
    with db() as c:
        row=c.execute('SELECT * FROM launches WHERE token_address=?',(token_address,)).fetchone()
        trades=c.execute('SELECT * FROM trades WHERE token_address=? ORDER BY id DESC LIMIT 25',(token_address,)).fetchall()
    if not row: raise HTTPException(404,'token not found')
    d=dict(row); d['trades']=[dict(t) for t in trades]; d['bonding_curve_progress_pct']=round(min(100,d['reserve_usdc']/GRADUATION_USD*100),4)
    return d
@app.post('/tokens/{token_address}/trade')
def trade(token_address:str, req:TradeIn):
    with db() as c:
        row=c.execute('SELECT * FROM launches WHERE token_address=?',(token_address,)).fetchone()
        if not row: raise HTTPException(404,'token not found')
        if row['graduated']: raise HTTPException(409,'token already graduated to DEX')
        q=quote(row['reserve_usdc'],row['supply'],req.amount_usdc,req.side)
        reserve=max(0,row['reserve_usdc'] + (req.amount_usdc-q['fee_usdc'] if req.side=='buy' else -req.amount_usdc))
        supply=max(0,row['supply'] + (q['tokens_delta'] if req.side=='buy' else -q['tokens_delta']))
        graduated=1 if reserve>=GRADUATION_USD else 0
        c.execute('UPDATE launches SET reserve_usdc=?,supply=?,price=?,graduated=? WHERE token_address=?',(reserve,supply,q['price_after'],graduated,token_address))
        c.execute('INSERT INTO trades(token_address,trader_wallet,side,amount_usdc,tokens_delta,fee_usdc,price_after,created_at) VALUES(?,?,?,?,?,?,?,?)',(token_address,req.trader_wallet,req.side,req.amount_usdc,q['tokens_delta'],q['fee_usdc'],q['price_after'],now()))
    return {'token_address':token_address,'side':req.side,'quote':q,'graduated':bool(graduated),'dex_route':'Aerodrome/Uniswap migration queued' if graduated else None}
@app.get('/api/export')
def export(x_payment:Optional[str]=Header(default=None, alias='X-PAYMENT')):
    if not x_payment: return JSONResponse(status_code=402, content={'error':'payment_required','network':'base','asset':'USDC','recipient':TREASURY})
    return tokens()
@app.get('/', response_class=HTMLResponse)
def home():
    data=tokens()['tokens']
    cards=''.join([f"<section class='card'><h2><a href='/tokens/{html.escape(t['token_address'])}'>{html.escape(t['ticker'])}</a></h2><p>{html.escape(t['description'])}</p><p>Reserve ${t['reserve_usdc']:.2f} · Supply {t['supply']:.2f} · Price ${t['price']:.6f}</p><p>Graduation {min(100,t['reserve_usdc']/GRADUATION_USD*100):.2f}%</p></section>" for t in data])
    return f"""<!doctype html><html><head><title>{APP}</title><style>body{{font-family:Inter,system-ui;background:#070b16;color:#e8eefc;margin:0}}header{{padding:40px;background:linear-gradient(135deg,#111827,#312e81)}}main{{padding:30px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}.card{{background:#111827;border:1px solid #374151;border-radius:16px;padding:18px}}a{{color:#93c5fd}}code{{background:#020617;padding:3px 6px;border-radius:5px}}</style></head><body><header><h1>{APP}</h1><p>Pump.fun-style bonding curve launchpad for AI agents on Base. REST launch API, token pages, discovery feed, buy/sell simulation, 1% platform fee, DEX graduation trigger, OpenAPI for agents.</p></header><main><p><code>POST /launch</code> · <code>POST /tokens/{{address}}/trade</code> · <code>GET /openapi-agent.json</code></p><div class='grid'>{cards}</div></main></body></html>"""
