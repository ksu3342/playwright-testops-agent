from app.core.collector import collect_run_artifacts
from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.parser import parse_prd
from app.core.reporter import build_bug_report, write_bug_report
from app.core.runner import run_generated_test


def test_pipeline_placeholder_flow() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points)
    run_result = run_generated_test(str(script_path))
    artifact_path = collect_run_artifacts(run_result)
    report = build_bug_report(document, test_points, run_result["status"])
    report_path = write_bug_report(report, test_points)

    assert script_path.exists()
    assert artifact_path.exists()
    assert report_path.exists()
