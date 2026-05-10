from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

API_KEY = "dev-audit-key"

VULNERABLE_SOURCE = """
pragma solidity ^0.8.20;

contract Vault {
    mapping(address => uint256) public balances;
    address public owner;

    constructor() { owner = msg.sender; }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 amount = balances[msg.sender];
        (bool ok, ) = msg.sender.call{value: amount}("");
        balances[msg.sender] = 0;
    }

    function adminSweep(address payable to) external {
        require(tx.origin == owner, "not owner");
        to.transfer(address(this).balance);
    }

    function drawWinner(address[] memory users) external view returns (address) {
        return users[block.timestamp % users.length];
    }
}
"""


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(history_path=tmp_path / "history.jsonl"))


def test_auth_required(tmp_path: Path):
    response = client(tmp_path).post("/audit", json={"source": VULNERABLE_SOURCE, "preview": True})
    assert response.status_code == 401
    assert response.json()["detail"] == "missing_or_invalid_api_key"


def test_preview_is_free_and_hides_detailed_findings(tmp_path: Path):
    c = client(tmp_path)
    response = c.post("/audit", headers={"X-API-Key": API_KEY}, json={"contract_name": "Vault", "source": VULNERABLE_SOURCE, "preview": True})

    assert response.status_code == 200
    body = response.json()
    assert body["preview"] is True
    assert body["pricing"]["amount_cents"] == 0
    assert body["severity_summary"]["High"] >= 1
    assert body["severity_summary"]["Critical"] >= 1
    assert body["findings"] == []
    assert body["compliance"]["details_hidden"] is True


def test_paid_audit_requires_x402_payment_header(tmp_path: Path):
    response = client(tmp_path).post("/audit", headers={"X-API-Key": API_KEY}, json={"source": VULNERABLE_SOURCE})

    assert response.status_code == 402
    body = response.json()
    assert body["x402Version"] == 1
    assert body["error"] == "X-PAYMENT header is required"
    requirement = body["accepts"][0]
    assert requirement["network"] == "base"
    assert requirement["asset"] == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    assert requirement["maxAmountRequired"] == "2000000"


def test_paid_audit_returns_ranked_findings_reports_and_report_formats(tmp_path: Path):
    c = client(tmp_path)
    response = c.post(
        "/audit",
        headers={"X-API-Key": API_KEY, "X-PAYMENT": "demo-paid"},
        json={"contract_name": "Vault", "source": VULNERABLE_SOURCE},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["contract_name"] == "Vault"
    assert len(body["model_reports"]) == 2
    assert body["analysis_engine"]["ast_indexer"] is True
    assert body["analysis_engine"]["bounded_symbolic_trace"] is True
    assert body["structural_summary"]["functions_indexed"] >= 4
    assert body["findings"][0]["severity"] == "Critical"
    titles = {finding["title"] for finding in body["findings"]}
    assert "External call before state update" in titles
    assert "Authorization uses tx.origin" in titles
    assert "Miner/validator-influenced time dependency" in titles
    assert any(finding["swc_id"] == "SWC-107" for finding in body["findings"])
    assert "```solidity" in body["markdown_report"]
    assert body["pdf_report"].startswith("PDF-ish Smart Contract Audit Report")

    audit_id = body["audit_id"]
    md = c.get(f"/reports/{audit_id}.md", headers={"X-API-Key": API_KEY})
    assert md.status_code == 200
    assert "Smart Contract Audit: Vault" in md.text
    html = c.get(f"/reports/{audit_id}.html", headers={"X-API-Key": API_KEY})
    assert html.status_code == 200
    assert "External call before state update" in html.text


def test_multi_file_import_resolution_and_history_dashboard(tmp_path: Path):
    c = client(tmp_path)
    files = [
        {"path": "lib/Ownable.sol", "content": "pragma solidity ^0.8.20; contract Ownable { address owner; }"},
        {"path": "contracts/Token.sol", "content": "pragma solidity ^0.8.20; import '../lib/Ownable.sol'; contract Token { function mint(address to, uint256 amount) public { } }"},
    ]
    response = c.post(
        "/audit",
        headers={"X-API-Key": API_KEY, "X-PAYMENT": "demo-paid"},
        json={"contract_name": "Token", "files": files},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["audit_id"].startswith("aud_")
    assert any(f["title"] == "Sensitive function may be missing access control" for f in body["findings"])

    history = c.get("/history", headers={"X-API-Key": API_KEY})
    assert history.status_code == 200
    assert history.json()["audits"][0]["contract_name"] == "Token"
    dashboard = c.get("/dashboard", headers={"X-API-Key": API_KEY})
    assert dashboard.status_code == 200
    assert "Smart Contract Auditor" in dashboard.text


def test_gas_and_compliance_checks_for_erc20_shape(tmp_path: Path):
    source = """
    pragma solidity ^0.8.20;
    contract DemoToken {
        event Transfer(address indexed from, address indexed to, uint256 value);
        event Approval(address indexed owner, address indexed spender, uint256 value);
        function totalSupply() external view returns (uint256) { return 0; }
        function balanceOf(address who) external view returns (uint256) { return 0; }
        function transfer(address to, uint256 amount) external returns (bool) { return true; }
        function allowance(address a, address b) external view returns (uint256) { return 0; }
        function approve(address spender, uint256 amount) external returns (bool) { return true; }
        function transferFrom(address from, address to, uint256 amount) external returns (bool) { return true; }
        function names(string memory label) external pure returns (string memory) { return label; }
        function sum(uint256[] memory values) public pure returns (uint256 out) { for (uint256 i = 0; i < values.length; i++) { out += values[i]; } }
    }
    """
    response = client(tmp_path).post(
        "/audit",
        headers={"X-API-Key": API_KEY, "X-PAYMENT": "demo-paid"},
        json={"contract_name": "DemoToken", "source": source},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["compliance"]["ERC-20"]["status"] == "appears_compliant"
    assert any(item["title"] == "Cache array length in loops" for item in body["gas_optimizations"])
    assert any(item["title"] == "Use calldata for external dynamic arguments" for item in body["gas_optimizations"])


def test_ast_dataflow_trace_explains_reentrancy_order(tmp_path: Path):
    c = client(tmp_path)
    response = c.post(
        "/audit",
        headers={"X-API-Key": API_KEY, "X-PAYMENT": "demo-paid"},
        json={"contract_name": "Vault", "source": VULNERABLE_SOURCE},
    )

    assert response.status_code == 200
    body = response.json()
    trace = next(item for item in body["structural_summary"]["trace_functions_sample"] if item["function"] == "withdraw")
    op_types = [op["type"] for op in trace["operations"]]
    assert "external_interaction" in op_types
    assert "state_write" in op_types
    interaction_line = next(op["line"] for op in trace["operations"] if op["type"] == "external_interaction")
    write_line = next(op["line"] for op in trace["operations"] if op["type"] == "state_write" and op.get("state_variable") == "balances")
    assert interaction_line < write_line
    reentrancy = next(f for f in body["findings"] if f["title"] == "External call before state update")
    assert reentrancy["source"].startswith("synthesizer")
    assert "AST-lite" in reentrancy["description"]
