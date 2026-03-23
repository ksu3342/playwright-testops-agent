import json
from pathlib import Path
from typing import Optional


MODULE_DIR = Path(__file__).resolve().parent
APP_DIR = MODULE_DIR.parent
REPO_ROOT = APP_DIR.parent
RUNS_DIR = REPO_ROOT / "data" / "runs"


def _relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def create_run_directory(run_id: str) -> Path:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


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
    summary["artifact_paths"] = artifact_paths
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return artifact_paths


# TODO: Add screenshot and trace artifact storage only when execution really produces them.
