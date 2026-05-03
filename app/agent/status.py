from __future__ import annotations

from enum import Enum
from typing import Any


class AgentBusinessStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED_MISSING_CONTEXT = "blocked_missing_context"
    BLOCKED_SELECTOR_MISSING = "blocked_selector_missing"
    BLOCKED_TEST_DATA_MISSING = "blocked_test_data_missing"
    BLOCKED_PLAN_NOT_APPROVED = "blocked_plan_not_approved"
    WAITING_HUMAN_APPROVAL = "waiting_human_approval"
    REPORT_DRAFT_CREATED = "report_draft_created"
    ENVIRONMENT_ERROR = "environment_error"


class TraceLifecycleStatus(str, Enum):
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalDecision(str, Enum):
    PENDING = "pending"
    APPROVE = "approve"
    REJECT = "reject"


# Backward-compatible export used by existing API schemas and tests.
AgentRunStatus = AgentBusinessStatus

WAITING_TRACE_STATUS = TraceLifecycleStatus.WAITING_FOR_APPROVAL.value
COMPLETED_TRACE_STATUS = TraceLifecycleStatus.COMPLETED.value


def status_value(status: AgentBusinessStatus | str) -> str:
    if isinstance(status, AgentBusinessStatus):
        return status.value
    return str(status)


def is_agent_status(value: str) -> bool:
    return value in {status.value for status in AgentBusinessStatus}


def normalize_agent_status(value: Any) -> str:
    raw_value = str(value or AgentBusinessStatus.ENVIRONMENT_ERROR.value)
    if is_agent_status(raw_value):
        return raw_value

    legacy_map = {
        "blocked": AgentBusinessStatus.BLOCKED_MISSING_CONTEXT.value,
        "rejected": AgentBusinessStatus.BLOCKED_PLAN_NOT_APPROVED.value,
        "report_rejected": AgentBusinessStatus.BLOCKED_PLAN_NOT_APPROVED.value,
        "waiting_for_test_plan_approval": AgentBusinessStatus.WAITING_HUMAN_APPROVAL.value,
        "waiting_for_execution_approval": AgentBusinessStatus.WAITING_HUMAN_APPROVAL.value,
        "waiting_for_report_approval": AgentBusinessStatus.REPORT_DRAFT_CREATED.value,
    }
    return legacy_map.get(raw_value, AgentBusinessStatus.ENVIRONMENT_ERROR.value)


def normalize_approval_decision(value: Any) -> ApprovalDecision:
    raw_value = str(value or "").strip().lower()
    decision_map = {
        ApprovalDecision.PENDING.value: ApprovalDecision.PENDING,
        ApprovalDecision.APPROVE.value: ApprovalDecision.APPROVE,
        "approved": ApprovalDecision.APPROVE,
        ApprovalDecision.REJECT.value: ApprovalDecision.REJECT,
        "rejected": ApprovalDecision.REJECT,
    }
    try:
        return decision_map[raw_value]
    except KeyError as exc:
        raise ValueError("Approval decision must be one of: pending, approve, reject, approved, rejected.") from exc


def status_from_missing_inputs(missing_inputs: list[Any]) -> AgentBusinessStatus:
    normalized = {str(item) for item in missing_inputs}
    if any("selector_contract" in item for item in normalized):
        return AgentBusinessStatus.BLOCKED_SELECTOR_MISSING
    if any("test_data_contract" in item for item in normalized):
        return AgentBusinessStatus.BLOCKED_TEST_DATA_MISSING
    return AgentBusinessStatus.BLOCKED_MISSING_CONTEXT


def status_from_plan_validation(plan_validation: dict[str, Any]) -> AgentBusinessStatus:
    if plan_validation.get("status") == "passed":
        return AgentBusinessStatus.PASSED
    missing_inputs = plan_validation.get("missing_inputs")
    if not isinstance(missing_inputs, list):
        missing_inputs = []
    return status_from_missing_inputs(missing_inputs)


def status_from_run_result(run_result: dict[str, Any]) -> AgentBusinessStatus:
    raw_status = str(run_result.get("status", "environment_error"))
    if raw_status == "passed":
        return AgentBusinessStatus.PASSED
    if raw_status == "failed":
        return AgentBusinessStatus.FAILED
    if raw_status == "environment_error":
        return AgentBusinessStatus.ENVIRONMENT_ERROR
    if raw_status == "blocked":
        readiness = str(run_result.get("execution_readiness", ""))
        reason = str(run_result.get("reason", "")).lower()
        if readiness == "blocked_by_selector_contract" or "selector contract" in reason:
            return AgentBusinessStatus.BLOCKED_SELECTOR_MISSING
        if "test data" in reason or "fixture" in reason:
            return AgentBusinessStatus.BLOCKED_TEST_DATA_MISSING
        return AgentBusinessStatus.BLOCKED_MISSING_CONTEXT
    return AgentBusinessStatus.ENVIRONMENT_ERROR


def trace_status_for_final_status(final_status: AgentBusinessStatus | str) -> str:
    value = status_value(final_status)
    if value in {AgentBusinessStatus.WAITING_HUMAN_APPROVAL.value, AgentBusinessStatus.REPORT_DRAFT_CREATED.value}:
        return TraceLifecycleStatus.WAITING_FOR_APPROVAL.value
    return TraceLifecycleStatus.COMPLETED.value
