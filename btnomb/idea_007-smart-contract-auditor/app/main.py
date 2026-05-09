from __future__ import annotations

import hashlib
import html
import json
import os
import re
import secrets
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

DEFAULT_API_KEY = os.getenv("AUDITOR_API_KEY", "dev-audit-key")
DEFAULT_HISTORY = "/tmp/audit_history.jsonl" if os.getenv("VERCEL") else "audit_history.jsonl"
HISTORY_PATH = Path(os.getenv("AUDIT_HISTORY_PATH", DEFAULT_HISTORY))
SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Informational": 4}
PRICE_SMALL_CENTS = 200
PRICE_LARGE_CENTS = 500
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
DEFAULT_PAY_TO = os.getenv("X402_PAY_TO", "0x0000000000000000000000000000000000000000")


class SourceFile(BaseModel):
    path: str = Field(..., examples=["contracts/Token.sol"])
    content: str


class AuditRequest(BaseModel):
    contract_name: str | None = None
    source: str | None = Field(default=None, description="Single-file Solidity source")
    files: list[SourceFile] = Field(default_factory=list, description="Optional multi-file Solidity project")
    preview: bool = Field(False, description="Return severity summary only")
    standards: list[str] = Field(default_factory=lambda: ["ERC-20", "ERC-721", "ERC-1155"])
    use_mock_models: bool = Field(True, description="Use deterministic mock multi-model pipeline")


class Finding(BaseModel):
    id: str
    title: str
    severity: Literal["Critical", "High", "Medium", "Low", "Informational"]
    swc_id: str | None = None
    file: str
    line: int
    code: str
    description: str
    attack_vector: str
    remediation: str
    fixed_snippet: str
    source: str


class ModelReport(BaseModel):
    provider: str
    summary: str
    findings: list[Finding]


class AuditReport(BaseModel):
    audit_id: str
    contract_name: str
    created_at: str
    pricing: dict[str, Any]
    preview: bool
    severity_summary: dict[str, int]
    findings: list[Finding]
    gas_optimizations: list[dict[str, Any]]
    compliance: dict[str, Any]
    model_reports: list[ModelReport]
    synthesized_summary: str
    markdown_report: str | None = None
    pdf_report: str | None = Field(default=None, description="PDF-ish plain text report suitable for saving as .pdf/.txt in MVP")


def create_app(history_path: Path | str | None = None) -> FastAPI:
    app = FastAPI(
        title="Smart Contract Auditor MVP",
        description="API-key protected Solidity auditing service with static heuristics and mockable multi-model report synthesis.",
        version="0.1.0",
    )
    app.state.history_path = Path(history_path) if history_path is not None else HISTORY_PATH
    app.state.started_at = datetime.now(UTC)

    def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
        if not x_api_key or not secrets.compare_digest(x_api_key, DEFAULT_API_KEY):
            raise HTTPException(status_code=401, detail="missing_or_invalid_api_key")
        return x_api_key

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def readiness() -> dict[str, Any]:
        history_path = Path(app.state.history_path)
        history_dir = history_path.parent if str(history_path.parent) else Path(".")
        checks: dict[str, Any] = {
            "history_path": str(history_path),
            "history_directory_writable": os.access(history_dir if history_dir.exists() else Path("."), os.W_OK),
            "api_key_configured": bool(DEFAULT_API_KEY) and DEFAULT_API_KEY != "dev-audit-key" and DEFAULT_API_KEY != "change-me",
            "x402_pay_to_configured": DEFAULT_PAY_TO != "0x0000000000000000000000000000000000000000",
            "pricing_configured": {"small_audit_cents": PRICE_SMALL_CENTS, "large_audit_cents": PRICE_LARGE_CENTS, "asset": BASE_USDC, "network": "base"},
            "report_formats": ["json", "markdown", "html", "pdf-ish"],
            "started_at": app.state.started_at.isoformat(),
        }
        checks["serving"] = True
        production_ready = bool(checks["history_directory_writable"] and checks["api_key_configured"] and checks["x402_pay_to_configured"])
        checks["production_ready"] = production_ready
        checks["warnings"] = [] if production_ready else [
            "Set AUDITOR_API_KEY to a non-demo secret and X402_PAY_TO to the payout wallet for production deployment."
        ]
        return {"status": "ready", "checks": checks}

    @app.post("/audit", response_model=None)
    def audit_contract(
        payload: AuditRequest,
        _: str = Depends(require_api_key),
        x_payment: str | None = Header(default=None, alias="X-PAYMENT"),
    ) -> Any:
        project = normalize_project(payload)
        if not project:
            raise HTTPException(status_code=400, detail="source_or_files_required")
        line_count = sum(len(content.splitlines()) for content in project.values())
        price_cents = 0 if payload.preview else (PRICE_SMALL_CENTS if line_count < 500 else PRICE_LARGE_CENTS)
        if price_cents and not x_payment:
            return JSONResponse(
                status_code=402,
                content=x402_requirements(price_cents, "/audit", f"Smart contract audit for {payload.contract_name or 'Solidity project'}"),
            )
        report = build_report(payload, project, line_count, price_cents)
        append_history(app.state.history_path, report)
        return report.model_dump()

    @app.get("/reports/{audit_id}.md")
    def markdown_report(audit_id: str, _: str = Depends(require_api_key)) -> PlainTextResponse:
        report = find_history(app.state.history_path, audit_id)
        if not report:
            raise HTTPException(status_code=404, detail="audit_not_found")
        return PlainTextResponse(report.get("markdown_report") or render_markdown_from_dict(report), media_type="text/markdown")

    @app.get("/reports/{audit_id}.pdf")
    def pdf_report(audit_id: str, _: str = Depends(require_api_key)) -> PlainTextResponse:
        report = find_history(app.state.history_path, audit_id)
        if not report:
            raise HTTPException(status_code=404, detail="audit_not_found")
        return PlainTextResponse(report.get("pdf_report") or render_pdfish_from_dict(report), media_type="application/pdf")

    @app.get("/reports/{audit_id}.html", response_class=HTMLResponse)
    def html_report(audit_id: str, _: str = Depends(require_api_key)) -> str:
        report = find_history(app.state.history_path, audit_id)
        if not report:
            raise HTTPException(status_code=404, detail="audit_not_found")
        return render_html_from_dict(report)

    @app.get("/reports/{audit_id}")
    def get_report(audit_id: str, _: str = Depends(require_api_key)) -> dict[str, Any]:
        report = find_history(app.state.history_path, audit_id)
        if not report:
            raise HTTPException(status_code=404, detail="audit_not_found")
        return report

    @app.get("/history")
    def history(_: str = Depends(require_api_key), limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
        rows = read_history(app.state.history_path)[-limit:]
        return {
            "audits": [
                {
                    "audit_id": row["audit_id"],
                    "contract_name": row["contract_name"],
                    "created_at": row["created_at"],
                    "severity_summary": row["severity_summary"],
                    "finding_count": len(row.get("findings", [])),
                    "preview": row.get("preview", False),
                }
                for row in reversed(rows)
            ]
        }

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(_: str = Depends(require_api_key)) -> str:
        rows = read_history(app.state.history_path)
        total = len(rows)
        finding_total = sum(len(row.get("findings", [])) for row in rows)
        severities = Counter()
        for row in rows:
            severities.update(row.get("severity_summary", {}))
        items = "".join(
            f"<tr><td>{html.escape(row['audit_id'])}</td><td>{html.escape(row['contract_name'])}</td><td>{row['created_at']}</td><td>{len(row.get('findings', []))}</td><td>{html.escape(json.dumps(row.get('severity_summary', {})))}</td></tr>"
            for row in reversed(rows[-25:])
        ) or "<tr><td colspan='5'>No audits yet</td></tr>"
        return f"""
        <html><head><title>Smart Contract Auditor Dashboard</title>
        <style>body{{font-family:Arial;margin:2rem}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:.45rem}}.stat{{display:inline-block;margin-right:1rem}}</style></head>
        <body><h1>Smart Contract Auditor</h1>
        <p class='stat'><b>Audits:</b> {total}</p><p class='stat'><b>Findings:</b> {finding_total}</p>
        <p class='stat'><b>Severity totals:</b> {html.escape(json.dumps(dict(severities)))}</p>
        <h2>Recent audits</h2><table><thead><tr><th>ID</th><th>Contract</th><th>Created</th><th>Findings</th><th>Severity</th></tr></thead><tbody>{items}</tbody></table>
        </body></html>
        """

    return app



def normalize_project(payload: AuditRequest) -> dict[str, str]:
    project: dict[str, str] = {}
    if payload.source:
        project["Contract.sol"] = payload.source
    for file in payload.files:
        project[file.path] = file.content
    return {path: resolve_imports(path, content, project) for path, content in project.items()}


def resolve_imports(path: str, content: str, project: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        imported = match.group(1) or match.group(2) or ""
        candidates = [imported, imported.lstrip("./"), str(Path(path).parent / imported)]
        for candidate in candidates:
            normalized = str(Path(candidate))
            if candidate in project:
                return f"// inlined import {candidate}\n{project[candidate]}"
            if normalized in project:
                return f"// inlined import {normalized}\n{project[normalized]}"
        return match.group(0) + " // unresolved import"

    return re.sub(r'import\s+(?:[^";]+from\s+)?["\']([^"\']+)["\'];|import\s+["\']([^"\']+)["\'];', repl, content)


def build_report(payload: AuditRequest, project: dict[str, str], line_count: int, price_cents: int) -> AuditReport:
    heuristic_findings = analyze_project(project)
    gas = gas_optimizations(project)
    compliance = compliance_checks(project, payload.standards)
    report_a = StaticModelProvider("heuristic-model-a", focus="exploitability").analyze(project, heuristic_findings)
    report_b = StaticModelProvider("heuristic-model-b", focus="remediation").analyze(project, heuristic_findings)
    findings = synthesize_findings([report_a, report_b])
    if payload.preview:
        findings_for_response: list[Finding] = []
        model_reports = [ModelReport(provider=r.provider, summary=r.summary, findings=[]) for r in [report_a, report_b]]
    else:
        findings_for_response = findings
        model_reports = [report_a, report_b]
    severity_summary = summarize(findings)
    audit_id = "aud_" + hashlib.sha256((json.dumps(project, sort_keys=True) + datetime.now(UTC).isoformat()).encode()).hexdigest()[:12]
    contract_name = payload.contract_name or infer_contract_name(project) or "Solidity Project"
    synthesized_summary = make_summary(contract_name, findings, gas, compliance, payload.preview)
    report = AuditReport(
        audit_id=audit_id,
        contract_name=contract_name,
        created_at=datetime.now(UTC).isoformat(),
        pricing={
            "mode": "preview" if payload.preview else "paid",
            "line_count": line_count,
            "amount_cents": price_cents,
            "display": "free preview" if payload.preview else ("$2 under 500 lines" if line_count < 500 else "$5 for 500+ lines"),
        },
        preview=payload.preview,
        severity_summary=severity_summary,
        findings=findings_for_response,
        gas_optimizations=gas if not payload.preview else [],
        compliance=compliance if not payload.preview else {"summary": compliance.get("summary", {}), "details_hidden": True},
        model_reports=model_reports,
        synthesized_summary=synthesized_summary,
    )
    if not payload.preview:
        report.markdown_report = render_markdown(report)
        report.pdf_report = render_pdfish(report)
    return report


def analyze_project(project: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    for file_path, source in project.items():
        lines = source.splitlines()
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            context = "\n".join(lines[max(0, idx - 4): min(len(lines), idx + 4)])
            lower_context = context.lower()
            if ".call{" in line or ".call.value" in line or re.search(r"\.call\s*\(", line):
                if not has_nearby_guard(context):
                    findings.append(make_finding("unchecked-call", "Unchecked low-level external call", "High", "SWC-104", file_path, idx, stripped, "Low-level calls return false on failure and can hide failed transfers or arbitrary external execution.", "An attacker can force the callee to revert or consume gas while the parent contract continues as if payment or execution succeeded.", "Capture the success flag, require it, and emit an event for failed downstream integrations.", "(bool ok, ) = recipient.call{value: amount}(\"\");\nrequire(ok, \"ETH transfer failed\");", "static"))
                if "nonreentrant" not in lower_context and re.search(r"balances?\s*\[[^\]]+\]\s*(?:-=|=)", "\n".join(lines[idx: idx + 5])):
                    findings.append(make_finding("reentrancy", "External call before state update", "Critical", "SWC-107", file_path, idx, stripped, "State appears to be updated after an external call, which is a classic reentrancy pattern.", "A malicious receiver contract can recursively call back before its balance is reduced and drain funds.", "Follow checks-effects-interactions and add a ReentrancyGuard modifier on value-moving entrypoints.", "uint256 amount = balances[msg.sender];\nbalances[msg.sender] = 0;\n(bool ok, ) = msg.sender.call{value: amount}(\"\");\nrequire(ok, \"transfer failed\");", "static"))
            if "tx.origin" in line:
                findings.append(make_finding("tx-origin", "Authorization uses tx.origin", "High", "SWC-115", file_path, idx, stripped, "tx.origin is unsafe for authorization because phishing contracts can preserve the victim origin.", "A malicious contract can trick an owner into calling it, then call this contract with tx.origin still equal to the owner.", "Use msg.sender for direct caller authorization and explicit role checks.", "require(msg.sender == owner, \"not owner\");", "static"))
            if re.search(r"block\.(timestamp|number)|now\b", line):
                findings.append(make_finding("timestamp-dependence", "Miner/validator-influenced time dependency", "Medium", "SWC-116", file_path, idx, stripped, "Block timestamp/number can be manipulated within consensus tolerance and is unsafe for randomness or tight deadlines.", "A validator can slightly shift timestamps to win lotteries or bypass exact time gates.", "Avoid timestamp randomness; use commit-reveal or a VRF. For deadlines, allow broad windows.", "require(block.timestamp >= unlockTime + 5 minutes, \"too early\");", "static"))
            if re.search(r"\bselfdestruct\s*\(", line):
                findings.append(make_finding("selfdestruct", "Dangerous selfdestruct usage", "High", "SWC-106", file_path, idx, stripped, "selfdestruct can permanently remove code or force-send ETH and has changed semantics on newer EVM forks.", "If access control is weak or upgrade keys are compromised, an attacker can brick the contract or grief accounting.", "Remove selfdestruct for production or restrict it behind timelocked governance with emergency runbooks.", "// Prefer pausable/timelocked shutdown over selfdestruct.", "static"))
            if re.search(r"delegatecall\s*\(", line):
                findings.append(make_finding("delegatecall", "delegatecall to untrusted target", "Critical", "SWC-112", file_path, idx, stripped, "delegatecall executes target code in this contract's storage context.", "An attacker-controlled implementation can overwrite owner/storage slots and seize funds.", "Allowlist implementations, lock upgrades behind timelocks, and validate storage layout.", "require(approvedImplementation[target], \"implementation not approved\");\n(bool ok, bytes memory data) = target.delegatecall(payload);\nrequire(ok, \"delegatecall failed\");", "static"))
            if re.search(r"\babi\.encodePacked\s*\(", line) and "keccak256" in context:
                findings.append(make_finding("hash-collision", "Potential abi.encodePacked hash collision", "Medium", "SWC-133", file_path, idx, stripped, "Packed encoding of multiple dynamic values can collide.", "A crafted pair of dynamic strings/bytes can produce the same packed hash and bypass signature or uniqueness checks.", "Use abi.encode for typed delimiters or include lengths/domain separators.", "bytes32 digest = keccak256(abi.encode(user, amount, nonce));", "static"))
            if re.search(r"function\s+\w+\s*\([^)]*\)\s*(public|external)?[^\{;]*\{", line) and ("onlyowner" not in lower_context and "onlyrole" not in lower_context):
                if any(word in lower_context for word in ["mint(", "burn(", "setowner", "upgrade", "withdraw", "pause(", "unpause("]):
                    findings.append(make_finding("access-control", "Sensitive function may be missing access control", "High", "SWC-105", file_path, idx, stripped, "A sensitive function name/body was found without an obvious onlyOwner/onlyRole guard nearby.", "Anyone may call the function to mint/burn, withdraw assets, pause operations, or change privileged configuration.", "Add role-based access control and tests proving unauthorized callers revert.", "function withdraw(uint256 amount) external onlyOwner {\n    _withdraw(amount);\n}", "static"))
            if re.search(r"pragma\s+solidity\s+[^;]*(\^0\.4|>=0\.4|<0\.8|0\.5|0\.6|0\.7)", line):
                findings.append(make_finding("old-pragma", "Compiler version lacks default overflow checks", "Medium", "SWC-103", file_path, idx, stripped, "Solidity versions below 0.8 do not include built-in arithmetic overflow/underflow checks.", "Arithmetic on balances/supply can wrap and corrupt accounting if SafeMath is absent.", "Use Solidity 0.8+ or SafeMath for legacy deployments.", "pragma solidity ^0.8.24;", "static"))
            if re.search(r"\b(owner|admin)\s*=\s*tx\.origin\b", line):
                findings.append(make_finding("owner-tx-origin", "Owner assigned from tx.origin", "High", "SWC-115", file_path, idx, stripped, "Assigning privileged roles from tx.origin can set unexpected owners through deployment factories.", "A factory or phishing flow can cause owner to be the EOA origin rather than the intended caller/controller.", "Assign owner from msg.sender or constructor argument and emit ownership transfer.", "constructor(address initialOwner) { owner = initialOwner; }", "static"))
        findings.extend(contract_level_checks(file_path, source))
    return dedupe_findings(findings)


def contract_level_checks(file_path: str, source: str) -> list[Finding]:
    findings: list[Finding] = []
    lowered = source.lower()
    if "pragma solidity" not in lowered:
        findings.append(make_finding("missing-pragma", "Missing Solidity pragma", "Low", None, file_path, 1, "", "No explicit compiler version was found.", "Different compiler defaults can change bytecode, optimizer behavior, or safety assumptions.", "Pin a tested compiler range and lock it in CI.", "pragma solidity ^0.8.24;", "static"))
    if "unchecked" in lowered:
        line = line_number(source, "unchecked")
        findings.append(make_finding("unchecked-arithmetic", "Unchecked arithmetic block", "Medium", "SWC-101", file_path, line, source.splitlines()[line - 1].strip() if source.splitlines() else "", "unchecked disables Solidity 0.8 overflow checks.", "A boundary input can underflow/overflow counters or balances if preconditions are wrong.", "Keep unchecked blocks tiny and assert bounds before entering them.", "require(x >= y, \"underflow\");\nunchecked { x -= y; }", "static"))
    if "receive() external payable" in lowered or "fallback() external payable" in lowered:
        if "emit " not in lowered:
            line = line_number(lowered, "receive() external payable") if "receive() external payable" in lowered else line_number(lowered, "fallback() external payable")
            findings.append(make_finding("payable-no-event", "Payable fallback/receive lacks accounting event", "Low", None, file_path, line, "payable fallback/receive", "Direct ETH receipts are hard to reconcile without events.", "Funds can be sent directly and missed by off-chain accounting or monitoring.", "Emit a Deposited event and document direct-send behavior.", "event Deposited(address indexed from, uint256 amount);\nreceive() external payable { emit Deposited(msg.sender, msg.value); }", "static"))
    return findings


def make_finding(key: str, title: str, severity: str, swc_id: str | None, file: str, line: int, code: str, description: str, attack_vector: str, remediation: str, fixed_snippet: str, source: str) -> Finding:
    digest = hashlib.sha1(f"{key}:{file}:{line}:{code}".encode()).hexdigest()[:8]
    return Finding(id=f"{key}-{digest}", title=title, severity=severity, swc_id=swc_id, file=file, line=line, code=code, description=description, attack_vector=attack_vector, remediation=remediation, fixed_snippet=fixed_snippet, source=source)


def has_nearby_guard(context: str) -> bool:
    lowered = context.lower()
    return "require(success" in lowered or "require(ok" in lowered or "if (!success)" in lowered or "if(!success)" in lowered or "revert " in lowered


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, int, str]] = set()
    output: list[Finding] = []
    for finding in sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.file, f.line, f.title)):
        key = (finding.title, finding.file, finding.line, finding.code)
        if key not in seen:
            seen.add(key)
            output.append(finding)
    return output


def gas_optimizations(project: dict[str, str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for file_path, source in project.items():
        for idx, line in enumerate(source.splitlines(), start=1):
            if re.search(r"for\s*\([^;]+;[^;]+\.length\s*;", line):
                items.append({"file": file_path, "line": idx, "title": "Cache array length in loops", "recommendation": "Store array.length in a local uint256 before the loop to avoid repeated reads."})
            if re.search(r"\b(string|bytes)\s+(memory)\s+\w+", line) and "external" in line:
                items.append({"file": file_path, "line": idx, "title": "Use calldata for external dynamic arguments", "recommendation": "Prefer calldata over memory for external string/bytes/array parameters."})
            if "public" in line and re.search(r"\b(public)\b", line) and "function" in line and not re.search(r"\b(public)\s+(view|pure)", line):
                items.append({"file": file_path, "line": idx, "title": "Use external where possible", "recommendation": "Functions not called internally can be external to reduce ABI copy overhead."})
    return items[:20]


def compliance_checks(project: dict[str, str], standards: list[str]) -> dict[str, Any]:
    source = "\n".join(project.values())
    checks: dict[str, Any] = {}
    lowered = source.lower()
    if "ERC-20" in standards:
        required = ["totalsupply", "balanceof", "transfer", "allowance", "approve", "transferfrom"]
        checks["ERC-20"] = standard_result(required, lowered, ["Transfer", "Approval"], source)
    if "ERC-721" in standards:
        required = ["ownerof", "balanceof", "safetransferfrom", "transferfrom", "approve", "setapprovalforall"]
        checks["ERC-721"] = standard_result(required, lowered, ["Transfer", "Approval", "ApprovalForAll"], source)
    if "ERC-1155" in standards:
        required = ["balanceof", "balanceofbatch", "safetransferfrom", "safebatchtransferfrom", "setapprovalforall"]
        checks["ERC-1155"] = standard_result(required, lowered, ["TransferSingle", "TransferBatch", "ApprovalForAll", "URI"], source)
    checks["summary"] = {name: value["status"] for name, value in checks.items() if isinstance(value, dict) and "status" in value}
    return checks


def standard_result(required: list[str], lowered_source: str, events: list[str], original_source: str) -> dict[str, Any]:
    missing = [name for name in required if name.lower() not in lowered_source]
    missing_events = [event for event in events if f"event {event}" not in original_source and f"emit {event}" not in original_source]
    if not missing and not missing_events:
        status = "appears_compliant"
    elif len(missing) <= 2:
        status = "partial"
    else:
        status = "not_detected"
    return {"status": status, "missing_functions": missing, "missing_events": missing_events}


class StaticModelProvider:
    def __init__(self, provider: str, focus: str):
        self.provider = provider
        self.focus = focus

    def analyze(self, project: dict[str, str], base_findings: list[Finding]) -> ModelReport:
        selected = []
        for finding in base_findings:
            if self.focus == "exploitability" and finding.severity in {"Critical", "High", "Medium"}:
                selected.append(finding.model_copy(update={"source": self.provider}))
            elif self.focus == "remediation" and finding.severity in {"Critical", "High", "Low", "Informational"}:
                selected.append(finding.model_copy(update={"source": self.provider}))
        if not selected and base_findings:
            selected = [base_findings[0].model_copy(update={"source": self.provider})]
        summary = f"{self.provider} reviewed {len(project)} file(s) for {self.focus} and produced {len(selected)} finding(s)."
        return ModelReport(provider=self.provider, summary=summary, findings=selected)


def synthesize_findings(reports: list[ModelReport]) -> list[Finding]:
    by_signature: dict[tuple[str, str, int], Finding] = {}
    for report in reports:
        for finding in report.findings:
            sig = (finding.title, finding.file, finding.line)
            if sig not in by_signature:
                by_signature[sig] = finding.model_copy(update={"source": "synthesizer"})
            else:
                by_signature[sig].source = "synthesizer:confirmed_by_multiple_models"
    return sorted(by_signature.values(), key=lambda f: (SEVERITY_ORDER[f.severity], f.file, f.line))


def summarize(findings: list[Finding]) -> dict[str, int]:
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        counts[finding.severity] += 1
    return counts


def infer_contract_name(project: dict[str, str]) -> str | None:
    match = re.search(r"\bcontract\s+(\w+)", "\n".join(project.values()))
    return match.group(1) if match else None


def make_summary(contract_name: str, findings: list[Finding], gas: list[dict[str, Any]], compliance: dict[str, Any], preview: bool) -> str:
    counts = summarize(findings)
    top = next((f for f in findings if f.severity in {"Critical", "High"}), None)
    risk = "review required" if any(counts[s] for s in ["Critical", "High"]) else "moderate/low risk from static heuristics"
    detail = "Preview mode hides detailed findings." if preview else f"Top issue: {top.title if top else 'none'}. Gas recommendations: {len(gas)}."
    return f"{contract_name} audit completed: {risk}. Severity counts: {counts}. Compliance: {compliance.get('summary', {})}. {detail}"


def render_markdown(report: AuditReport) -> str:
    lines = [f"# Smart Contract Audit: {report.contract_name}", "", f"Audit ID: `{report.audit_id}`", f"Created: {report.created_at}", "", "## Severity Summary", ""]
    for severity, count in report.severity_summary.items():
        lines.append(f"- **{severity}:** {count}")
    lines.extend(["", "## Synthesized Summary", "", report.synthesized_summary, "", "## Findings", ""])
    if not report.findings:
        lines.append("No findings returned in this mode.")
    for finding in report.findings:
        swc = f" ({finding.swc_id})" if finding.swc_id else ""
        lines.extend([
            f"### {finding.severity}: {finding.title}{swc}",
            f"- Location: `{finding.file}:{finding.line}`",
            f"- Code: `{finding.code}`",
            f"- Description: {finding.description}",
            f"- Attack vector: {finding.attack_vector}",
            f"- Remediation: {finding.remediation}",
            "",
            "```solidity",
            finding.fixed_snippet,
            "```",
            "",
        ])
    lines.extend(["## Gas Optimizations", ""])
    for item in report.gas_optimizations or []:
        lines.append(f"- `{item['file']}:{item['line']}` **{item['title']}** — {item['recommendation']}")
    if not report.gas_optimizations:
        lines.append("- No gas-specific recommendations detected.")
    lines.extend(["", "## Compliance", "", "```json", json.dumps(report.compliance, indent=2), "```", "", "## Model Pipeline", ""])
    for model_report in report.model_reports:
        lines.append(f"- **{model_report.provider}:** {model_report.summary}")
    return "\n".join(lines) + "\n"


def render_pdfish(report: AuditReport) -> str:
    return "PDF-ish Smart Contract Audit Report\n" + "=" * 40 + "\n\n" + render_markdown(report)


def render_markdown_from_dict(report: dict[str, Any]) -> str:
    return report.get("markdown_report") or "# Smart Contract Audit\n\n" + json.dumps(report, indent=2)


def render_pdfish_from_dict(report: dict[str, Any]) -> str:
    return report.get("pdf_report") or "PDF-ish Smart Contract Audit Report\n" + render_markdown_from_dict(report)


def render_html_from_dict(report: dict[str, Any]) -> str:
    findings = report.get("findings", [])
    rows = "".join(
        f"<tr><td>{html.escape(item.get('severity', ''))}</td><td>{html.escape(item.get('title', ''))}</td><td>{html.escape(item.get('file', ''))}:{item.get('line', '')}</td><td>{html.escape(item.get('swc_id') or '')}</td></tr>"
        for item in findings
    ) or "<tr><td colspan='4'>No detailed findings in this report.</td></tr>"
    summary = html.escape(json.dumps(report.get("severity_summary", {})))
    compliance = html.escape(json.dumps(report.get("compliance", {}), indent=2))
    return f"""
    <html><head><title>Audit {html.escape(report.get('audit_id', ''))}</title>
    <style>body{{font-family:Arial;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:.45rem;text-align:left}}pre{{background:#f7f7f7;padding:1rem;overflow:auto}}</style></head>
    <body><h1>Smart Contract Audit: {html.escape(report.get('contract_name', ''))}</h1>
    <p><b>Audit ID:</b> {html.escape(report.get('audit_id', ''))}</p>
    <p><b>Created:</b> {html.escape(report.get('created_at', ''))}</p>
    <p><b>Severity:</b> {summary}</p>
    <p>{html.escape(report.get('synthesized_summary', ''))}</p>
    <h2>Findings</h2><table><thead><tr><th>Severity</th><th>Title</th><th>Location</th><th>SWC</th></tr></thead><tbody>{rows}</tbody></table>
    <h2>Compliance</h2><pre>{compliance}</pre>
    </body></html>
    """


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
                "maxTimeoutSeconds": 90,
                "asset": BASE_USDC,
                "outputSchema": {"input": {"type": "http", "method": "POST", "discoverable": True}},
                "extra": {"name": "USD Coin", "version": "2"},
            }
        ],
    }


def append_history(path: Path, report: AuditReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(report.model_dump(), sort_keys=True) + "\n")


def read_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def find_history(path: Path, audit_id: str) -> dict[str, Any] | None:
    for row in reversed(read_history(path)):
        if row.get("audit_id") == audit_id:
            return row
    return None


def line_number(source: str, needle: str) -> int:
    for idx, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return idx
    return 1


app = create_app()
