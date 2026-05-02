from pathlib import Path
import json

import pytest

from app.agent.tools import (
    TOOL_REGISTRY,
    PlanningError,
    analyze_information_needs,
    collect_run_evidence,
    create_report,
    draft_test_plan,
    generate_test,
    generate_test_from_plan,
    get_langchain_tools,
    get_artifacts,
    get_run_summary,
    prepare_existing_script_execution,
    parse_requirement,
    retrieve_testing_context,
    run_test,
    validate_test_plan,
)
from app.llm.base import BaseLLMProvider, LLMResponse


class StaticPlannerProvider(BaseLLMProvider):
    def __init__(self, content: str) -> None:
        self.content = content

    def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(content=self.content)


def test_agent_tool_registry_exposes_expected_tools() -> None:
    assert {
        "normalize_requirement",
        "parse_requirement",
        "analyze_information_needs",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
        "prepare_existing_script_execution",
        "generate_test",
        "generate_test_from_plan",
        "run_test",
        "create_report",
        "get_run_summary",
        "get_artifacts",
        "collect_run_evidence",
    }.issubset(TOOL_REGISTRY)


def test_parse_and_generate_tools_return_serializable_payloads() -> None:
    parse_result = parse_requirement("data/inputs/sample_prd_login.md")

    assert parse_result["document"]["feature_name"] == "User Login"
    assert parse_result["document"]["missing_sections"] == []

    generate_result = generate_test("data/inputs/sample_prd_login.md")

    assert generate_result["test_point_count"] == 1
    assert generate_result["test_points"][0]["id"] == "TP-001"
    assert generate_result["script_path"] == "generated/tests/test_login_generated.py"
    assert Path(generate_result["script_path"]).exists()


def test_retrieval_tool_returns_context_for_generation() -> None:
    retrieval_result = retrieve_testing_context(
        "data/inputs/sample_prd_login.md",
        max_results=5,
        source_types=["selector_contract", "test_data_contract", "product_doc"],
    )

    assert retrieval_result["result_count"] >= 3
    assert retrieval_result["retrieval_backend"] == "file_lexical"
    assert retrieval_result["retrieval_implementation"] == "deterministic_file_lexical"
    assert "data/contracts/demo_app_selectors.json" in [
        item["source_path"] for item in retrieval_result["results"]
    ]

    generate_result = generate_test(
        "data/inputs/sample_prd_login.md",
        testing_context=retrieval_result,
    )

    assert "data/contracts/demo_app_selectors.json" in generate_result["context_source_paths"]
    assert generate_result["script_path"] == "generated/tests/test_login_generated.py"


def test_draft_and_validate_test_plan_tools_return_reviewable_payload() -> None:
    information_needs = analyze_information_needs("data/inputs/sample_prd_login.md")
    retrieval_result = retrieve_testing_context(
        "data/inputs/sample_prd_login.md",
        max_results=5,
        source_types=information_needs["required_context_types"],
        query=information_needs["retrieval_query"],
    )
    test_plan = draft_test_plan(
        "data/inputs/sample_prd_login.md",
        testing_context=retrieval_result,
        information_needs=information_needs,
    )
    validation = validate_test_plan(test_plan)

    assert test_plan["feature_name"] == "User Login"
    assert test_plan["page_url"] == "/login"
    assert test_plan["planning_strategy"] == "deterministic_scaffold"
    assert test_plan["planning_backend"] == "deterministic"
    assert test_plan["planning_implementation"] == "deterministic_test_plan_scaffold"
    assert "selector_contract" in information_needs["required_context_types"]
    assert test_plan["test_cases"][0]["id"] == "TP-001"
    assert "data/contracts/demo_app_selectors.json" in test_plan["retrieved_source_paths"]
    assert validation == {
        "status": "passed",
        "missing_inputs": [],
        "can_generate": True,
        "reason": "test_plan_ready",
    }


def test_generate_test_from_plan_uses_reviewed_cases_and_context() -> None:
    information_needs = analyze_information_needs("data/inputs/sample_prd_login.md")
    retrieval_result = retrieve_testing_context(
        "data/inputs/sample_prd_login.md",
        max_results=5,
        source_types=information_needs["required_context_types"],
        query=information_needs["retrieval_query"],
    )
    test_plan = draft_test_plan(
        "data/inputs/sample_prd_login.md",
        testing_context=retrieval_result,
        information_needs=information_needs,
    )
    test_plan["test_cases"][0]["id"] = "TP-PLAN-001"
    test_plan["test_cases"][0]["title"] = "Reviewed login happy path"

    generate_result = generate_test_from_plan(
        "data/inputs/sample_prd_login.md",
        test_plan,
        testing_context=retrieval_result,
    )

    assert generate_result["generation_mode"] == "test_plan"
    assert generate_result["test_point_count"] == 1
    assert generate_result["test_plan_case_count"] == 1
    assert generate_result["test_points"][0]["id"] == "TP-PLAN-001"
    assert generate_result["test_points"][0]["title"] == "Reviewed login happy path"
    assert "data/contracts/demo_app_selectors.json" in generate_result["context_source_paths"]
    assert "data/contracts/demo_app_test_data.json" in generate_result["context_source_paths"]


def test_llm_assisted_test_plan_uses_reviewable_json_without_model_owned_sources() -> None:
    information_needs = analyze_information_needs("data/inputs/sample_prd_login.md")
    retrieval_result = retrieve_testing_context(
        "data/inputs/sample_prd_login.md",
        max_results=5,
        source_types=information_needs["required_context_types"],
        query=information_needs["retrieval_query"],
    )
    provider_payload = {
        "feature_name": "User Login",
        "page_url": "/login",
        "retrieved_sources": [],
        "test_cases": [
            {
                "id": "TP-LLM-001",
                "title": "Review login happy path with retrieved contracts",
                "type": "happy_path",
                "preconditions": ["Selector and fixture contracts have been retrieved"],
                "steps": ["Open /login", "Submit valid credentials", "Check dashboard redirect"],
                "expected_result": "The user reaches the dashboard without blocking validation.",
                "source_sections": ["llm_assisted_plan"],
                "rationale": "Covers the main login task using retrieved context as evidence.",
            }
        ],
        "risks": ["llm_plan_requires_human_review"],
        "missing_inputs": [],
    }

    test_plan = draft_test_plan(
        "data/inputs/sample_prd_login.md",
        testing_context=retrieval_result,
        information_needs=information_needs,
        planning_backend="llm_assisted",
        planner_provider_name="static",
        planner_provider=StaticPlannerProvider(json.dumps(provider_payload)),
    )

    assert test_plan["planning_strategy"] == "llm_assisted_reviewable_plan"
    assert test_plan["planning_backend"] == "llm_assisted"
    assert test_plan["planning_implementation"] == "llm_assisted_reviewable_json"
    assert test_plan["planner_provider"] == "static"
    assert test_plan["test_cases"][0]["id"] == "TP-LLM-001"
    assert "data/contracts/demo_app_selectors.json" in test_plan["retrieved_source_paths"]
    assert test_plan["retrieved_sources"]


def test_llm_assisted_test_plan_fails_on_invalid_json() -> None:
    with pytest.raises(PlanningError, match="invalid JSON"):
        draft_test_plan(
            "data/inputs/sample_prd_login.md",
            planning_backend="llm_assisted",
            planner_provider=StaticPlannerProvider("not json"),
        )


def test_llm_assisted_test_plan_fails_on_missing_required_field() -> None:
    with pytest.raises(PlanningError, match="missing required field: test_cases"):
        draft_test_plan(
            "data/inputs/sample_prd_login.md",
            planning_backend="llm_assisted",
            planner_provider=StaticPlannerProvider(
                json.dumps(
                    {
                        "feature_name": "User Login",
                        "page_url": "/login",
                        "retrieved_sources": [],
                        "risks": [],
                        "missing_inputs": [],
                    }
                )
            ),
        )


def test_draft_test_plan_rejects_invalid_planning_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported planning backend"):
        draft_test_plan("data/inputs/sample_prd_login.md", planning_backend="not_a_backend")


def test_validate_test_plan_blocks_missing_required_review_inputs() -> None:
    validation = validate_test_plan(
        {
            "feature_name": "",
            "page_url": None,
            "test_cases": [],
            "retrieved_sources": [],
        }
    )

    assert validation["status"] == "blocked"
    assert validation["can_generate"] is False
    assert validation["missing_inputs"] == [
        "feature_name",
        "page_url",
        "test_cases",
        "selector_contract",
        "retrieved_source_paths",
    ]


def test_validate_test_plan_blocks_incomplete_case_contract() -> None:
    validation = validate_test_plan(
        {
            "feature_name": "User Login",
            "page_url": "/login",
            "retrieved_source_paths": ["data/contracts/demo_app_selectors.json"],
            "retrieved_sources": [
                {"source_type": "selector_contract", "source_path": "data/contracts/demo_app_selectors.json"}
            ],
            "test_cases": [
                {
                    "id": "TP-001",
                    "title": "Missing expected result",
                    "type": "happy_path",
                    "steps": ["Open /login"],
                    "source_sections": ["Acceptance Criteria"],
                    "rationale": "Covers login.",
                }
            ],
        }
    )

    assert validation["status"] == "blocked"
    assert validation["can_generate"] is False
    assert "test_cases[0].expected_result" in validation["missing_inputs"]


def test_prepare_existing_script_execution_returns_reviewable_payload() -> None:
    result = prepare_existing_script_execution("tests/assets/runner_pass_case.py")

    assert result["script_path"] == "tests/assets/runner_pass_case.py"
    assert result["generation_mode"] == "existing_script"
    assert result["execution_readiness"] == "review_required"


def test_analyze_information_needs_adds_history_and_bug_context_for_task_text() -> None:
    parse_result = parse_requirement("data/inputs/sample_prd_login.md")
    needs = analyze_information_needs(
        "data/inputs/sample_prd_login.md",
        parse_result=parse_result,
        task={
            "task_text": "Run a regression check because this login flow failed before with a defect.",
            "module": "login",
            "target_url": "/login",
        },
    )

    assert "run_history" in needs["required_context_types"]
    assert "bug_report" in needs["required_context_types"]
    assert "historical_run_context_requested" in needs["reason_codes"]
    assert "defect_context_requested" in needs["reason_codes"]


def test_run_summary_and_artifact_tools_read_saved_run_outputs() -> None:
    run_result = run_test("tests/assets/runner_pass_case.py")

    assert run_result["status"] == "passed"

    summary_result = get_run_summary(run_result["run_id"])
    artifacts_result = get_artifacts(run_result["run_dir"])
    evidence_result = collect_run_evidence(run_result["run_dir"])

    assert summary_result["summary"]["status"] == "passed"
    assert summary_result["summary"]["run_id"] == run_result["run_id"]
    assert artifacts_result["artifact_paths"]["summary"].endswith("summary.json")
    assert artifacts_result["run_id"] == run_result["run_id"]
    assert evidence_result["queried_tools"] == ["get_run_summary", "get_artifacts"]
    assert evidence_result["run_summary"]["run_id"] == run_result["run_id"]
    assert evidence_result["queried_artifacts"]["run_id"] == run_result["run_id"]


def test_report_tool_generates_report_for_failed_run() -> None:
    run_result = run_test("tests/assets/runner_fail_case.py")

    assert run_result["status"] == "failed"

    report_result = create_report(run_result["run_dir"])

    assert report_result["generated"] is True
    assert report_result["status"] == "failed"
    assert report_result["report_path"].startswith("generated/reports/")
    assert Path(report_result["report_path"]).exists()


def test_langchain_tool_export_wraps_existing_tool_registry() -> None:
    langchain_tools = get_langchain_tools()
    tool_names = {tool.name for tool in langchain_tools}

    assert set(TOOL_REGISTRY).issubset(tool_names)
    assert "retrieve_testing_context" in tool_names
