from __future__ import annotations

from enum import Enum
from typing import Any


class AgentRunStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED_MISSING_CONTEXT = "blocked_missing_context"
    BLOCKED_SELECTOR_MISSING = "blocked_selector_missing"
    BLOCKED_TEST_DATA_MISSING = "blocked_test_data_missing"
    BLOCKED_PLAN_NOT_APPROVED = "blocked_plan_not_approved"
    WAITING_HUMAN_APPROVAL = "waiting_human_approval"
    REPORT_DRAFT_CREATED = "report_draft_created"
    ENVIRONMENT_ERROR = "environment_error"


WAITING_TRACE_STATUS = "waiting_for_approval"
COMPLETED_TRACE_STATUS = "completed"


def status_value(status: AgentRunStatus | str) -> str:
    if isinstance(status, AgentRunStatus):
        return status.value
    return str(status)


def is_agent_status(value: str) -> bool:
    return value in {status.value for status in AgentRunStatus}


def normalize_agent_status(value: Any) -> str:
    raw_value = str(value or AgentRunStatus.ENVIRONMENT_ERROR.value)
    if is_agent_status(raw_value):
        return raw_value

    legacy_map = {
        "blocked": AgentRunStatus.BLOCKED_MISSING_CONTEXT.value,
        "rejected": AgentRunStatus.BLOCKED_PLAN_NOT_APPROVED.value,
        "report_rejected": AgentRunStatus.BLOCKED_PLAN_NOT_APPROVED.value,
        "waiting_for_test_plan_approval": AgentRunStatus.WAITING_HUMAN_APPROVAL.value,
        "waiting_for_execution_approval": AgentRunStatus.WAITING_HUMAN_APPROVAL.value,
        "waiting_for_report_approval": AgentRunStatus.REPORT_DRAFT_CREATED.value,
    }
    return legacy_map.get(raw_value, AgentRunStatus.ENVIRONMENT_ERROR.value)


def status_from_missing_inputs(missing_inputs: list[Any]) -> AgentRunStatus:
    normalized = {str(item) for item in missing_inputs}
    if any("selector_contract" in item for item in normalized):
        return AgentRunStatus.BLOCKED_SELECTOR_MISSING
    if any("test_data_contract" in item for item in normalized):
        return AgentRunStatus.BLOCKED_TEST_DATA_MISSING
    return AgentRunStatus.BLOCKED_MISSING_CONTEXT


def status_from_plan_validation(plan_validation: dict[str, Any]) -> AgentRunStatus:
    if plan_validation.get("status") == "passed":
        return AgentRunStatus.PASSED
    missing_inputs = plan_validation.get("missing_inputs")
    if not isinstance(missing_inputs, list):
        missing_inputs = []
    return status_from_missing_inputs(missing_inputs)


def status_from_run_result(run_result: dict[str, Any]) -> AgentRunStatus:
    raw_status = str(run_result.get("status", "environment_error"))
    if raw_status == "passed":
        return AgentRunStatus.PASSED
    if raw_status == "failed":
        return AgentRunStatus.FAILED
    if raw_status == "environment_error":
        return AgentRunStatus.ENVIRONMENT_ERROR
    if raw_status == "blocked":
        readiness = str(run_result.get("execution_readiness", ""))
        reason = str(run_result.get("reason", "")).lower()
        if readiness == "blocked_by_selector_contract" or "selector contract" in reason:
            return AgentRunStatus.BLOCKED_SELECTOR_MISSING
        if "test data" in reason or "fixture" in reason:
            return AgentRunStatus.BLOCKED_TEST_DATA_MISSING
        return AgentRunStatus.BLOCKED_MISSING_CONTEXT
    return AgentRunStatus.ENVIRONMENT_ERROR


def trace_status_for_final_status(final_status: AgentRunStatus | str) -> str:
    value = status_value(final_status)
    if value in {AgentRunStatus.WAITING_HUMAN_APPROVAL.value, AgentRunStatus.REPORT_DRAFT_CREATED.value}:
        return WAITING_TRACE_STATUS
    return COMPLETED_TRACE_STATUS
