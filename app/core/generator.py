import re
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


def _login_step_lines(contract: SelectorContract) -> list[str]:
    lines: list[str] = []
    lines.extend(_selector_lines(contract, "login.email_input"))
    if contract.get("login.email_input") is not None:
        lines.append("# TODO: Replace <VALID_EMAIL> with a verified fixture before execution-ready runs.")
        lines.append('login_email_input.fill("<VALID_EMAIL>")')
    lines.append("")
    lines.extend(_selector_lines(contract, "login.password_input"))
    if contract.get("login.password_input") is not None:
        lines.append("# TODO: Replace <VALID_PASSWORD> with a verified fixture before execution-ready runs.")
        lines.append('login_password_input.fill("<VALID_PASSWORD>")')
    lines.append("")
    lines.extend(_selector_lines(contract, "login.submit_button", action_line="{locator}.click()"))
    return lines


def _login_assertion_lines(contract: SelectorContract, expected_result: str) -> list[str]:
    lines: list[str] = []
    lines.extend(_selector_lines(contract, "dashboard.heading"))
    lines.append(f"# TODO: Add an honest post-login assertion for: {expected_result}")
    lines.append("")
    lines.extend(_selector_lines(contract, "login.inline_error"))
    lines.append("# TODO: Add an honest negative assertion that login_inline_error is not visible for valid credentials.")
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
    if flow_key == "/login":
        return _login_step_lines(contract)
    if flow_key == "/search" and test_point.type == "negative_path":
        return _search_negative_step_lines(contract)
    if flow_key == "/search":
        return _search_happy_step_lines(contract)
    return [_step_todo(step) for step in test_point.steps]


def _assertion_lines(document: PRDDocument, test_point: TestPoint, contract: SelectorContract) -> list[str]:
    flow_key = _flow_key(document)
    if flow_key == "/login":
        return _login_assertion_lines(contract, test_point.expected_result)
    if flow_key == "/search" and test_point.type == "negative_path":
        return _search_negative_assertion_lines(contract, test_point.expected_result)
    if flow_key == "/search":
        return _search_happy_assertion_lines(contract, test_point.expected_result)
    return _assertion_todos(test_point.expected_result)


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


def generate_test_script(
    document: PRDDocument,
    test_points: list[TestPoint],
    selector_contract_path: Optional[Path] = None,
) -> Path:
    """Render a deterministic Playwright pytest-style scaffold from extracted test points."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"test_{_document_slug(document)}_generated.py"
    output_path = OUTPUT_DIR / filename
    rendered = _render_with_template(_render_context(document, test_points, load_selector_contract(selector_contract_path)))
    output_path.write_text(rendered, encoding="utf-8")
    return OUTPUT_DIR_RELATIVE / filename


# TODO: Support splitting into multiple files only when a single file becomes too large.
