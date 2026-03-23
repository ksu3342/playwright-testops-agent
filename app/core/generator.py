import re
from pathlib import Path
from typing import Optional

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


def _render_context(document: PRDDocument, test_points: list[TestPoint]) -> dict[str, object]:
    cases = []
    for test_point in test_points:
        cases.append(
            {
                "id": test_point.id,
                "title": test_point.title,
                "type": test_point.type,
                "function_name": _function_name(test_point),
                "preconditions": test_point.preconditions,
                "step_todos": [_step_todo(step) for step in test_point.steps],
                "expected_result": test_point.expected_result,
                "assertion_todos": _assertion_todos(test_point.expected_result),
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
        "# Missing selectors and unsupported assertions remain TODO comments on purpose.",
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
        if case["step_todos"]:
            for item in case["step_todos"]:
                lines.append(f"    {item}")
        else:
            lines.append("    # TODO: Add safe page interactions for this test point.")
        lines.append("")
        lines.append("    # Expected result from PRD:")
        lines.append(f'    # {case["expected_result"]}')
        for item in case["assertion_todos"]:
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


def generate_test_script(document: PRDDocument, test_points: list[TestPoint]) -> Path:
    """Render a deterministic Playwright pytest-style scaffold from extracted test points."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"test_{_document_slug(document)}_generated.py"
    output_path = OUTPUT_DIR / filename
    rendered = _render_with_template(_render_context(document, test_points))
    output_path.write_text(rendered, encoding="utf-8")
    return OUTPUT_DIR_RELATIVE / filename


# TODO: Support splitting into multiple files only when a single file becomes too large.
