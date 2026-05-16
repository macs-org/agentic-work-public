
from __future__ import annotations

import hashlib
import json
from typing import Any

from .requirements_matrix import REQUIREMENT_BY_ID, Requirement


def content_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _item(req_id: str, label: str, value: str, json_safe: bool = False) -> dict:
    req = REQUIREMENT_BY_ID[req_id]
    requirement = req.id if json_safe else req
    return {"requirement_id": req.id, "requirement": requirement, "label": label, "value": value}


def _package(kind: str, version: int, items: list[dict], json_safe: bool = False) -> dict:
    serializable_items = []
    for item in items:
        if json_safe and not isinstance(item["requirement"], str):
            item = {**item, "requirement": item["requirement"].id}
        serializable_items.append(item)
    body = {"kind": kind, "version": version, "items": serializable_items}
    body["content_hash"] = content_hash(body)
    return body


def offering_statement_package(json_safe: bool = False) -> dict:
    items = [
        _item("R-027", "Offering statement package", "Completed demo offering statement and related documents prepared for external filing/export.", json_safe),
        _item("R-028", "Financial information", "Unaudited demo balance sheet: $0 liabilities; $50,000 demo treasury; no real funds represented.", json_safe),
        _item("R-029", "Issuer and operations", "Demo issuer builds open-source CLARITY-aware token tooling and buyer-visible disclosure pages.", json_safe),
        _item("R-030", "Financial condition", "Demo issuer is pre-revenue; runway and spending assumptions are example-only.", json_safe),
        _item("R-031", "Plan of distribution", "Demo distribution: creator allocation, public test allocation, and ecosystem reserve shown as sample values.", json_safe),
        _item("R-032", "Use of proceeds", "Demo proceeds support development, hosting, legal review, and community testing; no real sale occurs.", json_safe),
        _item("R-033", "Development plan", "Milestones: public test app, source-backed disclosures, simulated launch adapter, post-launch reporting demo.", json_safe),
    ]
    return _package("offering_statement", 1, items, json_safe)


def purchaser_information_package(json_safe: bool = False) -> dict:
    ids_labels = [
        ("R-034", "Maturity status", "Not certified mature; demo records intent/timeline toward maturity where applicable."),
        ("R-035", "Source code URL", "https://github.com/macs-org/agentic-work-public/tree/main/clarity-act-dot-fun/test-launch-flow"),
        ("R-036", "Externally sourced code", "Some framework/runtime dependencies are externally sourced and listed in requirements.txt."),
        ("R-037", "External dependencies", "FastAPI, Starlette/httpx test stack, Vercel Python serverless runtime."),
        ("R-038", "Third-party audit", "No third-party audit is claimed. If claimed, creator must provide report URL and external audit-completion affirmation."),
        ("R-039", "Transaction-history verification", "Use chain explorer/RPC URL supplied at launch; demo token is simulated so no explorer transaction exists."),
        ("R-040", "Blockchain-system purpose", "Demo system illustrates compliance-first token creation and buyer disclosure hosting."),
        ("R-041", "Launch/supply", "Total demo units: 1,000,000; schedule and outstanding units are sample-only."),
        ("R-042", "Holding/access/transfer", "Example ERC-20-like wallet holding and transfer requirements; no production contract deployed."),
        ("R-043", "Consensus/generation/burn", "Demo describes generation and burn mechanics as adapter payload fields, not real onchain behavior."),
        ("R-044", "Value mechanism", "Demo token value is not promised; any value discussion is tied to blockchain-system use only."),
        ("R-045", "Governance", "Example governance can propose disclosure updates; no issuer profit/revenue rights are granted."),
        ("R-046", "Current state/timeline", "Public Vercel test app with generated statutory requirement surfaces."),
        ("R-047", "Roles", "Users, service providers, developers, validators, and governance participants are listed in the demo form."),
        ("R-048", "Control/authority", "Admin-key and upgrade-control fields are collected and buyer-visible where applicable."),
        ("R-049", "Critical dependencies", "Hosting, chain RPC, adapter API availability, and source repository integrity."),
        ("R-051", "Material risks", "Regulatory uncertainty, software bugs, hosting outages, wallet/key loss, and simulated launch limitations."),
    ]
    items = [_item(req_id, label, value, json_safe) for req_id, label, value in ids_labels]
    items.append(_item("R-050", "Confidential ownership status", "Confidential ownership list completed; not public by default.", json_safe))
    return _package("purchaser_information", 1, items, json_safe)


def semiannual_report_package(json_safe: bool = False) -> dict:
    items = [
        _item("R-052", "Semiannual reporting status", "Demo semiannual report generated for a non-mature §4(a)(8) path.", json_safe),
        _item("R-053", "Current state and timeline", "Public test app launched; next milestone is production token-launch integration review.", json_safe),
        _item("R-054", "Development efforts", "Issuer and related-person efforts: source-backed UI, hosted forms, smoke testing, buyer review flows.", json_safe),
        _item("R-055", "Money raised/spent", "Raised: $0 real funds. Spent: $0 real funds. Categories are demo-only.", json_safe),
        _item("R-056", "Financial statements", "Demo financial statement placeholder; no confidential financial attachment is public.", json_safe),
    ]
    return _package("semiannual_report_2026_H1", 1, items, json_safe)


def current_report_package(json_safe: bool = False) -> dict:
    return _package("current_report_demo_material_change", 1, [_item("R-057", "Material change report", "Demo current report form for material changes; external filing affirmation used only for off-platform filing.", json_safe)], json_safe)


def certification_package(json_safe: bool = False) -> dict:
    items = [
        _item("R-075", "Start maturity certification", "Demo eligible-person filer selector and package builder are present.", json_safe),
        _item("R-076", "Certification evidence", "Operation, functionality, value derivation, governance, and current material roles evidence sections are completed with demo values.", json_safe),
        _item("R-077", "Review/status tracker", "60-day review, stay, public notice, disposition, rebuttal, appeal, and recertification statuses tracked externally.", json_safe),
        _item("R-078", "Maturity criteria", "System value, functional system, openness, programmatic operation, governance, impartiality, and distributed ownership checklist completed with demo values.", json_safe),
        _item("R-079", "Preexisting-system criteria", "Optional preexisting-system criteria captured as not triggered in this demo.", json_safe),
    ]
    return _package("maturity_certification", 1, items, json_safe)
