import argparse

from app.core.collector import collect_run_artifacts
from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.parser import parse_prd
from app.core.reporter import build_bug_report, write_bug_report
from app.core.runner import run_generated_test


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI scaffold for the Playwright TestOps Agent MVP.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_cmd = subparsers.add_parser("parse", help="Parse a simple PRD or page description file.")
    parse_cmd.add_argument("--input", required=True, help="Path to the input PRD markdown/text file.")

    generate_cmd = subparsers.add_parser("generate", help="Generate a placeholder Playwright script.")
    generate_cmd.add_argument("--input", required=True, help="Path to the input PRD markdown/text file.")

    run_cmd = subparsers.add_parser("run", help="Run the placeholder phase-1 pipeline.")
    run_cmd.add_argument("--input", required=True, help="Path to the input PRD markdown/text file.")

    report_cmd = subparsers.add_parser("report", help="Generate a placeholder bug report from the latest run.")
    report_cmd.add_argument("--run-id", default="latest", help="Run id to report on. Only 'latest' is supported now.")
    report_cmd.add_argument(
        "--input",
        default="data/inputs/sample_prd_login.md",
        help="Path to the source PRD markdown/text file.",
    )
    return parser


def cmd_parse(input_path: str) -> int:
    document = parse_prd(input_path)
    print(f"title: {document.title}")
    print(f"summary: {document.summary}")
    return 0


def cmd_generate(input_path: str) -> int:
    document = parse_prd(input_path)
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points)
    print(f"generated_script: {script_path}")
    return 0


def cmd_run(input_path: str) -> int:
    document = parse_prd(input_path)
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points)
    run_result = run_generated_test(str(script_path))
    artifact_path = collect_run_artifacts(run_result)
    print(f"generated_script: {script_path}")
    print(f"run_status: {run_result['status']}")
    print(f"run_artifacts: {artifact_path}")
    return 0


def cmd_report(input_path: str, run_id: str) -> int:
    if run_id != "latest":
        raise SystemExit("Only run-id=latest is supported in the phase-1 scaffold.")
    document = parse_prd(input_path)
    test_points = extract_test_points(document)
    report = build_bug_report(document, test_points, run_status="placeholder_success")
    report_path = write_bug_report(report, test_points)
    print(f"bug_report: {report_path}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "parse":
        return cmd_parse(args.input)
    if args.command == "generate":
        return cmd_generate(args.input)
    if args.command == "run":
        return cmd_run(args.input)
    if args.command == "report":
        return cmd_report(args.input, args.run_id)

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
