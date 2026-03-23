import argparse
import json
from dataclasses import asdict
from typing import Optional

from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.parser import parse_prd
from app.core.reporter import create_bug_report_from_run
from app.core.runner import run_test_script


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI scaffold for the Playwright TestOps Agent MVP.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_cmd = subparsers.add_parser("parse", help="Parse a simple PRD or page description file.")
    parse_cmd.add_argument("input_path", nargs="?", help="Shorthand input path for the PRD markdown/text file.")
    parse_cmd.add_argument(
        "--input",
        dest="input_flag",
        help="Path to the input PRD markdown/text file. Overrides the positional input when both are provided.",
    )

    generate_cmd = subparsers.add_parser("generate", help="Parse input, extract test points, and generate script files.")
    generate_cmd.add_argument("input_path", nargs="?", help="Shorthand input path for the PRD markdown/text file.")
    generate_cmd.add_argument(
        "--input",
        dest="input_flag",
        help="Path to the input PRD markdown/text file. Overrides the positional input when both are provided.",
    )

    run_cmd = subparsers.add_parser("run", help="Run a local test script and collect honest execution artifacts.")
    run_cmd.add_argument("input_path", nargs="?", help="Shorthand path to the target test script.")
    run_cmd.add_argument(
        "--input",
        dest="input_flag",
        help="Path to the target test script. Overrides the positional input when both are provided.",
    )

    report_cmd = subparsers.add_parser("report", help="Generate a bug report draft from a Phase 5 run directory.")
    report_cmd.add_argument("input_path", nargs="?", help="Shorthand path to the target run directory.")
    report_cmd.add_argument(
        "--input",
        dest="input_flag",
        help="Path to the target run directory. Overrides the positional input when both are provided.",
    )
    return parser


def _resolve_input_path(input_flag: Optional[str], input_path: Optional[str], command_name: str) -> str:
    resolved = input_flag or input_path
    if not resolved:
        raise SystemExit(f"{command_name} requires an input path. Use '{command_name} <path>' or '{command_name} --input <path>'.")
    return resolved


def cmd_parse(input_path: str) -> int:
    document = parse_prd(input_path)
    print(json.dumps(asdict(document), indent=2))
    return 0


def cmd_generate(input_path: str) -> int:
    document = parse_prd(input_path)
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points)
    print(f"Extracted {len(test_points)} test point(s):")
    for test_point in test_points:
        print(f"- {test_point.id} [{test_point.type}] {test_point.title}")
    print("Generated script file(s):")
    print(f"- {script_path.as_posix()}")
    print("Execution is not part of this milestone. Generated files may still contain TODO comments for missing selectors or assertions.")
    return 0


def cmd_run(input_path: str) -> int:
    run_result = run_test_script(input_path)
    print(f"Run status: {run_result['status']}")
    print(f"Run directory: {run_result['run_dir']}")
    print(f"Target script: {run_result['target_script']}")
    if run_result.get("reason"):
        print(f"Reason: {run_result['reason']}")
    return 0


def cmd_report(input_path: str) -> int:
    report_result = create_bug_report_from_run(input_path)
    print(f"Run status: {report_result['status']}")
    print(f"Run directory: {report_result['run_dir']}")
    print(f"Target script: {report_result['target_script']}")
    print(f"Report generated: {'yes' if report_result['generated'] else 'no'}")
    if report_result["generated"]:
        print(f"Report path: {report_result['report_path']}")
    if report_result.get("reason"):
        print(f"Reason: {report_result['reason']}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "parse":
        return cmd_parse(_resolve_input_path(args.input_flag, args.input_path, "parse"))
    if args.command == "generate":
        return cmd_generate(_resolve_input_path(args.input_flag, args.input_path, "generate"))
    if args.command == "run":
        return cmd_run(_resolve_input_path(args.input_flag, args.input_path, "run"))
    if args.command == "report":
        return cmd_report(_resolve_input_path(args.input_flag, args.input_path, "report"))

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
