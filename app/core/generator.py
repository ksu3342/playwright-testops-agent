import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.selector_contract import (
    SELECTOR_CONTRACT_MISSING_MARKER,
    SelectorContract,
    load_selector_contract,
)
from app.schemas.prd_schema import PRDDocument
from app.schemas.testpoint_schema import TestPoint


MODULE_DIR = Path(__file__).resolve().parent
APP_DIR = MODULE_DIR.parent
REPO_ROOT = APP_DIR.parent
TEMPLATE_PATH = APP_DIR / "templates" / "test_script.j2"
OUTPUT_DIR = REPO_ROOT / "generated" / "tests"
OUTPUT_DIR_RELATIVE = Path("generated/tests")
DEFAULT_TEST_DATA_CONTRACT_PATH = REPO_ROOT / "data" / "contracts" / "demo_app_test_data.json"


class TestDataContractError(ValueError):
    pass


@dataclass(frozen=True)
class TestDataDefinition:
    semantic_key: str
    value: str

    def source_comment(self) -> str:
        return f"# test-fixture: {self.semantic_key} -> {self.value}"


@dataclass(frozen=True)
class TestDataContract:
    version: int
    app: str
    fixtures: dict[str, TestDataDefinition]

    def get(self, semantic_key: str) -> Optional[TestDataDefinition]:
        return self.fixtures.get(semantic_key)


def _load_json_object(path: Path, label: str) -> dict[str, object]:
    if not path.exists():
        raise TestDataContractError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TestDataContractError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise TestDataContractError(f"{label} root must be a JSON object.")
    return payload


def _build_test_data_definition(semantic_key: str, value: object) -> TestDataDefinition:
    if not isinstance(value, dict):
        raise TestDataContractError(f"Test data entry must be an object: {semantic_key}")

    actual_semantic_key = value.get("semantic_key")
    fixture_value = value.get("value")
    if actual_semantic_key != semantic_key:
        raise TestDataContractError(f"Test data semantic_key mismatch for {semantic_key}.")
    if not isinstance(fixture_value, str) or not fixture_value:
        raise TestDataContractError(f"Test data entry is missing required value for {semantic_key}.")

    return TestDataDefinition(
        semantic_key=semantic_key,
        value=fixture_value,
    )


def load_test_data_contract(path: Optional[Path] = None) -> TestDataContract:
    contract_path = path or DEFAULT_TEST_DATA_CONTRACT_PATH
    payload = _load_json_object(contract_path, "Test data contract")
    fixtures_payload = payload.get("fixtures")
    if not isinstance(fixtures_payload, dict):
        raise TestDataContractError("Test data contract must contain a fixtures object.")

    fixtures = {
        semantic_key: _build_test_data_definition(semantic_key, fixture_data)
        for semantic_key, fixture_data in fixtures_payload.items()
    }

    version = payload.get("version")
    app_name = payload.get("app")
    if not isinstance(version, int):
        raise TestDataContractError("Test data contract version must be an integer.")
    if not isinstance(app_name, str) or not app_name:
        raise TestDataContractError("Test data contract app must be a non-empty string.")

    return TestDataContract(
        version=version,
        app=app_name,
        fixtures=fixtures,
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "generated"


def _document_slug(document: PRDDocument) -> str:
    if document.page_url:
        page_slug = document.page_url.strip().strip("/").split("/")[-1]
        if page_slug:
            return _slugify(page_slug)
    if document.feature_name:
        return _slugify(document.feature_name)
    if document.title:
        return _slugify(document.title)
    return "generated"


def _page_url_expression(document: PRDDocument) -> Optional[str]:
    if not document.page_url:
        return None
    if document.page_url.startswith("http://") or document.page_url.startswith("https://"):
        return repr(document.page_url)
    normalized = "/" + document.page_url.lstrip("/")
    return f'BASE_URL.rstrip("/") + "{normalized}"'


def _function_name(test_point: TestPoint) -> str:
    return f"test_{_slugify(test_point.id)}_{_slugify(test_point.title)}"


def _step_todo(step: str) -> str:
    lowered = step.lower()
    if any(keyword in lowered for keyword in ["enter", "fill", "type"]):
        return f"# TODO: Locate the relevant input selector before implementing: {step}"
    if "click" in lowered:
        return f"# TODO: Locate the relevant button selector before implementing: {step}"
    if "assert" in lowered:
        return f"# TODO: Translate this assertion safely: {step}"
    return f"# TODO: Translate this step safely: {step}"


def _assertion_todos(expected_result: str) -> list[str]:
    lowered = expected_result.lower()
    if "redirect" in lowered:
        return [f"# TODO: Add a safe URL assertion for: {expected_result}"]
    if "visible text" in lowered or "empty state" in lowered or "displayed" in lowered:
        return [f"# TODO: Add a safe visible-text assertion for: {expected_result}"]
    return [f"# TODO: Add a safe assertion for the expected result: {expected_result}"]


def _flow_key(document: PRDDocument) -> str:
    return (document.page_url or "").strip().lower()


def _selector_variable_name(semantic_key: str) -> str:
    return semantic_key.replace(".", "_")


def _selector_lines(
    contract: SelectorContract,
    semantic_key: str,
    action_line: Optional[str] = None,
) -> list[str]:
    selector = contract.get(semantic_key)
    if selector is None:
        return [
            f"# {SELECTOR_CONTRACT_MISSING_MARKER}: {semantic_key}",
            f"# Blocked because the selector contract does not define semantic key `{semantic_key}`.",
        ]

    variable_name = _selector_variable_name(semantic_key)
    lines = [
        selector.source_comment(),
        f"{variable_name} = {selector.locator_expression()}",
    ]
    if action_line:
        lines.append(action_line.format(locator=variable_name))
    return lines


def _search_happy_step_lines(contract: SelectorContract) -> list[str]:
    lines: list[str] = []
    lines.extend(_selector_lines(contract, "search.input"))
    if contract.get("search.input") is not None:
        lines.append("# TODO: Replace <SEARCH_KEYWORD> with a verified keyword fixture before execution-ready runs.")
        lines.append('search_input.fill("<SEARCH_KEYWORD>")')
    lines.append("")
    lines.extend(_selector_lines(contract, "search.submit_button", action_line="{locator}.click()"))
    return lines


def _search_negative_step_lines(contract: SelectorContract) -> list[str]:
    lines: list[str] = []
    lines.extend(_selector_lines(contract, "search.input"))
    if contract.get("search.input") is not None:
        lines.append("# TODO: Replace <NO_MATCH_KEYWORD> with a verified negative fixture before execution-ready runs.")
        lines.append('search_input.fill("<NO_MATCH_KEYWORD>")')
    lines.append("")
    lines.extend(_selector_lines(contract, "search.submit_button", action_line="{locator}.click()"))
    return lines


def _search_happy_assertion_lines(contract: SelectorContract, expected_result: str) -> list[str]:
    lines: list[str] = []
    lines.extend(_selector_lines(contract, "search.results_list"))
    lines.append(f"# TODO: Add an honest results-list assertion for: {expected_result}")
    lines.append("")
    lines.extend(_selector_lines(contract, "search.result_item"))
    lines.append("# TODO: Add an honest assertion about at least one result item becoming visible.")
    return lines


def _search_negative_assertion_lines(contract: SelectorContract, expected_result: str) -> list[str]:
    lines: list[str] = []
    lines.extend(_selector_lines(contract, "search.empty_state"))
    lines.append(f"# TODO: Add an honest empty-state assertion for: {expected_result}")
    return lines


def _step_lines(document: PRDDocument, test_point: TestPoint, contract: SelectorContract) -> list[str]:
    flow_key = _flow_key(document)
    if flow_key == "/search" and test_point.type == "negative_path":
        return _search_negative_step_lines(contract)
    if flow_key == "/search":
        return _search_happy_step_lines(contract)
    return [_step_todo(step) for step in test_point.steps]


def _assertion_lines(document: PRDDocument, test_point: TestPoint, contract: SelectorContract) -> list[str]:
    flow_key = _flow_key(document)
    if flow_key == "/search" and test_point.type == "negative_path":
        return _search_negative_assertion_lines(contract, test_point.expected_result)
    if flow_key == "/search":
        return _search_happy_assertion_lines(contract, test_point.expected_result)
    return _assertion_todos(test_point.expected_result)


def _fixture_assignment_lines(
    test_data_contract: TestDataContract,
    semantic_key: str,
    variable_name: str,
) -> list[str]:
    fixture = test_data_contract.get(semantic_key)
    if fixture is None:
        raise TestDataContractError(f"Test data contract is missing required fixture `{semantic_key}`.")
    return [
        fixture.source_comment(),
        f"{variable_name} = {fixture.value!r}",
    ]


def _render_executable_login_script(
    document: PRDDocument,
    test_point: TestPoint,
    selector_contract: SelectorContract,
    test_data_contract: TestDataContract,
) -> str:
    lines = [
        "import os",
        "import socket",
        "import subprocess",
        "import sys",
        "import time",
        "import urllib.request",
        "from typing import Optional",
        "from pathlib import Path",
        "",
        "import pytest",
        "from playwright.sync_api import sync_playwright",
        "",
        "REPO_ROOT = Path(__file__).resolve().parents[2]",
        'DEFAULT_DEMO_HOST = "127.0.0.1"',
        f'DEFAULT_BASE_URL = os.getenv("BASE_URL", {selector_contract.base_url!r})',
        'SERVER_START_TIMEOUT_SECONDS = float(os.getenv("DEMO_SERVER_START_TIMEOUT_SECONDS", "20"))',
        'REUSE_EXISTING_DEMO_SERVER = os.getenv("REUSE_EXISTING_DEMO_SERVER", "0") == "1"',
        "DEMO_SERVER_COMMAND = [sys.executable, \"-m\", \"demo_app.main\"]",
        "",
        f'# Generated from: {document.title or "Untitled PRD"}',
        f'# Feature: {document.feature_name or "Unknown Feature"}',
        f'# Page URL: {document.page_url or "Not provided"}',
        "# This generated test is executable for the demo login happy path.",
        "# By default it owns its demo server process and port to avoid reusing an unstable external localhost:3000 server.",
        "",
        "",
        "def _login_url(base_url: str) -> str:",
        '    return base_url.rstrip("/") + "/login"',
        "",
        "",
        "def _pick_free_port() -> int:",
        "    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:",
        "        sock.bind((DEFAULT_DEMO_HOST, 0))",
        "        return int(sock.getsockname()[1])",
        "",
        "",
        "def _is_login_page_reachable(base_url: str) -> bool:",
        "    try:",
        "        with urllib.request.urlopen(_login_url(base_url), timeout=1) as response:",
            "            return response.status == 200",
        "    except Exception:",
        "        return False",
        "",
        "",
        "def _wait_for_login_page(base_url: str, process: Optional[subprocess.Popen] = None) -> None:",
        "    deadline = time.time() + SERVER_START_TIMEOUT_SECONDS",
        "    last_error: Optional[Exception] = None",
        "    while time.time() < deadline:",
        "        if process is not None and process.poll() is not None:",
        '            raise RuntimeError("Demo app process exited before /login became ready.")',
        "        try:",
        "            with urllib.request.urlopen(_login_url(base_url), timeout=1) as response:",
        "                if response.status == 200:",
        "                    return",
        "        except Exception as exc:",
        "            last_error = exc",
        "            time.sleep(0.25)",
        '    raise RuntimeError(f"Demo app did not become ready at {_login_url(base_url)}: {last_error}")',
        "",
        "",
        '@pytest.fixture(scope="module")',
        "def demo_server() -> str:",
        "    if REUSE_EXISTING_DEMO_SERVER:",
        "        if not _is_login_page_reachable(DEFAULT_BASE_URL):",
        '            raise RuntimeError(f"REUSE_EXISTING_DEMO_SERVER=1 but {_login_url(DEFAULT_BASE_URL)} is not reachable.")',
        "        yield DEFAULT_BASE_URL",
        "        return",
        "",
        "    demo_port = _pick_free_port()",
        '    owned_base_url = f"http://{DEFAULT_DEMO_HOST}:{demo_port}"',
        "    server_env = dict(os.environ)",
        '    server_env["DEMO_APP_PORT"] = str(demo_port)',
        "    process = subprocess.Popen(",
        "        DEMO_SERVER_COMMAND,",
        "        cwd=str(REPO_ROOT),",
        "        env=server_env,",
        "        stdout=subprocess.DEVNULL,",
        "        stderr=subprocess.DEVNULL,",
        "    )",
        "    try:",
        "        _wait_for_login_page(owned_base_url, process=process)",
        "        yield owned_base_url",
        "    finally:",
        "        if process.poll() is None:",
            "            process.terminate()",
            "            try:",
                "                process.wait(timeout=10)",
        "            except subprocess.TimeoutExpired:",
        "                process.kill()",
        "                process.wait(timeout=5)",
        "",
        "",
        f"def {_function_name(test_point)}(demo_server: str) -> None:",
        f'    """Source test point: {test_point.id} - {test_point.title}"""',
        f"    # Source test point type: {test_point.type}",
        f'    # Source sections: {", ".join(test_point.source_sections)}',
        f"    # Rationale: {test_point.rationale}",
        "    with sync_playwright() as playwright:",
        "        browser = playwright.chromium.launch(headless=True)",
        "        try:",
        '            target_url = demo_server.rstrip("/") + "/login"',
        '            expected_dashboard_url = demo_server.rstrip("/") + "/dashboard"',
        '            expected_dashboard_heading_text = "Demo Dashboard"',
        '            page = browser.new_page()',
        '            page.goto(target_url, wait_until="domcontentloaded")',
        "",
        "            # Preconditions from PRD:",
    ]

    if test_point.preconditions:
        lines.extend([f"            # - {item}" for item in test_point.preconditions])
    else:
        lines.append("            # - None provided")

    lines.extend(
        [
            "",
            "            # Steps translated deterministically from the PRD:",
        ]
    )
    lines.extend([f"            {item}" for item in _selector_lines(selector_contract, "login.email_input")])
    if selector_contract.get("login.email_input") is not None:
        lines.extend([f"            {item}" for item in _fixture_assignment_lines(test_data_contract, "login.valid_email", "valid_email")])
        lines.append("            login_email_input.fill(valid_email)")
    lines.append("")
    lines.extend([f"            {item}" for item in _selector_lines(selector_contract, "login.password_input")])
    if selector_contract.get("login.password_input") is not None:
        lines.extend([f"            {item}" for item in _fixture_assignment_lines(test_data_contract, "login.valid_password", "valid_password")])
        lines.append("            login_password_input.fill(valid_password)")
    lines.append("")
    lines.extend([f"            {item}" for item in _selector_lines(selector_contract, "login.submit_button", action_line="{locator}.click()")])
    lines.extend(
        [
            "",
            "            # Expected result from PRD:",
            f"            # {test_point.expected_result}",
        ]
    )
    lines.extend([f"            {item}" for item in _selector_lines(selector_contract, "dashboard.heading")])
    lines.extend(
        [
            "            page.wait_for_url(expected_dashboard_url)",
            '            dashboard_heading.wait_for(state="visible")',
            "            assert page.url.rstrip('/') == expected_dashboard_url",
            "            assert dashboard_heading.inner_text() == expected_dashboard_heading_text",
            "",
        ]
    )
    lines.extend([f"            {item}" for item in _selector_lines(selector_contract, "login.inline_error")])
    if selector_contract.get("login.inline_error") is not None:
        lines.append("            assert login_inline_error.count() == 0")
    lines.extend(
        [
            "        finally:",
            "            browser.close()",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _render_context(document: PRDDocument, test_points: list[TestPoint], contract: SelectorContract) -> dict[str, object]:
    cases = []
    for test_point in test_points:
        cases.append(
            {
                "id": test_point.id,
                "title": test_point.title,
                "type": test_point.type,
                "function_name": _function_name(test_point),
                "preconditions": test_point.preconditions,
                "step_lines": _step_lines(document, test_point, contract),
                "expected_result": test_point.expected_result,
                "assertion_lines": _assertion_lines(document, test_point, contract),
                "source_sections": test_point.source_sections,
                "rationale": test_point.rationale,
                "page_url_expression": _page_url_expression(document),
            }
        )
    return {
        "document_title": document.title or "Untitled PRD",
        "feature_name": document.feature_name or "Unknown Feature",
        "page_url": document.page_url or "Not provided",
        "test_cases": cases,
    }


def _render_without_jinja(context: dict[str, object]) -> str:
    lines = [
        "import os",
        "import pytest",
        "",
        'playwright_sync_api = pytest.importorskip("playwright.sync_api")',
        "Page = playwright_sync_api.Page",
        "",
        'BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")',
        "",
        f'# Generated from: {context["document_title"]}',
        f'# Feature: {context["feature_name"]}',
        f'# Page URL: {context["page_url"]}',
        "# This scaffold is intentionally conservative.",
        "# Unsupported assertions and placeholder data remain TODO comments on purpose.",
        "",
    ]

    for case in context["test_cases"]:
        case = dict(case)
        lines.append(f'def {case["function_name"]}(page: Page) -> None:')
        lines.append(f'    """Source test point: {case["id"]} - {case["title"]}"""')
        lines.append("    # TODO: This generated test expects a pytest-playwright style `page` fixture.")
        lines.append(f'    # Source test point type: {case["type"]}')
        lines.append(f'    # Source sections: {", ".join(case["source_sections"])}')
        lines.append(f'    # Rationale: {case["rationale"]}')
        if case["page_url_expression"]:
            lines.append(f'    target_url = {case["page_url_expression"]}')
            lines.append("    page.goto(target_url)")
        else:
            lines.append("    # TODO: Add a concrete page URL before opening the page.")
        lines.append("")
        lines.append("    # Preconditions from PRD:")
        if case["preconditions"]:
            for item in case["preconditions"]:
                lines.append(f"    # - {item}")
        else:
            lines.append("    # - None provided")
        lines.append("")
        lines.append("    # Steps translated conservatively from the PRD:")
        if case["step_lines"]:
            for item in case["step_lines"]:
                lines.append(f"    {item}")
        else:
            lines.append("    # TODO: Add safe page interactions for this test point.")
        lines.append("")
        lines.append("    # Expected result from PRD:")
        lines.append(f'    # {case["expected_result"]}')
        for item in case["assertion_lines"]:
            lines.append(f"    {item}")
        lines.append("")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_with_template(context: dict[str, object]) -> str:
    try:
        from jinja2 import Template
    except ImportError:
        return _render_without_jinja(context)

    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.render(**context).rstrip() + "\n"


def _should_render_executable_login(document: PRDDocument, test_points: list[TestPoint]) -> bool:
    return _flow_key(document) == "/login" and len(test_points) == 1 and test_points[0].type == "happy_path"


def generate_test_script(
    document: PRDDocument,
    test_points: list[TestPoint],
    selector_contract_path: Optional[Path] = None,
    test_data_contract_path: Optional[Path] = None,
) -> Path:
    """Render a deterministic Playwright scaffold or an executable login happy-path test."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"test_{_document_slug(document)}_generated.py"
    output_path = OUTPUT_DIR / filename

    selector_contract = load_selector_contract(selector_contract_path)
    if _should_render_executable_login(document, test_points):
        test_data_contract = load_test_data_contract(test_data_contract_path)
        rendered = _render_executable_login_script(document, test_points[0], selector_contract, test_data_contract)
    else:
        rendered = _render_with_template(_render_context(document, test_points, selector_contract))

    output_path.write_text(rendered, encoding="utf-8")
    return OUTPUT_DIR_RELATIVE / filename


# TODO: Support splitting into multiple files only when a single file becomes too large.
