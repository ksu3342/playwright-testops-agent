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
from app.rag.retriever import retrieve_testing_context as retrieve_local_testing_context


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


def _document_from_parse_result(parse_result: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not parse_result:
        return {}
    document = parse_result.get("document")
    return document if isinstance(document, dict) else {}


def analyze_information_needs(
    input_path: str,
    parse_result: Optional[dict[str, Any]] = None,
    task: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    document = _document_from_parse_result(parse_result)
    if not document:
        document = _json_safe(parse_prd(input_path))

    task = task or {}
    missing_task_fields: list[str] = []
    reason_codes: list[str] = []
    required_context_types = {
        "product_doc",
        "test_guideline",
        "selector_contract",
        "test_data_contract",
    }

    page_url = document.get("page_url") or task.get("target_url")
    feature_name = document.get("feature_name") or task.get("module")
    expected_results = document.get("expected_results")
    raw_text = str(document.get("raw_text", ""))
    task_text = str(task.get("task_text", ""))
    constraints = task.get("constraints") if isinstance(task.get("constraints"), list) else []
    combined_text = " ".join([raw_text, task_text, " ".join(str(item) for item in constraints)]).lower()

    if not feature_name:
        missing_task_fields.append("module")
        reason_codes.append("missing_module_or_feature")
    if not page_url:
        missing_task_fields.append("target_url")
        reason_codes.append("missing_target_url")
    if not expected_results:
        missing_task_fields.append("expected_results")
        reason_codes.append("missing_expected_results")

    history_markers = ("history", "previous", "regression", "failed before", "失败", "历史", "回归")
    bug_markers = ("bug", "defect", "failure", "failed", "缺陷", "故障", "报错")
    if any(marker in combined_text for marker in history_markers):
        required_context_types.add("run_history")
        reason_codes.append("historical_run_context_requested")
    if any(marker in combined_text for marker in bug_markers):
        required_context_types.add("bug_report")
        reason_codes.append("defect_context_requested")

    if "selector" in combined_text or "locator" in combined_text:
        reason_codes.append("selector_context_requested")
    if "data" in combined_text or "fixture" in combined_text or "测试数据" in combined_text:
        reason_codes.append("test_data_context_requested")

    retrieval_query_parts = [
        str(feature_name or ""),
        str(page_url or ""),
        raw_text,
        task_text,
        " ".join(str(item) for item in constraints),
    ]
    retrieval_query = " ".join(part for part in retrieval_query_parts if part).strip()
    if not retrieval_query:
        retrieval_query = input_path

    return {
        "required_context_types": sorted(required_context_types),
        "reason_codes": sorted(set(reason_codes)),
        "retrieval_query": retrieval_query,
        "missing_task_fields": missing_task_fields,
    }


def retrieve_testing_context(
    input_path: str,
    max_results: int = 5,
    source_types: Optional[list[str]] = None,
    query: Optional[str] = None,
) -> dict[str, Any]:
    return _json_safe(
        retrieve_local_testing_context(
            input_path=input_path,
            query=query,
            max_results=max_results,
            source_types=source_types,
        )
    )


def _source_path_from_context(testing_context: Optional[dict[str, Any]], source_type: str) -> Optional[Path]:
    if not testing_context:
        return None

    results = testing_context.get("results")
    if not isinstance(results, list):
        return None

    for result in results:
        if not isinstance(result, dict):
            continue
        if result.get("source_type") != source_type:
            continue
        source_path = result.get("source_path")
        if isinstance(source_path, str):
            candidate = _resolve_repo_path(source_path)
            if candidate.is_file():
                return candidate
    return None


def _context_source_paths(testing_context: Optional[dict[str, Any]]) -> list[str]:
    if not testing_context:
        return []

    results = testing_context.get("results")
    if not isinstance(results, list):
        return []

    source_paths: list[str] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        source_path = result.get("source_path")
        if isinstance(source_path, str):
            source_paths.append(source_path)
    return source_paths


def _retrieved_sources(testing_context: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if not testing_context:
        return []

    results = testing_context.get("results")
    if not isinstance(results, list):
        return []

    sources: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        source_path = result.get("source_path")
        source_type = result.get("source_type")
        if isinstance(source_path, str) and isinstance(source_type, str):
            sources.append(
                {
                    "source_type": source_type,
                    "source_path": source_path,
                    "score": result.get("score"),
                }
            )
    return sources


def _has_source_type(test_plan: dict[str, Any], source_type: str) -> bool:
    retrieved_sources = test_plan.get("retrieved_sources")
    if not isinstance(retrieved_sources, list):
        return False
    return any(isinstance(source, dict) and source.get("source_type") == source_type for source in retrieved_sources)


def draft_test_plan(
    input_path: str,
    testing_context: Optional[dict[str, Any]] = None,
    information_needs: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    document = parse_prd(input_path)
    test_points = extract_test_points(document)
    retrieved_sources = _retrieved_sources(testing_context)
    retrieved_source_paths = [source["source_path"] for source in retrieved_sources]

    missing_inputs = list(document.missing_sections)
    if not any(source["source_type"] == "selector_contract" for source in retrieved_sources):
        missing_inputs.append("selector_contract")
    if not test_points:
        missing_inputs.append("test_cases")

    risks: list[str] = []
    if document.missing_sections:
        risks.append("requirement_missing_sections")
    if "selector_contract" in missing_inputs:
        risks.append("selector_contract_missing")
    if not any(source["source_type"] == "test_data_contract" for source in retrieved_sources):
        risks.append("test_data_contract_not_retrieved")

    return {
        "input_path": _relative_to_repo(_resolve_repo_path(input_path)),
        "feature_name": document.feature_name,
        "page_url": document.page_url,
        "planning_strategy": "deterministic_scaffold",
        "information_needs": information_needs or {},
        "retrieved_source_paths": retrieved_source_paths,
        "retrieved_sources": retrieved_sources,
        "test_cases": [
            {
                "id": test_point.id,
                "title": test_point.title,
                "type": test_point.type,
                "preconditions": test_point.preconditions,
                "steps": test_point.steps,
                "expected_result": test_point.expected_result,
                "source_sections": test_point.source_sections,
                "rationale": test_point.rationale,
            }
            for test_point in test_points
        ],
        "risks": risks,
        "missing_inputs": missing_inputs,
    }


def validate_test_plan(test_plan: dict[str, Any]) -> dict[str, Any]:
    missing_inputs: list[str] = []

    if not test_plan.get("feature_name"):
        missing_inputs.append("feature_name")
    if not test_plan.get("page_url"):
        missing_inputs.append("page_url")

    test_cases = test_plan.get("test_cases")
    if not isinstance(test_cases, list) or not test_cases:
        missing_inputs.append("test_cases")

    if not _has_source_type(test_plan, "selector_contract"):
        missing_inputs.append("selector_contract")

    status = "blocked" if missing_inputs else "passed"
    return {
        "status": status,
        "missing_inputs": missing_inputs,
        "can_generate": status == "passed",
        "reason": "test_plan_ready" if status == "passed" else "test_plan_missing_required_inputs",
    }


def generate_test(input_path: str, testing_context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    document = parse_prd(input_path)
    test_points = extract_test_points(document)
    selector_contract_path = _source_path_from_context(testing_context, "selector_contract")
    test_data_contract_path = _source_path_from_context(testing_context, "test_data_contract")
    script_path = generate_test_script(
        document,
        test_points,
        selector_contract_path=selector_contract_path,
        test_data_contract_path=test_data_contract_path,
        input_path=input_path,
    )
    return {
        "resolved_input_path": _relative_to_repo(_resolve_repo_path(input_path)),
        "document": _json_safe(document),
        "test_points": _json_safe(test_points),
        "test_point_count": len(test_points),
        "script_path": script_path.as_posix(),
        "context_source_paths": _context_source_paths(testing_context),
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


def collect_run_evidence(run_reference: str) -> dict[str, Any]:
    return {
        "queried_tools": ["get_run_summary", "get_artifacts"],
        "run_summary": get_run_summary(run_reference),
        "queried_artifacts": get_artifacts(run_reference),
    }


TOOL_REGISTRY = {
    "normalize_requirement": normalize_requirement,
    "parse_requirement": parse_requirement,
    "analyze_information_needs": analyze_information_needs,
    "retrieve_testing_context": retrieve_testing_context,
    "draft_test_plan": draft_test_plan,
    "validate_test_plan": validate_test_plan,
    "generate_test": generate_test,
    "run_test": run_test,
    "create_report": create_report,
    "get_run_summary": get_run_summary,
    "get_artifacts": get_artifacts,
    "collect_run_evidence": collect_run_evidence,
}
