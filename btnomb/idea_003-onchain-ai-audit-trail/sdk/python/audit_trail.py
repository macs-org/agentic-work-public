from __future__ import annotations
import hashlib, json, requests
from dataclasses import dataclass, asdict

@dataclass
class ActionLog:
    agent_id: str; action_type: str; input_hash: str; output_hash: str; timestamp: str; description: str

def canonical_action(action: ActionLog | dict) -> str:
    data = asdict(action) if isinstance(action, ActionLog) else dict(action)
    return json.dumps({k: data[k] for k in sorted(data)}, separators=(",", ":"), ensure_ascii=False)

def hash_action(action: ActionLog | dict) -> str:
    return hashlib.sha256(canonical_action(action).encode()).hexdigest()

class AuditTrailClient:
    def __init__(self, base_url: str): self.base_url = base_url.rstrip("/")
    def log_action(self, action: ActionLog | dict) -> dict:
        payload = asdict(action) if isinstance(action, ActionLog) else action
        r = requests.post(f"{self.base_url}/api/actions", json=payload, timeout=30); r.raise_for_status(); return r.json()
    def verify_action(self, action: ActionLog | dict) -> dict:
        payload = asdict(action) if isinstance(action, ActionLog) else action
        r = requests.post(f"{self.base_url}/api/verify", json=payload, timeout=30); r.raise_for_status(); return r.json()
