from app.core.extractor import extract_test_points
from app.core.parser import parse_prd
from app.core.reporter import build_bug_report


def test_build_bug_report_returns_placeholder_summary() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    report = build_bug_report(document, test_points, run_status="placeholder_success")
    assert "placeholder_success" in report.summary
