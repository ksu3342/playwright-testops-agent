import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.collector import REPO_ROOT, create_run_directory, collect_run_artifacts
from app.core.selector_contract import SELECTOR_CONTRACT_MISSING_MARKER


INCOMPLETE_MARKERS = [
    "TODO",
    "<...SELECTOR...>",
    "generated test expects a pytest-playwright style `page` fixture",
    "Missing selectors and unsupported assertions remain TODO comments on purpose.",
]
ENVIRONMENT_ERROR_MARKERS = [
    "ModuleNotFoundError",
    "No module named",
    "ImportError",
    "fixture 'page' not found",
    "playwright",
]
SELECTOR_CONTRACT_MISSING_PATTERN = re.compile(
    rf"{re.escape(SELECTOR_CONTRACT_MISSING_MARKER)}:\s*([A-Za-z0-9_.-]+)"
)


def _slugify(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value.lower()).strip("_") or "run"


def _resolve_target_script(script_path: str) -> Path:
    candidate = Path(script_path)
    if candidate.is_absolute():
        return candidate.resolve()

    repo_candidate = (REPO_ROOT / candidate).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return candidate.resolve()


def _relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _build_run_id(target_script: Path) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}_{_slugify(target_script.stem)}"


def _missing_selector_contract_keys(script_text: str) -> list[str]:
    matches = SELECTOR_CONTRACT_MISSING_PATTERN.findall(script_text)
    seen: set[str] = set()
    ordered: list[str] = []
    for semantic_key in matches:
        if semantic_key not in seen:
            seen.add(semantic_key)
            ordered.append(semantic_key)
    return ordered


def _readiness_status(script_text: str) -> tuple[Optional[str], Optional[str]]:
    missing_selectors = _missing_selector_contract_keys(script_text)
    if missing_selectors:
        joined = ", ".join(missing_selectors)
        reason = f"Script is blocked because the selector contract is missing required selector(s): {joined}."
        return reason, "blocked_by_selector_contract"
    for marker in INCOMPLETE_MARKERS:
        if marker in script_text:
            reason = f"Script contains incomplete implementation markers ({marker}) and is not ready for honest execution."
            return reason, "blocked_by_incomplete_markers"
    return None, None


def _classify_execution_result(return_code: int, stdout_text: str, stderr_text: str) -> tuple[str, str]:
    combined_output = "\n".join([stdout_text, stderr_text])
    if return_code == 0:
        return "passed", "Execution completed successfully."
    if any(marker in combined_output for marker in ENVIRONMENT_ERROR_MARKERS):
        return "environment_error", "Execution could not proceed because required runtime support is missing."
    return "failed", "Execution ran but reported a failing test or runtime error."


def run_test_script(script_path: str) -> dict[str, object]:
    target_script = _resolve_target_script(script_path)
    run_id = _build_run_id(target_script)
    run_dir = create_run_directory(run_id)
    start_time = datetime.now(timezone.utc)

    if not target_script.exists():
        summary = {
            "run_id": run_id,
            "target_script": _relative_to_repo(target_script),
            "status": "environment_error",
            "reason": "Target script was not found.",
            "command": "",
            "start_time": start_time.isoformat(),
            "end_time": start_time.isoformat(),
            "duration_seconds": 0.0,
            "return_code": None,
            "execution_readiness": "missing_target",
            "notes": ["Provide a valid script path before running the pipeline."],
        }
        artifact_paths = collect_run_artifacts(run_dir, summary, "", "", "")
        summary["run_dir"] = artifact_paths["run_dir"]
        return summary

    script_text = target_script.read_text(encoding="utf-8")
    readiness_reason, execution_readiness = _readiness_status(script_text)
    command = [sys.executable, "-m", "pytest", _relative_to_repo(target_script), "-q"]
    command_text = subprocess.list2cmdline(command)

    if readiness_reason:
        end_time = datetime.now(timezone.utc)
        summary = {
            "run_id": run_id,
            "target_script": _relative_to_repo(target_script),
            "status": "blocked",
            "reason": readiness_reason,
            "command": command_text,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round((end_time - start_time).total_seconds(), 6),
            "return_code": None,
            "execution_readiness": execution_readiness,
            "notes": ["Execution was skipped on purpose to avoid pretending incomplete scaffolds are runnable."],
        }
        artifact_paths = collect_run_artifacts(run_dir, summary, command_text, "", "")
        summary["run_dir"] = artifact_paths["run_dir"]
        return summary

    try:
        completed = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        end_time = datetime.now(timezone.utc)
        status, reason = _classify_execution_result(completed.returncode, completed.stdout, completed.stderr)
        summary = {
            "run_id": run_id,
            "target_script": _relative_to_repo(target_script),
            "status": status,
            "reason": reason,
            "command": command_text,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round((end_time - start_time).total_seconds(), 6),
            "return_code": completed.returncode,
            "execution_readiness": "ready",
            "notes": [],
        }
        artifact_paths = collect_run_artifacts(run_dir, summary, command_text, completed.stdout, completed.stderr)
        summary["run_dir"] = artifact_paths["run_dir"]
        return summary
    except OSError as exc:
        end_time = datetime.now(timezone.utc)
        summary = {
            "run_id": run_id,
            "target_script": _relative_to_repo(target_script),
            "status": "environment_error",
            "reason": f"Execution could not start: {exc}",
            "command": command_text,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round((end_time - start_time).total_seconds(), 6),
            "return_code": None,
            "execution_readiness": "ready",
            "notes": ["Check the local Python/pytest environment before retrying."],
        }
        artifact_paths = collect_run_artifacts(run_dir, summary, command_text, "", str(exc))
        summary["run_dir"] = artifact_paths["run_dir"]
        return summary


# TODO: Add real browser execution only when generated Playwright scripts are honestly ready to run.
