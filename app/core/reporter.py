from pathlib import Path

from app.schemas.bugreport_schema import BugReport
from app.schemas.prd_schema import PRDDocument
from app.schemas.testpoint_schema import TestPoint


TEMPLATE_PATH = Path("app/templates/bug_report.md.j2")
OUTPUT_PATH = Path("generated/reports/latest_bug_report.md")


def _render_without_jinja(report: BugReport, test_points: list[TestPoint]) -> str:
    steps = "\n".join(f"- {step}" for step in report.reproduction_steps)
    points = "\n".join(f"- {point.id}: {point.title}" for point in test_points)
    return "\n".join(
        [
            f"# {report.title}",
            "",
            "## Summary",
            report.summary,
            "",
            "## Reproduction Steps",
            steps,
            "",
            "## Observed Result",
            report.observed_result,
            "",
            "## Expected Result",
            report.expected_result,
            "",
            "## Related Test Points",
            points,
            "",
        ]
    )


def build_bug_report(
    document: PRDDocument,
    test_points: list[TestPoint],
    run_status: str,
) -> BugReport:
    """Create a simple interview-friendly bug report placeholder."""
    return BugReport(
        title=f"Placeholder report for {document.title}",
        summary=f"Current run status: {run_status}",
        reproduction_steps=[
            "Review the generated Playwright script",
            "Run the placeholder pipeline",
            "Replace placeholder execution with a real browser run in the next phase",
        ],
        observed_result=f"Pipeline finished with status: {run_status}",
        expected_result="Real execution results should be collected from Playwright.",
    )


def write_bug_report(report: BugReport, test_points: list[TestPoint]) -> Path:
    try:
        from jinja2 import Template

        template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
        rendered = template.render(report=report, test_points=test_points)
    except ImportError:
        rendered = _render_without_jinja(report, test_points)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    return OUTPUT_PATH


# TODO: Build the report from actual failures and artifact paths.
