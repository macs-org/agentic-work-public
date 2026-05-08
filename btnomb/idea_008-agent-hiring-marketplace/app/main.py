from __future__ import annotations

import math
import os
import re
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

API_KEY = os.getenv("MARKETPLACE_API_KEY", "dev-marketplace-key")
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
ESCROW_CONTRACT_PLACEHOLDER = "0x0000000000000000000000000000000000000808"
ARBITRATION_FEE_PCT = 2.5


class TaskStatus(str, Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EscrowState(str, Enum):
    AWAITING_BID_ACCEPTANCE = "AWAITING_BID_ACCEPTANCE"
    HELD = "HELD"
    RELEASED = "RELEASED"
    REFUNDED = "REFUNDED"


class Category(str, Enum):
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    CONTENT_WRITING = "content_writing"
    SMART_CONTRACT_REVIEW = "smart_contract_review"


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    wallet: str
    capabilities: list[str] = Field(min_length=1)
    completed_tasks: int = Field(ge=0, default=0)
    approved_tasks: int = Field(ge=0, default=0)
    average_completion_hours: float = Field(gt=0, default=24)
    base_l2_attestation: str = Field(min_length=3)

    @field_validator("wallet")
    @classmethod
    def wallet_is_evm(cls, value: str) -> str:
        if not re.fullmatch(r"0x[a-fA-F0-9]{40}", value):
            raise ValueError("wallet must be an EVM address")
        return value

    @field_validator("approved_tasks")
    @classmethod
    def approvals_do_not_exceed_completed(cls, value: int, info: Any) -> int:
        completed = info.data.get("completed_tasks")
        if completed is not None and value > completed:
            raise ValueError("approved_tasks cannot exceed completed_tasks")
        return value


class AgentOut(BaseModel):
    id: str
    name: str
    wallet: str
    capabilities: list[str]
    completed_tasks: int
    approved_tasks: int
    average_completion_hours: float
    base_l2_attestation: str
    reputation_score: float


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    requirements: dict[str, Any]
    acceptance_criteria: list[str] = Field(min_length=1)
    deadline: datetime
    budget_usdc: float = Field(gt=0)
    category: Category

    @field_validator("deadline")
    @classmethod
    def deadline_is_future(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        if value <= datetime.now(timezone.utc):
            raise ValueError("deadline must be in the future")
        return value


class BidCreate(BaseModel):
    agent_id: str
    cost_usdc: float = Field(gt=0)
    estimated_hours: float = Field(gt=0)
    proposal: str = Field(min_length=10)


class SubmissionCreate(BaseModel):
    agent_id: str
    artifact_url: str = Field(pattern=r"^https?://")
    summary: str = Field(min_length=8)


class ApprovalRequest(BaseModel):
    approved: bool


@dataclass
class Store:
    agents: dict[str, dict[str, Any]] = field(default_factory=dict)
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    bids: dict[str, dict[str, Any]] = field(default_factory=dict)
    submissions: dict[str, dict[str, Any]] = field(default_factory=dict)

    def reset(self) -> None:
        self.agents.clear()
        self.tasks.clear()
        self.bids.clear()
        self.submissions.clear()


store = Store()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The submitted deliverable is demo/self-contained. Real deployments can swap
    # Store for a database-backed repository while keeping the same API surface.
    store.reset()
    yield


app = FastAPI(
    title="Agent Hiring Marketplace",
    version="1.0.0",
    description="Autonomous task-posting, agent discovery, bidding, ranking, x402 escrow simulation, and approval release API.",
    lifespan=lifespan,
)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Valid X-API-Key required")


def reputation_score(agent: dict[str, Any]) -> float:
    completed = max(int(agent.get("completed_tasks", 0)), 0)
    approved = max(int(agent.get("approved_tasks", 0)), 0)
    approval_rate = approved / completed if completed else 0.5
    speed_score = max(0.0, min(1.0, 1.0 - (float(agent.get("average_completion_hours", 24)) / 72.0)))
    volume_score = min(1.0, math.log1p(completed) / math.log(51))
    attestation_bonus = 1.0 if str(agent.get("base_l2_attestation", "")).startswith("eas:base:") else 0.0
    score = (approval_rate * 55) + (speed_score * 20) + (volume_score * 15) + (attestation_bonus * 10)
    return round(min(score, 100.0), 2)


def escrow_shell(amount: float | None = None, state: EscrowState = EscrowState.AWAITING_BID_ACCEPTANCE) -> dict[str, Any]:
    return {
        "state": state.value,
        "network": "base",
        "asset": "USDC",
        "asset_address": BASE_USDC,
        "contract": ESCROW_CONTRACT_PLACEHOLDER,
        "x402_scheme": "exact",
        "amount_usdc": amount,
    }


def capability_match(agent: dict[str, Any], task: dict[str, Any]) -> float:
    caps = {str(c).lower() for c in agent.get("capabilities", [])}
    wanted = {str(task.get("category", "")).lower()}
    for v in task.get("requirements", {}).values():
        if isinstance(v, str):
            wanted.add(v.lower())
        elif isinstance(v, list):
            wanted.update(str(item).lower() for item in v)
    if not wanted:
        return 0.0
    return round(len(caps & wanted) / len(wanted), 4)


def bid_rank_score(bid: dict[str, Any]) -> float:
    agent = store.agents[bid["agent_id"]]
    task = store.tasks[bid["task_id"]]
    rep_component = agent["reputation_score"] * 0.5
    match_component = capability_match(agent, task) * 25
    cost_component = max(0.0, 1 - (float(bid["cost_usdc"]) / float(task["budget_usdc"]))) * 15
    speed_component = max(0.0, 1 - (float(bid["estimated_hours"]) / 72.0)) * 10
    return round(rep_component + match_component + cost_component + speed_component, 2)


def public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {**task, "escrow": dict(task["escrow"])}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agents", response_model=AgentOut, dependencies=[Depends(require_api_key)])
def register_agent(payload: AgentCreate) -> dict[str, Any]:
    data = payload.model_dump()
    data["id"] = f"agent_{uuid4().hex[:10]}"
    data["capabilities"] = sorted({c.strip().lower() for c in data["capabilities"] if c.strip()})
    data["reputation_score"] = reputation_score(data)
    store.agents[data["id"]] = data
    return data


@app.get("/agents/{agent_id}", response_model=AgentOut, dependencies=[Depends(require_api_key)])
def get_agent(agent_id: str) -> dict[str, Any]:
    if agent_id not in store.agents:
        raise HTTPException(status_code=404, detail="agent not found")
    return store.agents[agent_id]


@app.post("/tasks", dependencies=[Depends(require_api_key)])
def create_task(payload: TaskCreate) -> dict[str, Any]:
    data = payload.model_dump(mode="json")
    data.update(
        {
            "id": f"task_{uuid4().hex[:10]}",
            "status": TaskStatus.OPEN.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "winning_bid_id": None,
            "escrow": escrow_shell(),
        }
    )
    store.tasks[data["id"]] = data
    return public_task(data)


@app.get("/tasks", dependencies=[Depends(require_api_key)])
def list_tasks(status: TaskStatus | None = None, category: Category | None = None) -> list[dict[str, Any]]:
    rows = list(store.tasks.values())
    if status:
        rows = [t for t in rows if t["status"] == status.value]
    if category:
        rows = [t for t in rows if t["category"] == category.value]
    return [public_task(t) for t in sorted(rows, key=lambda r: r["created_at"], reverse=True)]


@app.get("/agents/{agent_id}/tasks", dependencies=[Depends(require_api_key)])
def discover_tasks(agent_id: str) -> list[dict[str, Any]]:
    if agent_id not in store.agents:
        raise HTTPException(status_code=404, detail="agent not found")
    agent = store.agents[agent_id]
    rows = []
    for task in store.tasks.values():
        if task["status"] != TaskStatus.OPEN.value:
            continue
        score = capability_match(agent, task)
        rows.append({**public_task(task), "capability_match": score})
    return sorted(rows, key=lambda row: (row["capability_match"], row["budget_usdc"]), reverse=True)


@app.post("/tasks/{task_id}/bids", dependencies=[Depends(require_api_key)])
def create_bid(task_id: str, payload: BidCreate) -> dict[str, Any]:
    if task_id not in store.tasks:
        raise HTTPException(status_code=404, detail="task not found")
    if payload.agent_id not in store.agents:
        raise HTTPException(status_code=404, detail="agent not found")
    task = store.tasks[task_id]
    if task["status"] != TaskStatus.OPEN.value:
        raise HTTPException(status_code=409, detail="task is not open for bids")
    if payload.cost_usdc > float(task["budget_usdc"]):
        raise HTTPException(status_code=422, detail="bid cost exceeds task budget")
    bid = payload.model_dump()
    bid.update({"id": f"bid_{uuid4().hex[:10]}", "task_id": task_id, "status": "PENDING", "created_at": datetime.now(timezone.utc).isoformat()})
    bid["rank_score"] = bid_rank_score(bid)
    store.bids[bid["id"]] = bid
    return bid


@app.get("/tasks/{task_id}/bids/ranked", dependencies=[Depends(require_api_key)])
def ranked_bids(task_id: str) -> list[dict[str, Any]]:
    if task_id not in store.tasks:
        raise HTTPException(status_code=404, detail="task not found")
    bids = [b for b in store.bids.values() if b["task_id"] == task_id]
    for bid in bids:
        bid["rank_score"] = bid_rank_score(bid)
    return sorted(bids, key=lambda b: b["rank_score"], reverse=True)


@app.post("/bids/{bid_id}/accept", dependencies=[Depends(require_api_key)])
def accept_bid(bid_id: str) -> dict[str, Any]:
    if bid_id not in store.bids:
        raise HTTPException(status_code=404, detail="bid not found")
    bid = store.bids[bid_id]
    task = store.tasks[bid["task_id"]]
    agent = store.agents[bid["agent_id"]]
    if task["status"] != TaskStatus.OPEN.value:
        raise HTTPException(status_code=409, detail="task already awarded")
    bid["status"] = "ACCEPTED"
    task["status"] = TaskStatus.ASSIGNED.value
    task["winning_bid_id"] = bid_id
    task["assigned_agent_id"] = agent["id"]
    task["escrow"] = escrow_shell(float(bid["cost_usdc"]), EscrowState.HELD)
    task["escrow"].update({"held_for_agent": agent["wallet"], "held_at": datetime.now(timezone.utc).isoformat()})
    return {
        **public_task(task),
        "assigned_agent": {"id": agent["id"], "wallet": agent["wallet"], "full_spec_visible": True},
    }


@app.post("/tasks/{task_id}/submissions", dependencies=[Depends(require_api_key)])
def submit_work(task_id: str, payload: SubmissionCreate) -> dict[str, Any]:
    if task_id not in store.tasks:
        raise HTTPException(status_code=404, detail="task not found")
    task = store.tasks[task_id]
    if task.get("assigned_agent_id") != payload.agent_id:
        raise HTTPException(status_code=403, detail="only assigned agent may submit")
    if task["status"] != TaskStatus.ASSIGNED.value:
        raise HTTPException(status_code=409, detail="task is not awaiting submission")
    sub = payload.model_dump()
    sub.update({"id": f"sub_{uuid4().hex[:10]}", "task_id": task_id, "status": TaskStatus.SUBMITTED.value, "submitted_at": datetime.now(timezone.utc).isoformat()})
    store.submissions[sub["id"]] = sub
    task["status"] = TaskStatus.SUBMITTED.value
    return sub


@app.post("/submissions/{submission_id}/approve", dependencies=[Depends(require_api_key)])
def approve_submission(submission_id: str, payload: ApprovalRequest) -> dict[str, Any]:
    if submission_id not in store.submissions:
        raise HTTPException(status_code=404, detail="submission not found")
    sub = store.submissions[submission_id]
    task = store.tasks[sub["task_id"]]
    agent = store.agents[sub["agent_id"]]
    amount = float(task["escrow"]["amount_usdc"])
    if payload.approved:
        task["status"] = TaskStatus.APPROVED.value
        task["escrow"].update({"state": EscrowState.RELEASED.value, "released_to": agent["wallet"], "released_amount_usdc": amount})
        agent["completed_tasks"] += 1
        agent["approved_tasks"] += 1
    else:
        fee = round(amount * (ARBITRATION_FEE_PCT / 100), 2)
        task["status"] = TaskStatus.REJECTED.value
        task["escrow"].update({"state": EscrowState.REFUNDED.value, "arbitration_fee_usdc": fee, "refund_to_poster_usdc": round(amount - fee, 2)})
        agent["completed_tasks"] += 1
    agent["reputation_score"] = reputation_score(agent)
    sub["status"] = task["status"]
    return {"submission_id": submission_id, "task_status": task["status"], "escrow": task["escrow"]}


@app.get("/dashboard/stats", dependencies=[Depends(require_api_key)])
def dashboard_stats() -> dict[str, Any]:
    capabilities = Counter(cap for agent in store.agents.values() for cap in agent["capabilities"])
    tasks_by_status = Counter(task["status"] for task in store.tasks.values())
    return {
        "agents_total": len(store.agents),
        "tasks_total": len(store.tasks),
        "open_tasks": tasks_by_status.get(TaskStatus.OPEN.value, 0),
        "assigned_tasks": tasks_by_status.get(TaskStatus.ASSIGNED.value, 0),
        "submitted_tasks": tasks_by_status.get(TaskStatus.SUBMITTED.value, 0),
        "approved_tasks": tasks_by_status.get(TaskStatus.APPROVED.value, 0),
        "escrow_held_usdc": round(sum(float(t["escrow"].get("amount_usdc") or 0) for t in store.tasks.values() if t["escrow"]["state"] == EscrowState.HELD.value), 2),
        "registered_capabilities": dict(sorted(capabilities.items())),
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    task_rows = "".join(
        f"<tr><td>{t['title']}</td><td>{t['category']}</td><td>{t['status']}</td><td>${t['budget_usdc']}</td></tr>"
        for t in store.tasks.values()
    ) or "<tr><td colspan='4'>No tasks yet</td></tr>"
    stats = {
        "agents": len(store.agents),
        "tasks": len(store.tasks),
        "active_bids": len([b for b in store.bids.values() if b["status"] == "PENDING"]),
    }
    return f"""
    <!doctype html>
    <html><head><title>Agent Hiring Marketplace</title>
    <style>body{{font-family:Inter,system-ui,sans-serif;margin:2rem;background:#0b1020;color:#eef}}table{{border-collapse:collapse;width:100%;background:#121a33}}td,th{{border:1px solid #334;padding:.6rem}}.cards{{display:flex;gap:1rem}}.card{{background:#16213f;padding:1rem;border-radius:12px}}</style>
    </head><body>
    <h1>Agent Hiring Marketplace</h1>
    <p>Autonomous AI workers discover tasks, bid, escrow USDC over x402-compatible Base rails, and get paid when work is approved.</p>
    <div class="cards"><div class="card">Agents: {stats['agents']}</div><div class="card">Tasks: {stats['tasks']}</div><div class="card">Pending bids: {stats['active_bids']}</div></div>
    <h2>Active tasks</h2><table><thead><tr><th>Title</th><th>Category</th><th>Status</th><th>Budget</th></tr></thead><tbody>{task_rows}</tbody></table>
    </body></html>
    """
