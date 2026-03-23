import json
import re
from pathlib import Path
from typing import Optional

from app.core.collector import REPO_ROOT


REPORTS_DIR = REPO_ROOT / "generated" / "reports"
REPORTS_DIR_RELATIVE = Path("generated/reports")


def _relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve_run_dir(run_dir_path: str) -> Path:
    candidate = Path(run_dir_path)
    if candidate.is_absolute():
        return candidate.resolve()

    repo_candidate = (REPO_ROOT / candidate).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return candidate.resolve()


def _resolve_artifact_path(run_dir: Path, artifact_reference: Optional[str], default_name: str) -> Path:
    if artifact_reference:
        candidate = Path(artifact_reference)
        if candidate.is_absolute():
            return candidate.resolve()

        repo_candidate = (REPO_ROOT / candidate).resolve()
        if repo_candidate.exists():
            return repo_candidate

    return (run_dir / default_name).resolve()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _should_generate_bug_report(status: str) -> tuple[bool, str]:
    if status == "failed":
        return True, "Failed run artifacts support a bug report draft."
    if status == "blocked":
        return False, "Run status is blocked. A normal product bug report is not generated because execution was not actually ready."
    if status == "passed":
        return False, "Run status is passed. No bug report draft is generated for successful execution."
    if status == "environment_error":
        return False, "Run status is environment_error. This is treated as an environment/setup issue, not a normal product defect."
    return False, f"Run status '{status}' is not eligible for a normal product bug report."


def _select_evidence_excerpt(stdout_text: str, stderr_text: str) -> str:
    combined_lines = [line.rstrip() for line in f"{stderr_text}\n{stdout_text}".splitlines() if line.strip()]
    interesting_tokens = ["AssertionError", "FAILED", "ERROR", "Traceback", "E       ", "ModuleNotFoundError", "ImportError"]
    interesting_lines = [line for line in combined_lines if any(token in line for token in interesting_tokens)]
    selected_lines = interesting_lines[:8] if interesting_lines else combined_lines[:8]
    if not selected_lines:
        return "No stdout or stderr evidence was captured."
    return "\n".join(selected_lines)


def _probable_cause_hypothesis(stdout_text: str, stderr_text: str) -> str:
    combined_output = f"{stdout_text}\n{stderr_text}"
    if "AssertionError" in combined_output or re.search(r"\bassert\b", combined_output):
        return (
            "the executed test encountered an assertion mismatch. Current artifacts do not prove whether the product behavior is wrong "
            "or whether the scripted expectation is wrong."
        )
    runtime_markers = ["TypeError", "AttributeError", "NameError", "ValueError", "RuntimeError"]
    if any(marker in combined_output for marker in runtime_markers):
        return (
            "the executed script hit a runtime error in test code or application code. Current artifacts are insufficient to confirm "
            "the exact failing component."
        )
    return (
        "the run failed during execution, but the current artifacts do not confirm a single root cause. More targeted runtime evidence "
        "would be needed before making a stronger claim."
    )


def _build_report_markdown(
    summary: dict[str, object],
    run_dir: Path,
    command_text: str,
    stdout_text: str,
    stderr_text: str,
) -> str:
    run_id = str(summary.get("run_id", "unknown_run"))
    target_script = str(summary.get("target_script", "unknown_target"))
    status = str(summary.get("status", "unknown"))
    return_code = summary.get("return_code")
    reason = str(summary.get("reason", "No summary reason was captured."))
    artifact_paths = summary.get("artifact_paths") if isinstance(summary.get("artifact_paths"), dict) else {}
    evidence_excerpt = _select_evidence_excerpt(stdout_text, stderr_text)
    hypothesis = _probable_cause_hypothesis(stdout_text, stderr_text)

    notes = [
        "This draft is generated only from Phase 5 run artifacts.",
        "Probable cause is a hypothesis, not a confirmed root cause.",
        "No screenshots, browser traces, or DOM snapshots were collected in this phase.",
    ]
    if target_script.startswith("tests/assets/"):
        notes.append(
            "This run targets a local pytest asset used to validate the pipeline, so the draft demonstrates reporting behavior rather than a confirmed product defect."
        )

    lines = [
        f"# Bug Report Draft: {Path(target_script).name} failed",
        "",
        "## Run ID",
        f"`{run_id}`",
        "",
        "## Execution Status",
        f"- Status: `{status}`",
        f"- Return code: `{return_code}`",
        f"- Summary reason: {reason}",
        "",
        "## Target Script",
        f"`{target_script}`",
        "",
        "## Environment / Context",
        f"- Run directory: `{_relative_to_repo(run_dir)}`",
        f"- Command: `{command_text or 'Not available from current run artifacts.'}`",
        f"- Start time: `{summary.get('start_time', 'Not available')}`",
        f"- End time: `{summary.get('end_time', 'Not available')}`",
        f"- Duration seconds: `{summary.get('duration_seconds', 'Not available')}`",
        f"- Execution readiness: `{summary.get('execution_readiness', 'Not available')}`",
        "",
        "## Preconditions",
        "Not available from current Phase 5 run artifacts.",
        "",
        "## Steps to Reproduce",
        "1. From the repository root, run the recorded command shown in the Environment / Context section.",
        f"2. Inspect the captured artifacts under `{_relative_to_repo(run_dir)}`.",
        "3. Compare the observed failure output below against the expected successful execution state.",
        "",
        "## Expected Result",
        "The target script should complete with execution status `passed` and return code `0`.",
        "",
        "## Actual Result",
        f"The run finished with status `{status}` and return code `{return_code}`.",
        f"Summary reason: {reason}",
        "",
        "```text",
        evidence_excerpt,
        "```",
        "",
        "## Evidence",
        f"- Summary artifact: `{artifact_paths.get('summary', _relative_to_repo(run_dir / 'summary.json'))}`",
        f"- Command artifact: `{artifact_paths.get('command', _relative_to_repo(run_dir / 'command.txt'))}`",
        f"- Stdout artifact: `{artifact_paths.get('stdout', _relative_to_repo(run_dir / 'stdout.txt'))}`",
        f"- Stderr artifact: `{artifact_paths.get('stderr', _relative_to_repo(run_dir / 'stderr.txt'))}`",
        "- No screenshots or browser traces were collected in this phase.",
        "",
        "## Probable Cause Hypothesis",
        f"Hypothesis: {hypothesis}",
        "",
        "## Notes / Limitations",
    ]
    lines.extend(f"- {note}" for note in notes)
    lines.append("")
    return "\n".join(lines)


def create_bug_report_from_run(run_dir_path: str) -> dict[str, object]:
    run_dir = _resolve_run_dir(run_dir_path)
    result = {
        "generated": False,
        "report_path": None,
        "run_dir": _relative_to_repo(run_dir),
        "run_id": "unknown_run",
        "status": "environment_error",
        "target_script": "unknown_target",
        "reason": "Run directory was not found.",
    }

    if not run_dir.exists():
        return result

    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        result["reason"] = "Run summary.json was not found in the target run directory."
        return result

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        result["reason"] = "Run summary.json could not be parsed."
        return result

    run_id = str(summary.get("run_id", run_dir.name))
    status = str(summary.get("status", "environment_error"))
    target_script = str(summary.get("target_script", "unknown_target"))
    should_generate, reason = _should_generate_bug_report(status)

    result.update(
        {
            "run_id": run_id,
            "status": status,
            "target_script": target_script,
            "reason": reason,
        }
    )

    if not should_generate:
        return result

    artifact_paths = summary.get("artifact_paths") if isinstance(summary.get("artifact_paths"), dict) else {}
    command_text = _read_text(_resolve_artifact_path(run_dir, artifact_paths.get("command"), "command.txt"))
    stdout_text = _read_text(_resolve_artifact_path(run_dir, artifact_paths.get("stdout"), "stdout.txt"))
    stderr_text = _read_text(_resolve_artifact_path(run_dir, artifact_paths.get("stderr"), "stderr.txt"))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"bug_report_{run_id}.md"
    markdown = _build_report_markdown(summary, run_dir, command_text, stdout_text, stderr_text)
    report_path.write_text(markdown, encoding="utf-8")

    result.update(
        {
            "generated": True,
            "report_path": (REPORTS_DIR_RELATIVE / report_path.name).as_posix(),
            "reason": "Failed run artifacts were converted into a bug report draft.",
        }
    )
    return result


# TODO: Add richer reproduction context only when execution artifacts capture it explicitly.
