from __future__ import annotations

import difflib
import hashlib
import html
import json
import math
import os
import re
import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any

import httpx
import yaml
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
DEFAULT_PAY_TO = os.getenv("PAY_TO", "0x23bB05603A980C2915FC3B9D5D4a475993b666DE")
PLAN_PRICES_CENTS = {"starter": 4900, "pro": 14900, "enterprise": 49900}
VECTOR_DIMS = 64


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    agent_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    plan = Column(String, nullable=False, default="starter")
    api_key = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class TestSuite(Base):
    __tablename__ = "test_suites"

    suite_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    endpoint = Column(String, nullable=True)
    schedule_interval = Column(String, nullable=False, default="manual")
    definition_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)


class Run(Base):
    __tablename__ = "runs"

    run_id = Column(String, primary_key=True)
    suite_id = Column(String, ForeignKey("test_suites.suite_id"), nullable=False, index=True)
    agent_id = Column(String, nullable=False, index=True)
    trigger = Column(String, nullable=False)
    status = Column(String, nullable=False)
    total = Column(Integer, nullable=False, default=0)
    passed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    pass_rate = Column(Float, nullable=False, default=0.0)
    regression_count = Column(Integer, nullable=False, default=0)
    drift_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class CaseResult(Base):
    __tablename__ = "case_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.run_id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    expected_text = Column(Text, nullable=False)
    actual_text = Column(Text, nullable=False)
    passed = Column(Boolean, nullable=False)
    similarity_score = Column(Float, nullable=True)
    assertions_json = Column(Text, nullable=False)
    diff = Column(Text, nullable=False)


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    suite_id = Column(String, nullable=False, index=True)
    run_id = Column(String, nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    alert_type = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False)
    recipient = Column(String, nullable=False)
    status = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class AgentCreate(BaseModel):
    name: str
    plan: str = "starter"


class SuitePayload(BaseModel):
    name: str | None = None
    definition: dict[str, Any] | str


class PlanCheckoutRequest(BaseModel):
    plan: str = Field(pattern="^(starter|pro|enterprise)$")


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


def utcnow() -> datetime:
    return datetime.now(UTC)


def load_config(raw: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        loaded = yaml.safe_load(raw)
    if not isinstance(loaded, dict):
        raise HTTPException(status_code=400, detail="suite definition must be a YAML/JSON object")
    return loaded


def normalize_definition(raw: dict[str, Any] | str, override_name: str | None = None) -> dict[str, Any]:
    definition = load_config(raw)
    name = override_name or definition.get("name") or "Autonomous QA Suite"
    cases = definition.get("cases") or definition.get("tests") or []
    if not isinstance(cases, list) or not cases:
        raise HTTPException(status_code=400, detail="suite definition must include at least one case")

    normalized_cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise HTTPException(status_code=400, detail="each case must be an object")
        case = dict(case)
        case_id = str(case.get("id") or case.get("case_id") or f"case_{index}")
        prompt = case.get("input", case.get("prompt", ""))
        expected = case.get("expected", case.get("expected_output", ""))
        assertions = case.get("assertions")
        if assertions is None:
            assertion_type = str(case.get("assertion", "exact"))
            assertions = [{"type": assertion_type, "value": expected}]
        if not isinstance(assertions, list) or not assertions:
            raise HTTPException(status_code=400, detail=f"case {case_id} must include assertions")
        case["id"] = case_id
        case["input"] = str(prompt)
        case["expected"] = str(expected)
        case["assertions"] = assertions
        normalized_cases.append(case)

    schedule = definition.get("schedule") or {"interval": "manual"}
    if isinstance(schedule, str):
        schedule = {"interval": schedule}
    if not isinstance(schedule, dict):
        raise HTTPException(status_code=400, detail="schedule must be an object or interval string")

    alerts = definition.get("alerts") or {}
    if not isinstance(alerts, dict):
        raise HTTPException(status_code=400, detail="alerts must be an object")

    return {
        **definition,
        "name": str(name),
        "endpoint": definition.get("endpoint"),
        "method": str(definition.get("method", "POST")).upper(),
        "timeout_seconds": float(definition.get("timeout_seconds", 10)),
        "drift_threshold": float(definition.get("drift_threshold", 0.15)),
        "schedule": {"interval": str(schedule.get("interval", "manual"))},
        "alerts": alerts,
        "cases": normalized_cases,
    }


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def embed(text: str) -> list[float]:
    vector = [0.0] * VECTOR_DIMS
    for token in tokenize(text):
        idx = int(hashlib.sha256(token.encode()).hexdigest(), 16) % VECTOR_DIMS
        vector[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def make_diff(expected: str, actual: str) -> str:
    if not expected:
        return ""
    return "\n".join(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile="expected",
            tofile="actual",
            lineterm="",
        )
    )


def response_text(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "")
    if "json" in content_type:
        data = response.json()
        if isinstance(data, dict):
            for key in ("output", "response", "answer", "text", "content", "message"):
                value = data.get(key)
                if isinstance(value, str):
                    return value
                if isinstance(value, dict) and isinstance(value.get("content"), str):
                    return value["content"]
        return json.dumps(data, sort_keys=True)
    return response.text


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


def interval_delta(interval: str) -> timedelta | None:
    normalized = interval.strip().lower().replace("every_", "")
    if normalized in {"manual", "on_deploy", "deploy", "none"}:
        return None
    if normalized in {"hour", "hourly", "1h"}:
        return timedelta(hours=1)
    if normalized in {"day", "daily", "1d"}:
        return timedelta(days=1)
    if normalized.endswith("m") and normalized[:-1].isdigit():
        return timedelta(minutes=int(normalized[:-1]))
    if normalized.endswith("h") and normalized[:-1].isdigit():
        return timedelta(hours=int(normalized[:-1]))
    if normalized.endswith("d") and normalized[:-1].isdigit():
        return timedelta(days=int(normalized[:-1]))
    return None


def next_run_at(suite: TestSuite) -> str | None:
    delta = interval_delta(suite.schedule_interval)
    if delta is None:
        return None
    if suite.last_run_at is None:
        return utcnow().isoformat()
    return (suite.last_run_at + delta).isoformat()


def due_for_scheduler(suite: TestSuite) -> bool:
    delta = interval_delta(suite.schedule_interval)
    if delta is None:
        return False
    if suite.last_run_at is None:
        return True
    last = suite.last_run_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return utcnow() >= last + delta


def serialize_suite(suite: TestSuite) -> dict[str, Any]:
    definition = json.loads(suite.definition_json)
    return {
        "suite_id": suite.suite_id,
        "agent_id": suite.agent_id,
        "name": suite.name,
        "endpoint": suite.endpoint,
        "schedule_interval": suite.schedule_interval,
        "next_run_at": next_run_at(suite),
        "created_at": suite.created_at.isoformat(),
        "updated_at": suite.updated_at.isoformat(),
        "last_run_at": suite.last_run_at.isoformat() if suite.last_run_at else None,
        "case_count": len(definition.get("cases", [])),
        "definition": definition,
    }


def serialize_run(run: Run, results: list[CaseResult] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run.run_id,
        "suite_id": run.suite_id,
        "agent_id": run.agent_id,
        "trigger": run.trigger,
        "status": run.status,
        "total": run.total,
        "passed": run.passed,
        "failed": run.failed,
        "pass_rate": round(run.pass_rate, 4),
        "regression_count": run.regression_count,
        "drift_count": run.drift_count,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
    if results is not None:
        payload["results"] = [serialize_case_result(result) for result in results]
    return payload


def serialize_case_result(result: CaseResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "prompt": result.prompt,
        "expected_text": result.expected_text,
        "actual_text": result.actual_text,
        "passed": result.passed,
        "similarity_score": round(result.similarity_score, 4) if result.similarity_score is not None else None,
        "assertions": json.loads(result.assertions_json),
        "diff": result.diff,
    }


def serialize_alert(alert: Alert) -> dict[str, Any]:
    return {
        "alert_id": alert.alert_id,
        "suite_id": alert.suite_id,
        "run_id": alert.run_id,
        "case_id": alert.case_id,
        "alert_type": alert.alert_type,
        "channel": alert.channel,
        "recipient": alert.recipient,
        "status": alert.status,
        "message": alert.message,
        "created_at": alert.created_at.isoformat(),
    }


def normalize_database_url(database_url: str | None = None) -> str:
    if database_url is None:
        database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_url = "sqlite:////tmp/autonomous_qa.db" if os.getenv("VERCEL") else "sqlite:///autonomous_qa.db"
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(
        title="Autonomous QA Agent",
        description="Continuously runs structured YAML/JSON test suites against AI agent endpoints and reports regressions.",
        version="0.1.0",
    )
    database_url = normalize_database_url(database_url)
    SessionLocal = make_session_factory(database_url)
    app.state.database_url = database_url

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

    def get_suite_for_agent(db: Session, agent: Agent, suite_id: str) -> TestSuite:
        suite = db.scalar(select(TestSuite).where(TestSuite.suite_id == suite_id, TestSuite.agent_id == agent.agent_id))
        if not suite:
            raise HTTPException(status_code=404, detail="suite_not_found")
        return suite

    def call_target(definition: dict[str, Any], case: dict[str, Any], prior_run_count: int) -> str:
        if "mock_responses" in case:
            responses = case["mock_responses"]
            if isinstance(responses, list) and responses:
                return str(responses[min(prior_run_count, len(responses) - 1)])
        if "mock_response" in case:
            return str(case["mock_response"])

        endpoint = case.get("endpoint") or definition.get("endpoint")
        if not endpoint:
            raise RuntimeError("no endpoint configured and no mock_response provided")
        method = str(case.get("method") or definition.get("method") or "POST").upper()
        timeout = float(case.get("timeout_seconds") or definition.get("timeout_seconds") or 10)
        headers = dict(definition.get("headers") or {}) | dict(case.get("headers") or {})
        payload = case.get("payload") or {"prompt": case.get("input", "")}
        with httpx.Client(timeout=timeout) as client:
            if method == "GET":
                response = client.get(endpoint, params=payload, headers=headers)
            else:
                response = client.request(method, endpoint, json=payload, headers=headers)
            response.raise_for_status()
            return response_text(response)

    def evaluate_assertions(case: dict[str, Any], actual: str) -> tuple[bool, list[dict[str, Any]], float | None]:
        expected = str(case.get("expected", ""))
        assertion_results: list[dict[str, Any]] = []
        similarity_score: float | None = None
        for assertion in case.get("assertions", []):
            if not isinstance(assertion, dict):
                assertion = {"type": "contains", "value": str(assertion)}
            assertion_type = str(assertion.get("type", "contains")).lower()
            value = str(assertion.get("value", assertion.get("expected", expected)))
            passed = False
            detail: dict[str, Any] = {"type": assertion_type, "value": value}
            if assertion_type == "exact":
                passed = actual.strip() == value.strip()
            elif assertion_type == "contains":
                passed = value.lower() in actual.lower() if assertion.get("case_insensitive", True) else value in actual
            elif assertion_type == "regex":
                pattern = str(assertion.get("pattern", value))
                detail["pattern"] = pattern
                passed = re.search(pattern, actual, flags=re.IGNORECASE if assertion.get("case_insensitive", False) else 0) is not None
            elif assertion_type in {"similarity", "semantic_similarity"}:
                threshold = float(assertion.get("threshold", 0.8))
                score = cosine(embed(actual), embed(value))
                similarity_score = score if similarity_score is None else max(similarity_score, score)
                detail["threshold"] = threshold
                detail["score"] = round(score, 4)
                passed = score >= threshold
            else:
                detail["error"] = "unknown assertion type"
            detail["passed"] = passed
            assertion_results.append(detail)
        return all(item["passed"] for item in assertion_results), assertion_results, similarity_score

    def deliver_email(recipient: str, subject: str, body: str) -> str:
        host = os.getenv("SMTP_HOST")
        if not host:
            return "captured:no_smtp_configured"
        message = EmailMessage()
        sender = os.getenv("SMTP_FROM", "qa-agent@example.local")
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        try:
            port = int(os.getenv("SMTP_PORT", "587" if os.getenv("SMTP_TLS", "true").lower() == "true" else "25"))
            with smtplib.SMTP(host, port, timeout=8) as smtp:
                if os.getenv("SMTP_TLS", "true").lower() == "true":
                    smtp.starttls()
                if os.getenv("SMTP_USERNAME") and os.getenv("SMTP_PASSWORD"):
                    smtp.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD"))
                smtp.send_message(message)
            return "sent"
        except Exception as exc:  # pragma: no cover - depends on external SMTP
            return f"failed:{type(exc).__name__}"

    def deliver_webhook(recipient: str, payload: dict[str, Any]) -> str:
        if not recipient.startswith(("http://", "https://")):
            return "captured:non_http_webhook"
        try:
            with httpx.Client(timeout=8) as client:
                response = client.post(recipient, json=payload)
            return "sent" if response.status_code < 400 else f"failed:http_{response.status_code}"
        except Exception as exc:  # pragma: no cover - depends on external webhook
            return f"failed:{type(exc).__name__}"

    def create_alerts(
        db: Session,
        agent: Agent,
        suite: TestSuite,
        run: Run,
        case_id: str,
        alert_type: str,
        definition: dict[str, Any],
        message: str,
    ) -> int:
        alert_config = definition.get("alerts") or {}
        channels: list[tuple[str, str]] = []
        for email in alert_config.get("emails", []) or []:
            channels.append(("email", str(email)))
        for webhook in alert_config.get("webhooks", []) or []:
            channels.append(("webhook", str(webhook)))
        if not channels:
            channels.append(("dashboard", "internal"))

        count = 0
        for channel, recipient in channels:
            payload = {
                "suite_id": suite.suite_id,
                "run_id": run.run_id,
                "case_id": case_id,
                "alert_type": alert_type,
                "message": message,
            }
            if channel == "email":
                status = deliver_email(recipient, f"QA {alert_type}: {suite.name}", message)
            elif channel == "webhook":
                status = deliver_webhook(recipient, payload)
            else:
                status = "captured:dashboard"
            db.add(
                Alert(
                    alert_id="alt_" + secrets.token_hex(8),
                    agent_id=agent.agent_id,
                    suite_id=suite.suite_id,
                    run_id=run.run_id,
                    case_id=case_id,
                    alert_type=alert_type,
                    channel=channel,
                    recipient=recipient,
                    status=status,
                    message=message,
                    created_at=utcnow(),
                )
            )
            count += 1
        return count

    def execute_suite(db: Session, agent: Agent, suite: TestSuite, trigger: str) -> Run:
        definition = json.loads(suite.definition_json)
        prior_run_count = int(db.scalar(select(func.count()).select_from(Run).where(Run.suite_id == suite.suite_id)) or 0)
        run = Run(
            run_id="run_" + secrets.token_hex(8),
            suite_id=suite.suite_id,
            agent_id=agent.agent_id,
            trigger=trigger,
            status="running",
            started_at=utcnow(),
            total=len(definition["cases"]),
        )
        db.add(run)
        db.flush()

        passed_count = 0
        regression_count = 0
        drift_count = 0
        drift_threshold = float(definition.get("drift_threshold", 0.15))

        for case in definition["cases"]:
            case_id = str(case["id"])
            expected = str(case.get("expected", ""))
            try:
                actual = call_target(definition, case, prior_run_count)
            except Exception as exc:
                actual = f"ERROR: {type(exc).__name__}: {exc}"
            passed, assertions, similarity_score = evaluate_assertions(case, actual)
            if passed:
                passed_count += 1

            previous = db.scalar(
                select(CaseResult)
                .join(Run, CaseResult.run_id == Run.run_id)
                .where(Run.suite_id == suite.suite_id, CaseResult.case_id == case_id, Run.run_id != run.run_id)
                .order_by(Run.started_at.desc(), CaseResult.id.desc())
                .limit(1)
            )
            is_regression = bool(previous and previous.passed and not passed)
            is_drift = bool(
                previous
                and previous.similarity_score is not None
                and similarity_score is not None
                and previous.similarity_score - similarity_score >= drift_threshold
            )
            if is_regression:
                regression_count += 1
                create_alerts(
                    db,
                    agent,
                    suite,
                    run,
                    case_id,
                    "regression",
                    definition,
                    f"Previously passing case '{case_id}' failed in run {run.run_id}.",
                )
            if is_drift:
                drift_count += 1
                create_alerts(
                    db,
                    agent,
                    suite,
                    run,
                    case_id,
                    "drift",
                    definition,
                    f"Similarity for case '{case_id}' dropped by at least {drift_threshold} in run {run.run_id}.",
                )

            db.add(
                CaseResult(
                    run_id=run.run_id,
                    case_id=case_id,
                    prompt=str(case.get("input", "")),
                    expected_text=expected,
                    actual_text=actual,
                    passed=passed,
                    similarity_score=similarity_score,
                    assertions_json=json.dumps(assertions, sort_keys=True),
                    diff=make_diff(expected, actual),
                )
            )

        run.passed = passed_count
        run.failed = run.total - passed_count
        run.pass_rate = passed_count / run.total if run.total else 0.0
        run.regression_count = regression_count
        run.drift_count = drift_count
        run.status = "passed" if run.failed == 0 else "failed"
        run.finished_at = utcnow()
        suite.last_run_at = run.finished_at
        suite.updated_at = run.finished_at
        db.commit()
        db.refresh(run)
        return run

    @app.get("/health")
    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "autonomous-qa-agent", "version": app.version}

    @app.get("/readyz")
    def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
        db.execute(select(1)).scalar_one()
        return {"status": "ready", "database": "ok"}

    @app.post("/agents", status_code=201)
    def create_agent(payload: AgentCreate, db: Session = Depends(get_db)) -> dict[str, str]:
        if payload.plan not in {"starter", "pro", "enterprise"}:
            raise HTTPException(status_code=400, detail="unknown plan")
        agent = Agent(
            agent_id="agt_" + secrets.token_hex(8),
            name=payload.name,
            plan=payload.plan,
            api_key="ak_" + secrets.token_urlsafe(24),
            created_at=utcnow(),
        )
        db.add(agent)
        db.commit()
        return {"agent_id": agent.agent_id, "name": agent.name, "plan": agent.plan, "api_key": agent.api_key}

    @app.post("/suites", status_code=201)
    def create_suite(payload: SuitePayload, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        definition = normalize_definition(payload.definition, payload.name)
        now = utcnow()
        suite = TestSuite(
            suite_id="sui_" + secrets.token_hex(8),
            agent_id=agent.agent_id,
            name=definition["name"],
            endpoint=definition.get("endpoint"),
            schedule_interval=definition["schedule"]["interval"],
            definition_json=json.dumps(definition, sort_keys=True),
            created_at=now,
            updated_at=now,
        )
        db.add(suite)
        db.commit()
        db.refresh(suite)
        return serialize_suite(suite)

    @app.get("/suites")
    def list_suites(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        suites = list(db.scalars(select(TestSuite).where(TestSuite.agent_id == agent.agent_id).order_by(TestSuite.created_at.desc())))
        return {"suites": [serialize_suite(suite) for suite in suites]}

    @app.put("/suites/{suite_id}")
    def update_suite(suite_id: str, payload: SuitePayload, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        suite = get_suite_for_agent(db, agent, suite_id)
        definition = normalize_definition(payload.definition, payload.name)
        suite.name = definition["name"]
        suite.endpoint = definition.get("endpoint")
        suite.schedule_interval = definition["schedule"]["interval"]
        suite.definition_json = json.dumps(definition, sort_keys=True)
        suite.updated_at = utcnow()
        db.commit()
        db.refresh(suite)
        return serialize_suite(suite)

    @app.post("/suites/{suite_id}/run", status_code=201)
    def run_suite(suite_id: str, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        suite = get_suite_for_agent(db, agent, suite_id)
        run = execute_suite(db, agent, suite, trigger="manual")
        results = list(db.scalars(select(CaseResult).where(CaseResult.run_id == run.run_id).order_by(CaseResult.id)))
        return serialize_run(run, results)

    @app.post("/webhooks/deploy/{suite_id}", status_code=201)
    def deploy_webhook_trigger(suite_id: str, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        suite = get_suite_for_agent(db, agent, suite_id)
        run = execute_suite(db, agent, suite, trigger="deploy_webhook")
        return serialize_run(run)

    @app.post("/scheduler/tick")
    def scheduler_tick(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        suites = list(db.scalars(select(TestSuite).where(TestSuite.agent_id == agent.agent_id)))
        runs: list[dict[str, Any]] = []
        for suite in suites:
            if due_for_scheduler(suite):
                runs.append(serialize_run(execute_suite(db, agent, suite, trigger="scheduler")))
        return {"triggered": len(runs), "runs": runs}

    @app.get("/schedules")
    def schedules(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        suites = list(db.scalars(select(TestSuite).where(TestSuite.agent_id == agent.agent_id).order_by(TestSuite.created_at.desc())))
        return {
            "schedules": [
                {
                    "suite_id": suite.suite_id,
                    "name": suite.name,
                    "interval": suite.schedule_interval,
                    "last_run_at": suite.last_run_at.isoformat() if suite.last_run_at else None,
                    "next_run_at": next_run_at(suite),
                    "due": due_for_scheduler(suite),
                }
                for suite in suites
            ]
        }

    @app.get("/runs")
    def list_runs(suite_id: str | None = None, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        query = select(Run).where(Run.agent_id == agent.agent_id)
        if suite_id:
            query = query.where(Run.suite_id == suite_id)
        runs = list(db.scalars(query.order_by(Run.started_at.desc())))
        return {"runs": [serialize_run(run) for run in runs]}

    @app.get("/runs/{run_id}")
    def get_run(run_id: str, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        run = db.scalar(select(Run).where(Run.run_id == run_id, Run.agent_id == agent.agent_id))
        if not run:
            raise HTTPException(status_code=404, detail="run_not_found")
        results = list(db.scalars(select(CaseResult).where(CaseResult.run_id == run.run_id).order_by(CaseResult.id)))
        return serialize_run(run, results)

    @app.get("/alerts")
    def list_alerts(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        alerts = list(db.scalars(select(Alert).where(Alert.agent_id == agent.agent_id).order_by(Alert.created_at.desc())))
        return {"alerts": [serialize_alert(alert) for alert in alerts]}

    @app.get("/reports/summary")
    def reports_summary(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> dict[str, Any]:
        suites = list(db.scalars(select(TestSuite).where(TestSuite.agent_id == agent.agent_id)))
        rows: list[dict[str, Any]] = []
        for suite in suites:
            runs = list(db.scalars(select(Run).where(Run.suite_id == suite.suite_id).order_by(Run.started_at.asc())))
            rows.append(
                {
                    "suite_id": suite.suite_id,
                    "name": suite.name,
                    "runs": len(runs),
                    "latest_pass_rate": round(runs[-1].pass_rate, 4) if runs else None,
                    "trend": [round(run.pass_rate, 4) for run in runs[-10:]],
                    "regressions": sum(run.regression_count for run in runs),
                    "drift_alerts": sum(run.drift_count for run in runs),
                }
            )
        return {"suites": rows}

    @app.post("/plans/checkout")
    def plan_checkout(payload: PlanCheckoutRequest, agent: Agent = Depends(current_agent)) -> JSONResponse:
        description = f"Upgrade Autonomous QA Agent to {payload.plan} plan"
        return JSONResponse(
            status_code=402,
            content=x402_requirements(PLAN_PRICES_CENTS[payload.plan], f"/plans/{payload.plan}", description),
        )

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)) -> str:
        suites = list(db.scalars(select(TestSuite).where(TestSuite.agent_id == agent.agent_id).order_by(TestSuite.created_at.desc())))
        runs = list(db.scalars(select(Run).where(Run.agent_id == agent.agent_id).order_by(Run.started_at.desc()).limit(10)))
        suite_rows = "".join(
            f"<tr><td>{html.escape(s.name)}</td><td>{html.escape(s.schedule_interval)}</td><td>{len(json.loads(s.definition_json).get('cases', []))}</td><td>{html.escape(str(next_run_at(s)))}</td></tr>"
            for s in suites
        ) or "<tr><td colspan='4'>No suites yet</td></tr>"
        run_rows = "".join(
            f"<tr><td>{html.escape(r.run_id)}</td><td>{html.escape(r.status)}</td><td>{r.passed}/{r.total}</td><td>{r.pass_rate:.0%}</td><td>{r.regression_count}</td><td>{r.drift_count}</td></tr>"
            for r in runs
        ) or "<tr><td colspan='6'>No runs yet</td></tr>"
        total_runs = len(runs)
        latest_rate = f"{runs[0].pass_rate:.0%}" if runs else "n/a"
        return f"""
        <html><head><title>Autonomous QA Agent Dashboard</title>
        <style>body{{font-family:Arial,sans-serif;margin:2rem}}table{{border-collapse:collapse;width:100%;margin:1rem 0}}td,th{{border:1px solid #ddd;padding:.5rem}}th{{background:#f4f4f4}}</style></head>
        <body><h1>Autonomous QA Agent</h1><p>Agent: {html.escape(agent.name)} | Recent runs: {total_runs} | Latest pass rate: {latest_rate}</p>
        <h2>Suites</h2><table><tr><th>Name</th><th>Schedule</th><th>Cases</th><th>Next run</th></tr>{suite_rows}</table>
        <h2>Recent run history</h2><table><tr><th>Run</th><th>Status</th><th>Passed</th><th>Pass rate</th><th>Regressions</th><th>Drift</th></tr>{run_rows}</table>
        </body></html>
        """

    return app


app = create_app()
