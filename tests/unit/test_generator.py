import json
from pathlib import Path

from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.parser import parse_prd


def test_login_input_generates_script_under_generated_tests() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    output_path = generate_test_script(document, test_points)
    content = output_path.read_text(encoding="utf-8")

    assert output_path == Path("generated/tests/test_login_generated.py")
    assert output_path.exists()
    assert "TP-001" in content
    assert "User Login happy path works as described" in content
    assert "page.goto" in content
    assert "sync_playwright" in content
    assert "import uvicorn" in content
    assert "from demo_app.main import app" in content
    assert "threading.Thread(target=server.run, daemon=True)" in content
    assert "server.should_exit = True" in content
    assert "subprocess.Popen" not in content
    assert "DEMO_SERVER_COMMAND" not in content
    assert "REUSE_EXISTING_DEMO_SERVER" not in content
    assert "pytest-playwright" not in content
    assert '# selector-contract: login.email_input -> login-email-input' in content
    assert 'login_email_input = page.get_by_test_id("login-email-input")' in content
    assert '# selector-contract: login.password_input -> login-password-input' in content
    assert 'login_password_input = page.get_by_test_id("login-password-input")' in content
    assert '# selector-contract: login.submit_button -> login-submit-button' in content
    assert 'login_submit_button = page.get_by_test_id("login-submit-button")' in content
    assert '# selector-contract: dashboard.heading -> dashboard-heading' in content
    assert '# selector-contract: login.inline_error -> login-inline-error' in content
    assert '# test-fixture: login.valid_email -> demo@example.com' in content
    assert "valid_email = 'demo@example.com'" in content
    assert '# test-fixture: login.valid_password -> password123' in content
    assert "valid_password = 'password123'" in content
    assert 'owned_base_url = f"http://{DEFAULT_DEMO_HOST}:{demo_port}"' in content
    assert 'config = uvicorn.Config(' in content
    assert 'thread = threading.Thread(target=server.run, daemon=True)' in content
    assert 'server.should_exit = True' in content
    assert 'subprocess.Popen' not in content
    assert 'DEMO_SERVER_COMMAND' not in content
    assert 'REUSE_EXISTING_DEMO_SERVER' not in content
    assert "Locate the relevant input selector" not in content
    assert "Locate the relevant button selector" not in content
    assert "TODO" not in content
    assert "<VALID_EMAIL>" not in content
    assert "<VALID_PASSWORD>" not in content
    assert "#email" not in content
    assert "#password" not in content
    assert "SELECTOR_CONTRACT_MISSING" not in content


def test_search_input_generates_script_without_invented_selectors() -> None:
    document = parse_prd("data/inputs/sample_prd_search.md")
    test_points = extract_test_points(document)
    output_path = generate_test_script(document, test_points)
    content = output_path.read_text(encoding="utf-8")

    assert output_path == Path("generated/tests/test_search_generated.py")
    assert output_path.exists()
    assert "TP-002" in content
    assert "Empty state is shown when no result matches the keyword" in content
    assert '# selector-contract: search.input -> search-input' in content
    assert 'search_input = page.get_by_test_id("search-input")' in content
    assert '# selector-contract: search.submit_button -> search-submit-button' in content
    assert 'search_submit_button = page.get_by_test_id("search-submit-button")' in content
    assert '# selector-contract: search.results_list -> search-results-list' in content
    assert '# selector-contract: search.result_item -> search-result-item' in content
    assert '# selector-contract: search.empty_state -> search-empty-state' in content
    assert "Locate the relevant input selector" not in content
    assert "Locate the relevant button selector" not in content
    assert "TODO" in content
    assert "#email" not in content
    assert "#password" not in content
    assert "#login-button" not in content
    assert "input[name='q']" not in content
    assert "SELECTOR_CONTRACT_MISSING" not in content


def test_generator_marks_missing_selector_contract_entries_with_blocked_marker(tmp_path: Path) -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    contract_payload = json.loads(Path("data/contracts/demo_app_selectors.json").read_text(encoding="utf-8"))
    del contract_payload["selectors"]["login.email_input"]
    contract_path = tmp_path / "demo_app_selectors.json"
    contract_path.write_text(json.dumps(contract_payload, indent=2), encoding="utf-8")

    output_path = generate_test_script(document, test_points, selector_contract_path=contract_path)
    content = output_path.read_text(encoding="utf-8")

    assert "# SELECTOR_CONTRACT_MISSING: login.email_input" in content
    assert "selector contract does not define semantic key `login.email_input`" in content
