
import re
from fastapi.testclient import TestClient

from app.main import PUBLIC_PATHS, SMART_CONTRACT_NOTICE, app
from app.requirements_matrix import REQUIREMENTS, validate_matrix

client = TestClient(app)

REQUIRED_ENDPOINTS = [
    "/",
    "/health",
    "/ready",
    "/token/create",
    "/forms/demo/offering-statement",
    "/forms/demo/purchaser-information",
    "/reports/0xDemo/semiannual/2026-H1",
    "/certifications/0xDemo/maturity",
    "/token/0xDemo",
]


def test_health_and_ready():
    assert client.get("/health").status_code == 200
    ready = client.get("/ready")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["matrix_loaded"] is True
    assert payload["requirement_count"] == 80
    assert payload["requirement_range"] == ["R-001", "R-080"]


def test_required_routes_are_public_and_available():
    for path in REQUIRED_ENDPOINTS:
        response = client.get(path)
        assert response.status_code == 200, path


def test_home_links_core_flow_and_forms():
    body = client.get("/").text
    assert "/token/create" in body
    assert "/forms/demo/offering-statement" in body
    assert "/forms/demo/purchaser-information" in body
    assert "/token/0xDemo" in body


def test_requirement_matrix_is_complete_and_well_formed():
    assert validate_matrix() == []
    assert [req.id for req in REQUIREMENTS] == [f"R-{i:03d}" for i in range(1, 81)]
    by_id = {req.id: req for req in REQUIREMENTS}
    assert len(by_id) == 80
    for req in REQUIREMENTS:
        assert req.title
        assert req.source_file.endswith("hr3633-engrossed-house.txt")
        assert re.search(r"\d+", req.source_lines)
        assert req.bill_section
        assert req.ui_page
        assert req.completion_mode
        assert req.excerpt


def test_every_requirement_has_rendered_surface():
    rendered = set(re.findall(r"data-requirement-id=\"(R-\d{3})\"", client.get("/token/create").text))
    expected = {req.id for req in REQUIREMENTS}
    assert expected <= rendered


def test_statutory_pages_render_citation_panels_and_chips():
    for path in ["/token/create", "/forms/demo/offering-statement", "/forms/demo/purchaser-information", "/reports/0xDemo/semiannual/2026-H1", "/certifications/0xDemo/maturity"]:
        body = client.get(path).text
        assert "CLARITY Act references" in body, path
        assert "citation-chip" in body, path
        assert "hr3633-engrossed-house.txt" in body, path
        assert "lines" in body, path
        assert "Citation drawer / exact local-source excerpt" in body or "Completed section" in body, path


def test_smart_contract_launch_fields_are_not_fake_clarity_controls():
    body = client.get("/launch/mechanics").text + client.get("/token/create").text
    assert SMART_CONTRACT_NOTICE in body
    assert "Simulation only" in body or "fake/no onchain write" in body


def test_hosted_public_forms_include_answers_json_exports_hashes_and_citations():
    for path in ["/forms/demo/offering-statement", "/forms/demo/purchaser-information", "/reports/0xDemo/semiannual/2026-H1", "/certifications/0xDemo/maturity"]:
        body = client.get(path).text
        assert "Completed section" in body
        assert "JSON export" in body
        assert "sha256:" in body
        assert "CLARITY Act references" in body
    assert client.get("/forms/demo/offering-statement.json").json()["content_hash"].startswith("sha256:")
    assert client.get("/forms/demo/purchaser-information.json").json()["content_hash"].startswith("sha256:")


def test_token_page_links_buyer_visible_public_forms():
    body = client.get("/token/0xDemo").text
    assert "/forms/demo/offering-statement" in body
    assert "/forms/demo/purchaser-information" in body
    assert "/reports/0xDemo/semiannual/2026-H1" in body
    assert "/certifications/0xDemo/maturity" in body


def test_public_pages_do_not_leak_confidential_ownership():
    for path in PUBLIC_PATHS:
        body = client.get(path).text
        assert "Confidential Founder Wallet" not in body, path
        assert "0xConfidential" not in body, path
    token_page = client.get("/token/0xDemo").text
    assert "Confidential ownership list completed; not public by default." in token_page


def test_external_affirmations_do_not_replace_user_fillable_form_content():
    body = client.get("/token/create").text
    assert "I affirm this external action/status is completed outside this demo platform" in body
    # User-completable §4B rows render actual textareas/answers, not mere affirmations.
    for rid in ["R-027", "R-028", "R-029", "R-034", "R-040", "R-051"]:
        assert f'data-requirement-id="{rid}"' in body
    assert client.get("/forms/demo/offering-statement").text.count("Completed section") >= 1


def test_static_security_hygiene_for_public_app():
    body = client.get("/token/create").text + client.get("/launch/mechanics").text
    assert "PRIVATE_KEY" not in body
    assert "BANKR_API_KEY" not in body
    assert "VERCEL_TOKEN" not in body
    assert "No real SEC filing" in body or "no onchain write" in body
