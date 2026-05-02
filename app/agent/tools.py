from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional

from app.core.collector import REPO_ROOT, RUNS_DIR
from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.normalizer import normalize_requirement_file
from app.core.parser import parse_prd
from app.core.reporter import create_bug_report_from_run
from app.core.runner import run_test_script


def _relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()

    repo_candidate = (REPO_ROOT / candidate).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return candidate.resolve()


def _resolve_run_reference(run_reference: str) -> Path:
    candidate = Path(run_reference)
    if candidate.is_absolute():
        return candidate.resolve()

    repo_candidate = (REPO_ROOT / candidate).resolve()
    if repo_candidate.exists():
        return repo_candidate

    run_id_candidate = (RUNS_DIR / run_reference).resolve()
    if run_id_candidate.exists():
        return run_id_candidate

    return repo_candidate


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, Path):
        return _relative_to_repo(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def normalize_requirement(input_path: str, provider_name: Optional[str] = None) -> dict[str, Any]:
    result = normalize_requirement_file(input_path, provider_name=provider_name)
    return {
        "resolved_input_path": _relative_to_repo(_resolve_repo_path(input_path)),
        "output_path": _relative_to_repo(result.output_path),
        "provider_used": result.provider_name,
        "parser_validation_passed": result.parser_validation_passed,
        "missing_sections": result.missing_sections,
        "normalized_markdown": result.normalized_markdown,
    }


def parse_requirement(input_path: str) -> dict[str, Any]:
    document = parse_prd(input_path)
    return {
        "resolved_input_path": _relative_to_repo(_resolve_repo_path(input_path)),
        "document": _json_safe(document),
    }


def generate_test(input_path: str) -> dict[str, Any]:
    document = parse_prd(input_path)
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points, input_path=input_path)
    return {
        "resolved_input_path": _relative_to_repo(_resolve_repo_path(input_path)),
        "document": _json_safe(document),
        "test_points": _json_safe(test_points),
        "test_point_count": len(test_points),
        "script_path": script_path.as_posix(),
    }


def run_test(input_path: str) -> dict[str, Any]:
    return _json_safe(run_test_script(input_path))


def create_report(input_path: str) -> dict[str, Any]:
    return _json_safe(create_bug_report_from_run(input_path))


def get_run_summary(run_reference: str) -> dict[str, Any]:
    run_dir = _resolve_run_reference(run_reference)
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"Run summary.json was not found: {_relative_to_repo(summary_path)}")

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Run summary.json is not a JSON object: {_relative_to_repo(summary_path)}")

    return {
        "run_id": str(payload.get("run_id", run_dir.name)),
        "run_dir": _relative_to_repo(run_dir),
        "summary": _json_safe(payload),
    }


def get_artifacts(run_reference: str) -> dict[str, Any]:
    summary_result = get_run_summary(run_reference)
    summary = summary_result["summary"]
    artifact_paths = summary.get("artifact_paths") if isinstance(summary, dict) else {}
    if not isinstance(artifact_paths, dict):
        artifact_paths = {}

    return {
        "run_id": summary_result["run_id"],
        "run_dir": summary_result["run_dir"],
        "artifact_paths": _json_safe(artifact_paths),
        "lineage": _json_safe(summary.get("lineage")) if isinstance(summary, dict) else None,
        "report_path": summary.get("report_path") if isinstance(summary, dict) else None,
    }


TOOL_REGISTRY = {
    "normalize_requirement": normalize_requirement,
    "parse_requirement": parse_requirement,
    "generate_test": generate_test,
    "run_test": run_test,
    "create_report": create_report,
    "get_run_summary": get_run_summary,
    "get_artifacts": get_artifacts,
}
