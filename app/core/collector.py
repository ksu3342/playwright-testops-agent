import json
from pathlib import Path
from typing import Optional


MODULE_DIR = Path(__file__).resolve().parent
APP_DIR = MODULE_DIR.parent
REPO_ROOT = APP_DIR.parent
RUNS_DIR = REPO_ROOT / "data" / "runs"
RUN_DIR_ENV_VAR = "TESTOPS_RUN_DIR"


def _relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def create_run_directory(run_id: str) -> Path:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _discover_capture_artifacts(run_dir: Path) -> dict[str, str]:
    artifact_paths: dict[str, str] = {}

    screenshot_dir = run_dir / "screenshots"
    if screenshot_dir.is_dir():
        screenshot_candidates = sorted(
            [
                path
                for path in screenshot_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
            ],
            key=lambda path: path.as_posix(),
        )
        if screenshot_candidates:
            artifact_paths["screenshot"] = _relative_to_repo(screenshot_candidates[0])

    trace_candidates = sorted(
        [path for path in run_dir.rglob("trace.zip") if path.is_file()],
        key=lambda path: path.as_posix(),
    )
    if trace_candidates:
        artifact_paths["trace"] = _relative_to_repo(trace_candidates[0])

    return artifact_paths


def collect_run_artifacts(
    run_dir: Path,
    summary: dict[str, object],
    command_text: str,
    stdout_text: Optional[str],
    stderr_text: Optional[str],
) -> dict[str, str]:
    command_path = run_dir / "command.txt"
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    summary_path = run_dir / "summary.json"

    command_path.write_text(command_text or "", encoding="utf-8")
    stdout_path.write_text(stdout_text or "", encoding="utf-8")
    stderr_path.write_text(stderr_text or "", encoding="utf-8")

    artifact_paths = {
        "run_dir": _relative_to_repo(run_dir),
        "command": _relative_to_repo(command_path),
        "stdout": _relative_to_repo(stdout_path),
        "stderr": _relative_to_repo(stderr_path),
        "summary": _relative_to_repo(summary_path),
    }
    artifact_paths.update(_discover_capture_artifacts(run_dir))
    summary["artifact_paths"] = artifact_paths
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return artifact_paths


# Artifacts are discovered only when the executed test actually writes them under the run directory.
