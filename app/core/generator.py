from pathlib import Path

from app.schemas.prd_schema import PRDDocument
from app.schemas.testpoint_schema import TestPoint


TEMPLATE_PATH = Path("app/templates/test_script.j2")
OUTPUT_PATH = Path("generated/tests/generated_test.py")


def _render_without_jinja(title: str, test_points: list[TestPoint]) -> str:
    point_lines = "\n".join(f"    # {point.id} - {point.title}" for point in test_points)
    return f'''from playwright.sync_api import sync_playwright


def run() -> None:
    """
    Placeholder generated Playwright script for: {title}
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://example.com")
        page.screenshot(path="data/runs/placeholder_screenshot.png")
        browser.close()


if __name__ == "__main__":
    # Placeholder test points:
{point_lines}
    run()
'''


def generate_test_script(document: PRDDocument, test_points: list[TestPoint]) -> Path:
    """Render a placeholder Playwright script from a tiny template."""
    try:
        from jinja2 import Template

        template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
        rendered = template.render(title=document.title, test_points=test_points)
    except ImportError:
        rendered = _render_without_jinja(document.title, test_points)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    return OUTPUT_PATH


# TODO: Support multiple generated files and richer step rendering.
