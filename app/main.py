import argparse
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.agent.orchestrator import continue_agent_run, run_agent_task
from app.agent.trace_explainer import (
    load_agent_trace,
    render_trace_json,
    render_trace_summary,
    write_decision_trace_markdown,
)
from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.normalizer import NormalizationError, normalize_requirement_file
from app.core.parser import parse_prd
from app.core.reporter import create_bug_report_from_run
from app.core.runner import run_test_script


REPO_ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI scaffold for the Playwright TestOps Agent MVP.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    normalize_cmd = subparsers.add_parser("normalize", help="Normalize free-text requirement notes into parser-compatible PRD markdown.")
    normalize_cmd.add_argument("input_path", nargs="?", help="Shorthand input path for the free-text requirement file.")
    normalize_cmd.add_argument(
        "--input",
        dest="input_flag",
        help="Path to the free-text requirement file. Overrides the positional input when both are provided.",
    )
    normalize_cmd.add_argument(
        "--provider",
        help="Normalization provider to use. Defaults to the configured provider, which remains 'mock' unless changed explicitly.",
    )

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

    agent_run_cmd = subparsers.add_parser("agent-run", help="Run the traceable Agent workflow from a task, PRD, or existing script.")
    agent_run_cmd.add_argument("--input", dest="input_flag", help="Path to a PRD markdown/text file.")
    agent_run_cmd.add_argument("--script", dest="script_path", help="Path to an existing Python test script.")
    agent_run_cmd.add_argument("--task", dest="task_text", help="Free-text test task. Creates a parser-compatible task input when --input is omitted.")
    agent_run_cmd.add_argument("--target-url", help="Target page URL for free-text task inputs.")
    agent_run_cmd.add_argument("--module", help="Module or feature name for Agent trace grouping.")
    agent_run_cmd.add_argument(
        "--constraint",
        dest="constraints",
        action="append",
        default=[],
        help="Task constraint. Can be passed multiple times.",
    )
    agent_run_cmd.add_argument("--agent-run-id", help="Optional deterministic Agent run id for demos or tests.")
    agent_run_cmd.add_argument("--approval-mode", choices=["auto", "manual"], default="auto")
    agent_run_cmd.add_argument("--retrieval-backend", default="file_lexical")
    agent_run_cmd.add_argument("--planning-backend", default="deterministic")

    agent_approve_cmd = subparsers.add_parser("agent-approve", help="Approve or reject a pending Agent gate.")
    agent_approve_cmd.add_argument("--agent-run-id", required=True)
    agent_approve_cmd.add_argument("--gate", choices=["test_plan", "execution", "report"], required=True)
    agent_approve_cmd.add_argument("--decision", choices=["approve", "reject", "approved", "rejected"], required=True)
    agent_approve_cmd.add_argument("--reviewer")
    agent_approve_cmd.add_argument("--comment")

    agent_trace_cmd = subparsers.add_parser("agent-trace", help="Render an Agent trace as summary, JSON, or markdown.")
    agent_trace_cmd.add_argument("--agent-run-id", required=True)
    agent_trace_cmd.add_argument("--format", choices=["summary", "json", "markdown"], default="summary")
    return parser


def _resolve_input_path(input_flag: Optional[str], input_path: Optional[str], command_name: str) -> str:
    resolved = input_flag or input_path
    if not resolved:
        raise SystemExit(f"{command_name} requires an input path. Use '{command_name} <path>' or '{command_name} --input <path>'.")
    return resolved


def _relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "agent_task"


def _format_agent_task_markdown(
    task_text: str,
    target_url: Optional[str] = None,
    module: Optional[str] = None,
    constraints: Optional[list[str]] = None,
) -> str:
    clean_task = task_text.strip()
    clean_module = (module or "").strip()
    clean_target_url = (target_url or "").strip()
    clean_constraints = [item.strip() for item in (constraints or []) if item and item.strip()]
    title = clean_module or "Agent Test Task"
    preconditions = ["Task submitted through Agent CLI", *clean_constraints]

    lines = [
        "# Title",
        f"{title} PRD",
        "",
        "## Feature Name",
        clean_module or clean_task.splitlines()[0][:80] or "Agent Test Task",
        "",
        "## Page URL",
    ]
    if clean_target_url:
        lines.append(clean_target_url)
    lines.extend(
        [
            "",
            "## Preconditions",
            *[f"- {item}" for item in preconditions],
            "",
            "## User Actions",
            f"1. {clean_task}",
            "",
            "## Expected Results",
            "- The described behavior can be verified against the target page.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _write_agent_task_input(
    task_text: str,
    target_url: Optional[str] = None,
    module: Optional[str] = None,
    constraints: Optional[list[str]] = None,
) -> str:
    output_dir = REPO_ROOT / "data" / "api_inputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = _slugify(module or "agent_task")
    output_path = output_dir / f"{timestamp}_{stem}.md"
    output_path.write_text(
        _format_agent_task_markdown(task_text, target_url=target_url, module=module, constraints=constraints),
        encoding="utf-8",
    )
    return _relative_to_repo(output_path)


def _print_agent_result(result: dict[str, object]) -> None:
    for key in (
        "agent_run_id",
        "final_status",
        "script_path",
        "test_plan_path",
        "run_id",
        "run_dir",
        "report_draft_path",
        "trace_path",
    ):
        value = result.get(key)
        if value is not None:
            print(f"{key}: {value}")

    pending_approval = result.get("pending_approval")
    if isinstance(pending_approval, dict):
        print(f"pending_approval: {pending_approval.get('gate')}")


def cmd_normalize(input_path: str, provider_name: Optional[str] = None) -> int:
    try:
        result = normalize_requirement_file(input_path, provider_name=provider_name)
    except NormalizationError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"normalized_output: {_relative_to_repo(result.output_path)}")
    print(f"provider_used: {result.provider_name}")
    print(f"parser_validation_passed: {'yes' if result.parser_validation_passed else 'no'}")
    return 0


def cmd_parse(input_path: str) -> int:
    document = parse_prd(input_path)
    print(json.dumps(asdict(document), indent=2))
    return 0


def cmd_generate(input_path: str) -> int:
    document = parse_prd(input_path)
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points, input_path=input_path)
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


def cmd_agent_run(
    input_path: Optional[str],
    task_text: Optional[str],
    target_url: Optional[str],
    module: Optional[str],
    constraints: list[str],
    approval_mode: str,
    retrieval_backend: str,
    planning_backend: str,
    script_path: Optional[str],
    agent_run_id: Optional[str] = None,
) -> int:
    task_payload: dict[str, object] = {}
    if task_text and task_text.strip():
        task_payload["task_text"] = task_text.strip()
    if target_url:
        task_payload["target_url"] = target_url
    if module:
        task_payload["module"] = module
    if constraints:
        task_payload["constraints"] = constraints

    resolved_input_path = input_path
    if script_path:
        task_payload["script_path"] = script_path
        task_payload["execution_mode"] = "existing_script"
        resolved_input_path = resolved_input_path or script_path
    elif resolved_input_path is None and task_text and task_text.strip():
        resolved_input_path = _write_agent_task_input(
            task_text,
            target_url=target_url,
            module=module,
            constraints=constraints,
        )
        task_payload["generated_input_path"] = resolved_input_path

    if not resolved_input_path:
        raise SystemExit("agent-run requires --input, --script, or non-empty --task.")

    result = run_agent_task(
        resolved_input_path,
        agent_run_id=agent_run_id,
        approval_mode=approval_mode,  # type: ignore[arg-type]
        task=task_payload or None,
        script_path=script_path,
        retrieval_backend=retrieval_backend,
        planning_backend=planning_backend,
    )
    _print_agent_result(result)
    return 0


def cmd_agent_approve(
    agent_run_id: str,
    gate: str,
    decision: str,
    reviewer: Optional[str] = None,
    comment: Optional[str] = None,
) -> int:
    result = continue_agent_run(
        agent_run_id,
        gate=gate,
        decision=decision,
        reviewer=reviewer,
        comment=comment,
    )
    _print_agent_result(result)
    return 0


def cmd_agent_trace(agent_run_id: str, output_format: str = "summary") -> int:
    if output_format == "markdown":
        markdown_path = write_decision_trace_markdown(agent_run_id)
        print(f"decision_trace: {_relative_to_repo(markdown_path)}")
        return 0

    trace = load_agent_trace(agent_run_id)
    if output_format == "json":
        print(render_trace_json(trace), end="")
    else:
        print(render_trace_summary(trace), end="")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "normalize":
        return cmd_normalize(
            _resolve_input_path(args.input_flag, args.input_path, "normalize"),
            provider_name=args.provider,
        )
    if args.command == "parse":
        return cmd_parse(_resolve_input_path(args.input_flag, args.input_path, "parse"))
    if args.command == "generate":
        return cmd_generate(_resolve_input_path(args.input_flag, args.input_path, "generate"))
    if args.command == "run":
        return cmd_run(_resolve_input_path(args.input_flag, args.input_path, "run"))
    if args.command == "report":
        return cmd_report(_resolve_input_path(args.input_flag, args.input_path, "report"))
    if args.command == "agent-run":
        return cmd_agent_run(
            input_path=args.input_flag,
            task_text=args.task_text,
            target_url=args.target_url,
            module=args.module,
            constraints=args.constraints,
            approval_mode=args.approval_mode,
            retrieval_backend=args.retrieval_backend,
            planning_backend=args.planning_backend,
            script_path=args.script_path,
            agent_run_id=args.agent_run_id,
        )
    if args.command == "agent-approve":
        return cmd_agent_approve(
            agent_run_id=args.agent_run_id,
            gate=args.gate,
            decision=args.decision,
            reviewer=args.reviewer,
            comment=args.comment,
        )
    if args.command == "agent-trace":
        return cmd_agent_trace(args.agent_run_id, output_format=args.format)

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
