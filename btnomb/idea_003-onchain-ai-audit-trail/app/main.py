from __future__ import annotations
import hashlib, html, json, os, sqlite3
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
APP_NAME = "On-chain AI Audit Trail"; MAX_BATCH_SIZE = 100
class ActionIn(BaseModel):
    agent_id: str = Field(min_length=1); action_type: str = Field(min_length=1); input_hash: str = Field(min_length=1); output_hash: str = Field(min_length=1); timestamp: str = Field(min_length=1); description: str = Field(min_length=1)
class Store:
    def __init__(self, path: str): self.path = path; self.init()
    def connect(self): c = sqlite3.connect(self.path); c.row_factory = sqlite3.Row; return c
    def init(self):
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS actions(id INTEGER PRIMARY KEY AUTOINCREMENT,agent_id TEXT,action_type TEXT,input_hash TEXT,output_hash TEXT,timestamp TEXT,description TEXT,action_hash TEXT UNIQUE,batch_id INTEGER,proof TEXT,created_at TEXT);
            CREATE TABLE IF NOT EXISTS batches(id INTEGER PRIMARY KEY AUTOINCREMENT,merkle_root TEXT NOT NULL,action_count INTEGER NOT NULL,contract_address TEXT,tx_hash TEXT,committed_at TEXT NOT NULL);
            """)
    def add_action(self, action: ActionIn, action_hash: str):
        with self.connect() as c:
            c.execute('INSERT OR IGNORE INTO actions(agent_id,action_type,input_hash,output_hash,timestamp,description,action_hash,batch_id,proof,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)', (action.agent_id, action.action_type, action.input_hash, action.output_hash, action.timestamp, action.description, action_hash, None, '[]', utcnow()))
            return dict(c.execute('SELECT * FROM actions WHERE action_hash=?', (action_hash,)).fetchone())
    def pending(self):
        with self.connect() as c: return [dict(r) for r in c.execute('SELECT * FROM actions WHERE batch_id IS NULL ORDER BY id LIMIT ?', (MAX_BATCH_SIZE,))]
    def all_actions(self, limit=100):
        with self.connect() as c: return [dict(r) for r in c.execute('SELECT * FROM actions ORDER BY id DESC LIMIT ?', (limit,))]
    def action_by_hash(self, h: str):
        with self.connect() as c:
            r=c.execute('SELECT * FROM actions WHERE action_hash=?', (h,)).fetchone(); return dict(r) if r else None
    def batch(self, batch_id: int):
        with self.connect() as c:
            r=c.execute('SELECT * FROM batches WHERE id=?', (batch_id,)).fetchone(); return dict(r) if r else None
    def batches(self):
        with self.connect() as c: return [dict(r) for r in c.execute('SELECT * FROM batches ORDER BY id DESC LIMIT 50')]
    def commit(self, rows, root, proofs):
        with self.connect() as c:
            cur=c.execute('INSERT INTO batches(merkle_root,action_count,contract_address,tx_hash,committed_at) VALUES(?,?,?,?,?)', (root, len(rows), os.getenv('AUDIT_CONTRACT_ADDRESS'), os.getenv('LAST_COMMIT_TX_HASH'), utcnow()))
            bid=cur.lastrowid
            for row, proof in zip(rows, proofs): c.execute('UPDATE actions SET batch_id=?, proof=? WHERE id=?', (bid, json.dumps(proof), row['id']))
            return dict(c.execute('SELECT * FROM batches WHERE id=?', (bid,)).fetchone())
def utcnow(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def canonical_action(a: ActionIn | dict) -> str:
    d = a.model_dump() if isinstance(a, ActionIn) else {k:a[k] for k in ['agent_id','action_type','input_hash','output_hash','timestamp','description']}
    return json.dumps({k: d[k] for k in sorted(d)}, separators=(',', ':'), ensure_ascii=False)
def hash_action(a: ActionIn | dict) -> str: return hashlib.sha256(canonical_action(a).encode()).hexdigest()
def sha_pair(left: str, right: str) -> str: return hashlib.sha256(bytes.fromhex(left)+bytes.fromhex(right)).hexdigest()
def merkle_layers(leaves: list[str]) -> list[list[str]]:
    if not leaves: raise ValueError('no leaves')
    layers=[leaves]
    while len(layers[-1]) > 1:
        cur=layers[-1]; nxt=[]
        for i in range(0, len(cur), 2):
            left=cur[i]; right=cur[i+1] if i+1 < len(cur) else cur[i]; nxt.append(sha_pair(left, right))
        layers.append(nxt)
    return layers
def merkle_root(leaves: list[str]) -> str: return merkle_layers(leaves)[-1][0]
def merkle_proof(leaves: list[str], index: int) -> list[str]:
    layers=merkle_layers(leaves); proof=[]; idx=index
    for layer in layers[:-1]:
        sibling = idx-1 if idx % 2 else idx+1; proof.append(layer[sibling] if sibling < len(layer) else layer[idx]); idx //= 2
    return proof
def verify_proof(leaf: str, proof: list[str], root: str, index: int) -> bool:
    h=leaf; idx=index
    for p in proof: h = sha_pair(p, h) if idx % 2 else sha_pair(h, p); idx //= 2
    return h == root
store = Store(os.getenv('AUDIT_TRAIL_DB', '/tmp/onchain_ai_audit_trail.db')); app = FastAPI(title=APP_NAME, version='1.0.0')
@app.get('/health')
def health(): return {'ok': True, 'service': APP_NAME, 'max_batch_size': MAX_BATCH_SIZE, 'contract_address': os.getenv('AUDIT_CONTRACT_ADDRESS')}
@app.post('/api/actions')
def log_action(action: ActionIn):
    h=hash_action(action); row=store.add_action(action, h); return {'action_hash': h, 'status': 'queued' if row['batch_id'] is None else 'committed', 'action': row}
@app.post('/api/batches/commit')
def commit_batch():
    rows=store.pending()
    if not rows: raise HTTPException(400, 'no pending actions')
    leaves=[r['action_hash'] for r in rows]; root=merkle_root(leaves); proofs=[merkle_proof(leaves, i) for i in range(len(leaves))]
    return {'batch': store.commit(rows, root, proofs), 'merkle_root': root, 'actions': len(rows), 'base_ready': True}
@app.post('/api/verify')
def verify_action(action: ActionIn):
    h=hash_action(action); row=store.action_by_hash(h)
    if not row: return {'verified': False, 'action_hash': h, 'reason': 'hash not found'}
    if not row['batch_id']: return {'verified': False, 'action_hash': h, 'reason': 'action queued but not committed'}
    batch=store.batch(row['batch_id'])
    with store.connect() as c: batch_rows=[dict(r) for r in c.execute('SELECT * FROM actions WHERE batch_id=? ORDER BY id', (row['batch_id'],))]
    index=[r['action_hash'] for r in batch_rows].index(h); proof=json.loads(row['proof']); ok=verify_proof(h, proof, batch['merkle_root'], index)
    return {'verified': ok, 'action_hash': h, 'batch_id': row['batch_id'], 'merkle_root': batch['merkle_root'], 'proof': proof, 'index': index, 'contract_address': batch['contract_address'], 'tx_hash': batch['tx_hash']}
@app.get('/api/actions')
def actions(): return store.all_actions()
@app.get('/api/batches')
def batches(): return store.batches()
@app.get('/', response_class=HTMLResponse)
def explorer():
    actions=store.all_actions(50); batches=store.batches()
    rows=''.join(f"<tr><td>{a['id']}</td><td>{html.escape(a['agent_id'])}</td><td>{html.escape(a['action_type'])}</td><td><code>{a['action_hash'][:16]}…</code></td><td>{'committed' if a['batch_id'] else 'queued'}</td></tr>" for a in actions) or "<tr><td colspan='5'>No actions yet.</td></tr>"
    batch_items=''.join(f"<li>Batch #{b['id']}: <code>{b['merkle_root'][:18]}…</code> ({b['action_count']} actions)</li>" for b in batches) or '<li>No batches yet</li>'
    return f"""<!doctype html><html><head><title>{APP_NAME}</title><style>body{{font-family:Inter,system-ui,sans-serif;margin:32px;background:#0b1020;color:#eef}}.card{{background:#151b31;padding:18px;border-radius:14px;margin:16px 0}}table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px solid #334;padding:10px;text-align:left}}code{{color:#9ff}}</style></head><body><h1>On-chain AI Audit Trail</h1><p>Canonical agent-action hashes, Merkle batches, Base-ready root commits, and auditor verification.</p><div class='card'><h2>Recent batches</h2><ul>{batch_items}</ul></div><div class='card'><h2>Recent actions</h2><table><tr><th>ID</th><th>Agent</th><th>Type</th><th>Hash</th><th>Status</th></tr>{rows}</table></div></body></html>"""
