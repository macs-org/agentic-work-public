from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, select, func
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

VECTOR_DIMS = 64
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
DEFAULT_PAY_TO = "0x9c768177521C9A832B0f8567265ef02E89D0282e"
PLAN_PRICES_CENTS = {"free": 0, "starter": 1900, "pro": 9900, "enterprise": 49900}


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"
    agent_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    api_key = Column(String, nullable=False, unique=True, index=True)


class Memory(Base):
    __tablename__ = "memories"
    memory_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    namespace = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    meta_json = Column(Text, nullable=False, default="{}")
    embedding_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class Usage(Base):
    __tablename__ = "usage"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class AgentCreate(BaseModel):
    name: str


class MemoryCreate(BaseModel):
    namespace: str = "default"
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanCheckoutRequest(BaseModel):
    plan: str


def make_session_factory(database_url: str):
    connect_args: dict[str, Any] = {}
    kwargs: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    if database_url == "sqlite:///:memory:":
        kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, connect_args=connect_args, **kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def embed(text: str) -> list[float]:
    vec = [0.0] * VECTOR_DIMS
    for token in tokenize(text):
        idx = int(hashlib.sha256(token.encode()).hexdigest(), 16) % VECTOR_DIMS
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def memory_to_dict(memory: Memory, score: float | None = None) -> dict[str, Any]:
    out = {
        "memory_id": memory.memory_id,
        "namespace": memory.namespace,
        "content": memory.content,
        "metadata": json.loads(memory.meta_json or "{}"),
        "created_at": memory.created_at.isoformat(),
    }
    if score is not None:
        out["score"] = round(score, 6)
    return out


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


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(
        title="Agent Memory-as-a-Service",
        description="Managed memory storage and semantic retrieval API for AI agents.",
        version="0.1.0",
    )
    SessionLocal = make_session_factory(database_url or "sqlite:///agent_memory.db")

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def current_agent(x_api_key: str | None = Header(default=None, alias="X-API-Key"), db: Session = Depends(get_db)) -> Agent:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="missing_or_invalid_api_key")
        agent = db.scalar(select(Agent).where(Agent.api_key == x_api_key))
        if not agent:
            raise HTTPException(status_code=401, detail="missing_or_invalid_api_key")
        return agent

    def record_usage(db: Session, agent_id: str, action: str) -> None:
        db.add(Usage(agent_id=agent_id, action=action, created_at=datetime.now(UTC)))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/agents", status_code=201)
    def create_agent(payload: AgentCreate, db: Session = Depends(get_db)) -> dict[str, str]:
        agent = Agent(agent_id="agt_" + secrets.token_hex(8), name=payload.name, api_key="ak_" + secrets.token_urlsafe(24))
        db.add(agent)
        db.commit()
        return {"agent_id": agent.agent_id, "name": agent.name, "api_key": agent.api_key}

    @app.post("/memory", status_code=201)
    def store_memory(payload: MemoryCreate, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        memory = Memory(
            memory_id="mem_" + secrets.token_hex(8),
            agent_id=agent.agent_id,
            namespace=payload.namespace,
            content=payload.content,
            meta_json=json.dumps(payload.metadata, sort_keys=True),
            embedding_json=json.dumps(embed(payload.content)),
            created_at=datetime.now(UTC),
        )
        db.add(memory)
        record_usage(db, agent.agent_id, "store")
        db.commit()
        db.refresh(memory)
        return memory_to_dict(memory)

    @app.get("/memory/search")
    def search_memory(q: str, namespace: str = "default", top_k: int = 5, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        query_vec = embed(q)
        memories = list(db.scalars(select(Memory).where(Memory.agent_id == agent.agent_id, Memory.namespace == namespace)))
        ranked = sorted(((memory, cosine(query_vec, json.loads(memory.embedding_json))) for memory in memories), key=lambda item: item[1], reverse=True)
        record_usage(db, agent.agent_id, "search")
        db.commit()
        return {"query": q, "namespace": namespace, "results": [memory_to_dict(memory, score) for memory, score in ranked[:top_k] if score > 0]}

    @app.delete("/memory/{memory_id}")
    def delete_memory(memory_id: str, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        memory = db.scalar(select(Memory).where(Memory.agent_id == agent.agent_id, Memory.memory_id == memory_id))
        if not memory:
            raise HTTPException(status_code=404, detail="memory_not_found")
        db.delete(memory)
        record_usage(db, agent.agent_id, "delete")
        db.commit()
        return {"deleted": True, "memory_id": memory_id}

    @app.get("/usage")
    def usage(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, int | str]:
        counts = {"store": 0, "search": 0, "delete": 0, "plan_checkout": 0}
        rows = db.execute(select(Usage.action, func.count()).where(Usage.agent_id == agent.agent_id).group_by(Usage.action)).all()
        for action, count in rows:
            counts[action] = int(count)
        memory_count = db.scalar(select(func.count()).select_from(Memory).where(Memory.agent_id == agent.agent_id)) or 0
        return {
            "agent_id": agent.agent_id,
            "memories": int(memory_count),
            "stores": counts["store"],
            "searches": counts["search"],
            "deletes": counts["delete"],
            "plan_checkouts": counts["plan_checkout"],
        }

    @app.post("/plans/checkout")
    def plan_checkout(payload: PlanCheckoutRequest, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> JSONResponse:
        if payload.plan not in PLAN_PRICES_CENTS or payload.plan == "free":
            raise HTTPException(status_code=400, detail="invalid_paid_plan")
        record_usage(db, agent.agent_id, "plan_checkout")
        db.commit()
        description = f"Upgrade memory service plan to {payload.plan}"
        return JSONResponse(
            status_code=402,
            content=x402_requirements(PLAN_PRICES_CENTS[payload.plan], f"/plans/{payload.plan}", description),
        )

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> str:
        memories = list(db.scalars(select(Memory).where(Memory.agent_id == agent.agent_id).order_by(Memory.created_at.desc()).limit(20)))
        usage_data = usage(agent, db)
        items = "".join(f"<li><strong>{m.namespace}</strong>: {m.content}</li>" for m in memories) or "<li>No memories yet</li>"
        return f"""
        <html><head><title>Agent Memory Dashboard</title></head>
        <body><h1>{agent.name}</h1>
        <p>Stores: {usage_data['stores']} Searches: {usage_data['searches']} Deletes: {usage_data['deletes']}</p>
        <h2>Recent memories</h2><ul>{items}</ul></body></html>
        """

    return app


app = create_app()
