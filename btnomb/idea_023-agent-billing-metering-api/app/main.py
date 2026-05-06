from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, create_engine, select, func
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
DEFAULT_PAY_TO = "0x9c768177521C9A832B0f8567265ef02E89D0282e"
PLAN_PRICES_CENTS = {"free": 0, "starter": 2900, "pro": 9900, "enterprise": 39900}


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"
    agent_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    plan = Column(String, nullable=False)
    api_key = Column(String, nullable=False, unique=True, index=True)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    spend_limit_cents = Column(Integer, nullable=True)


class MeterEvent(Base):
    __tablename__ = "meter_events"
    event_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    unit_price_cents = Column(Integer, nullable=False)
    cost_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"
    invoice_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    period_start = Column(String, nullable=False)
    period_end = Column(String, nullable=False)
    total_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class AgentCreate(BaseModel):
    name: str
    plan: str = "free"


class CustomerCreate(BaseModel):
    customer_id: str
    spend_limit_cents: int | None = None


class MeterEventCreate(BaseModel):
    customer_id: str
    event_type: str
    quantity: int = Field(gt=0)
    unit_price_cents: int = Field(ge=0)


class GateRequest(BaseModel):
    customer_id: str
    resource: str
    amount_cents: int = Field(gt=0)


class InvoiceRequest(BaseModel):
    customer_id: str
    period_start: str
    period_end: str


class PlanCheckoutRequest(BaseModel):
    plan: str


def make_session_factory(database_url: str):
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    if database_url == "sqlite:///:memory:":
        engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def model_to_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, Agent):
        return {"agent_id": obj.agent_id, "name": obj.name, "plan": obj.plan, "api_key": obj.api_key}
    if isinstance(obj, Customer):
        return {"agent_id": obj.agent_id, "customer_id": obj.customer_id, "spend_limit_cents": obj.spend_limit_cents}
    if isinstance(obj, MeterEvent):
        return {
            "event_id": obj.event_id,
            "agent_id": obj.agent_id,
            "customer_id": obj.customer_id,
            "event_type": obj.event_type,
            "quantity": obj.quantity,
            "unit_price_cents": obj.unit_price_cents,
            "cost_cents": obj.cost_cents,
            "created_at": obj.created_at.isoformat(),
        }
    raise TypeError(f"Unsupported model: {type(obj)!r}")


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
        title="Agent Billing & Metering API",
        description="Drop-in usage metering, x402 payment gating, spending limits, and invoice generation for AI agents.",
        version="0.1.0",
    )
    database_url = database_url or "sqlite:///agent_billing.db"
    SessionLocal = make_session_factory(database_url)
    app.state.database_url = database_url

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def current_agent(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        db: Session = Depends(get_db),
    ) -> Agent:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="missing_or_invalid_api_key")
        agent = db.scalar(select(Agent).where(Agent.api_key == x_api_key))
        if not agent:
            raise HTTPException(status_code=401, detail="missing_or_invalid_api_key")
        return agent

    def find_customer(db: Session, agent_id: str, customer_id: str) -> Customer | None:
        return db.scalar(select(Customer).where(Customer.agent_id == agent_id, Customer.customer_id == customer_id))

    def customer_spend(db: Session, agent_id: str, customer_id: str) -> int:
        value = db.scalar(select(func.coalesce(func.sum(MeterEvent.cost_cents), 0)).where(MeterEvent.agent_id == agent_id, MeterEvent.customer_id == customer_id))
        return int(value or 0)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/agents", status_code=201)
    def create_agent(payload: AgentCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        if payload.plan not in PLAN_PRICES_CENTS:
            raise HTTPException(status_code=400, detail="unknown plan")
        agent = Agent(
            agent_id="agt_" + secrets.token_hex(8),
            name=payload.name,
            plan=payload.plan,
            api_key="ak_" + secrets.token_urlsafe(24),
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return model_to_dict(agent)

    @app.post("/customers", status_code=201)
    def create_customer(payload: CustomerCreate, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        existing = find_customer(db, agent.agent_id, payload.customer_id)
        if existing:
            existing.spend_limit_cents = payload.spend_limit_cents
            db.commit()
            db.refresh(existing)
            return model_to_dict(existing)
        customer = Customer(agent_id=agent.agent_id, customer_id=payload.customer_id, spend_limit_cents=payload.spend_limit_cents)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return model_to_dict(customer)

    @app.post("/meter/event", status_code=201, response_model=None)
    def meter_event(payload: MeterEventCreate, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> Any:
        customer = find_customer(db, agent.agent_id, payload.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="customer_not_found")
        cost_cents = payload.quantity * payload.unit_price_cents
        current = customer_spend(db, agent.agent_id, payload.customer_id)
        if customer.spend_limit_cents is not None and current + cost_cents > customer.spend_limit_cents:
            return JSONResponse(
                status_code=402,
                content={
                    "error": "spending_limit_exceeded",
                    "current_spend_cents": current,
                    "attempted_cost_cents": cost_cents,
                    "spend_limit_cents": customer.spend_limit_cents,
                },
            )
        event = MeterEvent(
            event_id="evt_" + secrets.token_hex(8),
            agent_id=agent.agent_id,
            customer_id=payload.customer_id,
            event_type=payload.event_type,
            quantity=payload.quantity,
            unit_price_cents=payload.unit_price_cents,
            cost_cents=cost_cents,
            created_at=datetime.now(UTC),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return model_to_dict(event)

    @app.get("/meter/usage")
    def meter_usage(customer_id: str | None = None, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        query = select(MeterEvent).where(MeterEvent.agent_id == agent.agent_id)
        if customer_id:
            query = query.where(MeterEvent.customer_id == customer_id)
        events = list(db.scalars(query))
        return {
            "agent_id": agent.agent_id,
            "customer_id": customer_id,
            "events": len(events),
            "total_quantity": sum(e.quantity for e in events),
            "total_cost_cents": sum(e.cost_cents for e in events),
        }

    @app.post("/gate", response_model=None)
    def gate(
        payload: GateRequest,
        agent: Agent = Depends(current_agent),
        db: Session = Depends(get_db),
        x_payment: str | None = Header(default=None, alias="X-PAYMENT"),
    ) -> Any:
        customer = find_customer(db, agent.agent_id, payload.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="customer_not_found")
        current = customer_spend(db, agent.agent_id, payload.customer_id)
        if customer.spend_limit_cents is not None and current + payload.amount_cents > customer.spend_limit_cents:
            return JSONResponse(status_code=402, content={"error": "spending_limit_exceeded", "current_spend_cents": current, "attempted_cost_cents": payload.amount_cents})
        if not x_payment:
            return JSONResponse(status_code=402, content=x402_requirements(payload.amount_cents, payload.resource, f"Pay to access {payload.resource}"))
        event = MeterEvent(
            event_id="evt_" + secrets.token_hex(8),
            agent_id=agent.agent_id,
            customer_id=payload.customer_id,
            event_type=f"gate:{payload.resource}",
            quantity=1,
            unit_price_cents=payload.amount_cents,
            cost_cents=payload.amount_cents,
            created_at=datetime.now(UTC),
        )
        db.add(event)
        db.commit()
        return {"status": "paid", "resource": payload.resource, "customer_id": payload.customer_id, "event_id": event.event_id}

    @app.post("/invoice/generate", status_code=201)
    def invoice(payload: InvoiceRequest, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        events = list(db.scalars(select(MeterEvent).where(MeterEvent.agent_id == agent.agent_id, MeterEvent.customer_id == payload.customer_id)))
        grouped: dict[str, dict[str, int | str]] = defaultdict(lambda: {"event_type": "", "quantity": 0, "total_cents": 0})
        for event in events:
            item = grouped[event.event_type]
            item["event_type"] = event.event_type
            item["quantity"] = int(item["quantity"]) + event.quantity
            item["total_cents"] = int(item["total_cents"]) + event.cost_cents
        total = sum(e.cost_cents for e in events)
        invoice_row = Invoice(
            invoice_id="inv_" + secrets.token_hex(8),
            agent_id=agent.agent_id,
            customer_id=payload.customer_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            total_cents=total,
            created_at=datetime.now(UTC),
        )
        db.add(invoice_row)
        db.commit()
        return {
            "invoice_id": invoice_row.invoice_id,
            "agent_id": agent.agent_id,
            "customer_id": payload.customer_id,
            "period_start": payload.period_start,
            "period_end": payload.period_end,
            "line_items": list(grouped.values()),
            "total_cents": total,
        }

    @app.post("/plans/checkout")
    def plan_checkout(payload: PlanCheckoutRequest, agent: Agent = Depends(current_agent)) -> JSONResponse:
        if payload.plan not in PLAN_PRICES_CENTS or payload.plan == "free":
            raise HTTPException(status_code=400, detail="invalid_paid_plan")
        description = f"Upgrade agent billing plan to {payload.plan}"
        return JSONResponse(status_code=402, content=x402_requirements(PLAN_PRICES_CENTS[payload.plan], f"/plans/{payload.plan}", description) | {"description": description})

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> str:
        events = list(db.scalars(select(MeterEvent).where(MeterEvent.agent_id == agent.agent_id)))
        total = sum(e.cost_cents for e in events)
        customers = sorted({e.customer_id for e in events})
        rows = "".join(f"<li>{cid}</li>" for cid in customers) or "<li>No customers yet</li>"
        return f"""
        <html><head><title>Agent Billing Dashboard</title></head>
        <body><h1>{agent.name}</h1><p>Plan: {agent.plan}</p>
        <p>Total revenue: ${total / 100:.2f}</p><p>Events: {len(events)}</p>
        <h2>Customers</h2><ul>{rows}</ul></body></html>
        """

    return app


app = create_app()
