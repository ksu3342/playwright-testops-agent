from app.agent.status import (
    AgentRunStatus,
    normalize_agent_status,
    status_from_missing_inputs,
    status_from_plan_validation,
    status_from_run_result,
    trace_status_for_final_status,
)


def test_status_from_plan_validation_classifies_missing_context() -> None:
    assert status_from_plan_validation({"status": "passed", "missing_inputs": []}) == AgentRunStatus.PASSED
    assert status_from_missing_inputs(["page_url"]) == AgentRunStatus.BLOCKED_MISSING_CONTEXT
    assert status_from_missing_inputs(["selector_contract"]) == AgentRunStatus.BLOCKED_SELECTOR_MISSING
    assert status_from_missing_inputs(["test_data_contract"]) == AgentRunStatus.BLOCKED_TEST_DATA_MISSING


def test_status_from_run_result_classifies_execution_outcomes() -> None:
    assert status_from_run_result({"status": "passed"}) == AgentRunStatus.PASSED
    assert status_from_run_result({"status": "failed"}) == AgentRunStatus.FAILED
    assert status_from_run_result({"status": "environment_error"}) == AgentRunStatus.ENVIRONMENT_ERROR
    assert status_from_run_result(
        {"status": "blocked", "execution_readiness": "blocked_by_selector_contract"}
    ) == AgentRunStatus.BLOCKED_SELECTOR_MISSING
    assert status_from_run_result(
        {"status": "blocked", "execution_readiness": "blocked_by_incomplete_markers"}
    ) == AgentRunStatus.BLOCKED_MISSING_CONTEXT


def test_legacy_statuses_normalize_to_agent_status_enum() -> None:
    assert normalize_agent_status("waiting_for_test_plan_approval") == "waiting_human_approval"
    assert normalize_agent_status("waiting_for_execution_approval") == "waiting_human_approval"
    assert normalize_agent_status("waiting_for_report_approval") == "report_draft_created"
    assert normalize_agent_status("blocked") == "blocked_missing_context"
    assert normalize_agent_status("rejected") == "blocked_plan_not_approved"


def test_trace_status_uses_lifecycle_status_for_pending_agent_states() -> None:
    assert trace_status_for_final_status(AgentRunStatus.WAITING_HUMAN_APPROVAL) == "waiting_for_approval"
    assert trace_status_for_final_status(AgentRunStatus.REPORT_DRAFT_CREATED) == "waiting_for_approval"
    assert trace_status_for_final_status(AgentRunStatus.PASSED) == "completed"
