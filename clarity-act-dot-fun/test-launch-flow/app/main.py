
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from .hosted_forms import (
    certification_package,
    content_hash,
    current_report_package,
    offering_statement_package,
    purchaser_information_package,
    semiannual_report_package,
)
from .requirements_matrix import PAGE_REQUIREMENTS, REQUIREMENTS, Requirement, by_ids, validate_matrix
from .sample_data import DEMO_TOKEN, LAUNCH_MECHANICS, PRIVATE_CONFIDENTIAL_OWNERSHIP, PUBLIC_STATUS

app = FastAPI(
    title="clarity-act.fun public test launch flow",
    version="0.1.0",
    description="No-auth public FastAPI/Vercel demo for CLARITY Act token-creator launch-flow coverage.",
)

SMART_CONTRACT_NOTICE = "Smart-contract launch requirement — not a CLARITY Act requirement"
PUBLIC_PATHS = [
    "/",
    "/token/create",
    "/forms/demo/offering-statement",
    "/forms/demo/purchaser-information",
    "/reports/0xDemo/semiannual/2026-H1",
    "/certifications/0xDemo/maturity",
    "/token/0xDemo",
    "/launch/mechanics",
]

def page(title: str, body: str) -> HTMLResponse:
    now = datetime.now(timezone.utc).isoformat()
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} · clarity-act.fun test launch flow</title>
  <style>
    :root {{ color-scheme: dark; --bg:#08111f; --panel:#111c2e; --muted:#8da2c0; --text:#eef6ff; --accent:#79f2c0; --line:#263954; --warn:#ffd166; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at top left, #13284b, var(--bg) 45%); color: var(--text); line-height:1.45; }}
    a {{ color: var(--accent); }}
    header, main, footer {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    header {{ display:flex; gap:18px; align-items:center; justify-content:space-between; }}
    nav a {{ margin-right: 14px; font-size: 0.95rem; }}
    .hero, .panel, .requirement-control, .form-section {{ background: rgba(17,28,46,.92); border:1px solid var(--line); border-radius:18px; padding:20px; box-shadow: 0 16px 60px rgba(0,0,0,.22); margin:16px 0; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:16px; }}
    .badge, .citation-chip, .mode, .status {{ display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:5px 10px; font-size:.8rem; border:1px solid var(--line); background:#0b1525; color:var(--text); margin: 3px 5px 3px 0; }}
    .citation-chip {{ color:#111c2e; background:var(--accent); border-color:transparent; font-weight:700; }}
    .mode {{ color: var(--warn); }}
    .status {{ color: var(--accent); }}
    input, textarea, select {{ width:100%; margin:6px 0 12px; padding:10px; border-radius:10px; border:1px solid var(--line); background:#07101d; color:var(--text); }}
    textarea {{ min-height:80px; }}
    table {{ width:100%; border-collapse: collapse; margin:12px 0; }}
    th, td {{ padding:10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    details {{ margin-top:8px; color:var(--muted); }}
    summary {{ cursor:pointer; color:var(--text); }}
    .notice {{ border-left:4px solid var(--accent); padding-left:12px; color:var(--muted); }}
    .danger {{ color:#ff9aa2; }}
    .muted {{ color:var(--muted); }}
    .toc {{ columns:2; }}
    @media (max-width: 760px) {{ header {{ display:block; }} .toc {{ columns:1; }} }}
  </style>
</head>
<body>
  <header>
    <div><strong>clarity-act.fun</strong><div class="muted">Public Vercel test app · generated {escape(now)}</div></div>
    <nav><a href="/">Home</a><a href="/token/create">Create token</a><a href="/token/0xDemo">Demo token</a><a href="/ready">Ready JSON</a></nav>
  </header>
  <main>{body}</main>
  <footer class="muted">Demo only. No real SEC filing, token deploy, private key use, or onchain write occurs.</footer>
</body>
</html>"""
    return HTMLResponse(html)


def citation_chip(req: Requirement) -> str:
    return (
        f'<span class="citation-chip" data-requirement-id="{req.id}">'
        f'{req.id} · {escape(req.bill_section)} · {escape(req.source_file)} lines {escape(req.source_lines)}</span>'
    )


def citation_panel(reqs: list[Requirement]) -> str:
    items = "".join(
        f"<li>{citation_chip(req)}<br><span>{escape(req.title)}</span></li>" for req in reqs
    )
    return f"<aside class=\"panel clarity-references\"><h2>CLARITY Act references</h2><ul>{items}</ul></aside>"


def requirement_control(req: Requirement, completed_answer: str | None = None) -> str:
    controls = "".join(f"<li>{escape(c)}</li>" for c in req.controls)
    answer = completed_answer or f"Demo input/status for {escape(req.id)}: {escape(req.controls[0])}."
    if req.completion_mode == "external_completion_affirmation":
        input_html = (
            '<label><input type="checkbox" checked /> '
            'I affirm this external action/status is completed outside this demo platform where required.</label>'
            '<input value="https://example.invalid/evidence/demo" aria-label="optional external evidence URL" />'
        )
    elif req.completion_mode == "computed_from_inputs":
        input_html = f'<p class="status">Computed demo status: pass / not triggered based on creator inputs for {req.id}</p>'
    elif req.completion_mode == "creator_upload_or_link":
        input_html = '<input value="https://example.invalid/demo-source-or-evidence" aria-label="creator supplied URL" />'
    elif req.completion_mode == "hosted_form":
        input_html = '<textarea aria-label="completed hosted form answer">' + escape(answer) + '</textarea>'
    else:
        input_html = '<textarea aria-label="creator input">' + escape(answer) + '</textarea>'
    return f"""
<section class="requirement-control" data-requirement-id="{req.id}">
  <h3>{escape(req.id)} — {escape(req.title)}</h3>
  <p>{citation_chip(req)} <span class="mode">{escape(req.tag)} · {escape(req.completion_mode)}</span></p>
  <ul>{controls}</ul>
  {input_html}
  <details><summary>Citation drawer / exact local-source excerpt</summary><p><strong>{escape(req.bill_section)}</strong><br>{escape(req.source_file)} lines {escape(req.source_lines)}</p><blockquote>{escape(req.excerpt)}</blockquote></details>
</section>"""


def render_requirement_sections() -> str:
    sections: list[str] = []
    ordered_pages = sorted(PAGE_REQUIREMENTS.keys(), key=lambda p: int(p.split(" — ")[0]) if p.split(" — ")[0].isdigit() else 99)
    for page_name in ordered_pages:
        reqs = PAGE_REQUIREMENTS[page_name]
        controls = "".join(requirement_control(req) for req in reqs)
        sections.append(f"<section class=\"panel\"><h2>{escape(page_name)}</h2>{citation_panel(reqs)}{controls}</section>")
    return "".join(sections)

@app.get("/health")
def health():
    return {"status": "ok", "app": "clarity-act-dot-fun/test-launch-flow", "no_auth_public_demo": True}

@app.get("/ready")
def ready():
    errors = validate_matrix()
    return {
        "status": "ready" if not errors else "not_ready",
        "requirement_count": len(REQUIREMENTS),
        "requirement_range": [REQUIREMENTS[0].id, REQUIREMENTS[-1].id],
        "matrix_loaded": not errors,
        "errors": errors,
        "public_paths": PUBLIC_PATHS,
    }

@app.get("/", response_class=HTMLResponse)
def home():
    body = """
    <section class="hero">
      <h1>CLARITY Act token launch-flow public test app</h1>
      <p>This no-auth Vercel/FastAPI demo shows a buyer-visible token launch path where each current House-engrossed CLARITY Act token-creator requirement is mapped to a visible input, status, hosted form section, or external-action affirmation.</p>
      <p><a class="badge" href="/token/create">Open token creation flow</a> <a class="badge" href="/forms/demo/offering-statement">Hosted offering statement</a> <a class="badge" href="/forms/demo/purchaser-information">Hosted purchaser information</a> <a class="badge" href="/token/0xDemo">Buyer token page</a></p>
    </section>
    <section class="grid">
      <div class="panel"><h2>Coverage</h2><p>R-001 through R-080 are loaded from <code>app/requirements_matrix.py</code> with bill section labels, local source line ranges, completion modes, and exact excerpt text.</p></div>
      <div class="panel"><h2>Public forms</h2><p>Completed demo offering statement, purchaser information, semiannual report, and maturity certification packages are hosted for buyer review with JSON export links and content hashes.</p></div>
      <div class="panel"><h2>Confidential handling</h2><p>Confidential ownership list completed; not public by default. Buyer pages show only this status, not private person names or wallet values.</p></div>
      <div class="panel"><h2>Launch mechanics</h2><p>Bankr/Liquid/Doppler-style deploy fields are labeled separately as smart-contract launch requirements, not CLARITY Act requirements.</p></div>
    </section>
    """
    return page("Home", body)

@app.get("/token/create", response_class=HTMLResponse)
def token_create():
    body = f"""
    <section class="hero">
      <h1>Create a CLARITY-aware token launch</h1>
      <p class="notice">Every statutory/classification/external action control below renders a citation chip and a CLARITY Act references panel. Smart-contract launch fields are separated at the end.</p>
      <p><a href="/forms/demo/offering-statement">Preview hosted offering statement</a> · <a href="/forms/demo/purchaser-information">Preview purchaser information</a> · <a href="/launch/mechanics">Launch mechanics</a> · <a href="/token/0xDemo">Buyer token page</a></p>
    </section>
    {render_requirement_sections()}
    <section class="panel" id="launch-mechanics-inline">
      <h2>15 — Launch mechanics</h2>
      <p class="badge">{SMART_CONTRACT_NOTICE}</p>
      <label>Adapter selector<select><option>Bankr structured deploy endpoint demo</option><option>Liquid demo adapter</option><option>Doppler demo adapter</option></select></label>
      <label>Token symbol<input value="DEMO" /></label>
      <label>Fee recipient<input value="wallet:0xDemoCreator" /></label>
      <button type="button">Run simulation — fake/no onchain write</button>
      <button type="button">Confirm launch mechanics</button>
    </section>
    """
    return page("Token creation flow", body)

@app.get("/launch/mechanics", response_class=HTMLResponse)
def launch_mechanics():
    rows = "".join(f"<tr><th>{escape(k)}</th><td>{escape(str(v))}</td></tr>" for k, v in LAUNCH_MECHANICS.items())
    body = f"""
    <section class="hero"><h1>Launch mechanics</h1><p class="badge">{SMART_CONTRACT_NOTICE}</p><p>This page is deliberately non-statutory: simulation/deploy fields are provider/API mechanics only.</p></section>
    <section class="panel"><h2>Demo adapter payload</h2><table>{rows}</table><p class="danger">Simulation only. No private keys, API keys, mainnet writes, or real filings are present.</p></section>
    """
    return page("Launch mechanics", body)


def render_package(title: str, package: dict, reqs: list[Requirement], json_url: str) -> HTMLResponse:
    answer_rows = "".join(
        f"<tr><th>{escape(item['label'])}</th><td>{escape(item['value'])}</td><td>{citation_chip(item['requirement'])}</td></tr>"
        for item in package["items"]
    )
    body = f"""
    <section class="hero"><h1>{escape(title)}</h1><p>Human-readable completed public form view with citations, version, and content hash.</p><p><a class="badge" href="{escape(json_url)}">JSON export</a> <span class="badge">version {escape(str(package['version']))}</span> <span class="badge">hash {escape(package['content_hash'])}</span></p></section>
    {citation_panel(reqs)}
    <section class="form-section"><table><thead><tr><th>Completed section</th><th>Demo answer</th><th>Citation</th></tr></thead><tbody>{answer_rows}</tbody></table></section>
    """
    return page(title, body)

@app.get("/forms/demo/offering-statement", response_class=HTMLResponse)
def offering_statement():
    reqs = by_ids([f"R-{i:03d}" for i in range(27, 34)])
    return render_package("Hosted offering statement", offering_statement_package(), reqs, "/forms/demo/offering-statement.json")

@app.get("/forms/demo/offering-statement.json")
def offering_statement_json():
    return offering_statement_package(json_safe=True)

@app.get("/forms/demo/purchaser-information", response_class=HTMLResponse)
def purchaser_information():
    ids = [f"R-{i:03d}" for i in range(34, 50)] + ["R-051"]
    reqs = by_ids(ids)
    return render_package("Hosted purchaser information", purchaser_information_package(), reqs, "/forms/demo/purchaser-information.json")

@app.get("/forms/demo/purchaser-information.json")
def purchaser_information_json():
    return purchaser_information_package(json_safe=True)

@app.get("/reports/0xDemo/semiannual/2026-H1", response_class=HTMLResponse)
def semiannual_report():
    ids = [f"R-{i:03d}" for i in range(52, 57)]
    reqs = by_ids(ids)
    return render_package("Hosted semiannual report · 2026-H1", semiannual_report_package(), reqs, "/reports/0xDemo/semiannual/2026-H1.json")

@app.get("/reports/0xDemo/semiannual/2026-H1.json")
def semiannual_report_json():
    return semiannual_report_package(json_safe=True)

@app.get("/reports/0xDemo/current/demo-material-change", response_class=HTMLResponse)
def current_report():
    reqs = by_ids(["R-057"])
    return render_package("Hosted current report · demo material change", current_report_package(), reqs, "/reports/0xDemo/current/demo-material-change.json")

@app.get("/reports/0xDemo/current/demo-material-change.json")
def current_report_json():
    return current_report_package(json_safe=True)

@app.get("/certifications/0xDemo/maturity", response_class=HTMLResponse)
def maturity_certification():
    reqs = by_ids([f"R-{i:03d}" for i in range(75, 80)])
    return render_package("Hosted maturity certification package", certification_package(), reqs, "/certifications/0xDemo/maturity.json")

@app.get("/certifications/0xDemo/maturity.json")
def maturity_certification_json():
    return certification_package(json_safe=True)

@app.get("/exports/demo/confidential-ownership")
def confidential_export_metadata():
    return JSONResponse({
        "visibility": "private_export_only",
        "requirement_id": "R-050",
        "status": PUBLIC_STATUS["confidential_ownership"],
        "content_hash": content_hash(PRIVATE_CONFIDENTIAL_OWNERSHIP),
        "notice": "Confidential packet metadata only. Public token/form pages do not expose person names or wallet values.",
    })

@app.get("/token/0xDemo", response_class=HTMLResponse)
def token_page():
    public_links = """
    <ul>
      <li><a href="/forms/demo/offering-statement">Completed offering statement</a></li>
      <li><a href="/forms/demo/purchaser-information">Completed purchaser information</a></li>
      <li><a href="/reports/0xDemo/semiannual/2026-H1">Semiannual report 2026-H1</a></li>
      <li><a href="/certifications/0xDemo/maturity">Maturity certification package</a></li>
    </ul>
    """
    mechanics_rows = "".join(f"<tr><th>{escape(k)}</th><td>{escape(str(v))}</td></tr>" for k, v in LAUNCH_MECHANICS.items())
    body = f"""
    <section class="hero"><h1>{escape(DEMO_TOKEN['name'])} ({escape(DEMO_TOKEN['symbol'])})</h1><p>{escape(DEMO_TOKEN['description'])}</p><p class="badge">demo token address: 0xDemo</p></section>
    <section class="panel"><h2>Buyer-visible public forms and reports</h2>{public_links}</section>
    <section class="panel"><h2>Confidential filing status</h2><p>{escape(PUBLIC_STATUS['confidential_ownership'])}</p><p>No confidential related/affiliated ownership list details are shown on this buyer page.</p></section>
    <section class="panel"><h2>Launch mechanics summary</h2><p class="badge">{SMART_CONTRACT_NOTICE}</p><table>{mechanics_rows}</table></section>
    """
    return page("Demo token", body)
