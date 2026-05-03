from app.agent.tracer import AgentRunTracer


def test_record_decision_deduplicates_identical_decisions() -> None:
    tracer = AgentRunTracer.create(
        {"input_path": "tests/assets/runner_pass_case.py"},
        agent_run_id="unit_tracer_deduplicates_decisions",
    )

    first = tracer.record_decision(
        "execution_approval",
        "passed",
        "Execution approved or auto approval mode is active.",
        "run_test",
    )
    second = tracer.record_decision(
        "execution_approval",
        "passed",
        "Execution approved or auto approval mode is active.",
        "run_test",
    )

    assert first == second
    assert tracer.trace["decision_trace"] == [first]


def test_record_decision_persists_hitl_resume_metadata() -> None:
    tracer = AgentRunTracer.create(
        {"input_path": "tests/assets/runner_pass_case.py"},
        agent_run_id="unit_tracer_decision_metadata",
    )

    decision = tracer.record_decision(
        "test_plan_approval",
        "passed",
        "Test plan approved.",
        "generate_test_from_plan",
        decision="approve",
        approval_gate="test_plan",
        test_plan_path="data/agent_runs/unit_tracer_decision_metadata/test_plan.json",
        resumed_from={
            "trace_status": "waiting_for_approval",
            "final_status": "waiting_human_approval",
            "pending_gate": "test_plan",
            "test_plan_path": "data/agent_runs/unit_tracer_decision_metadata/test_plan.json",
        },
        approval_comment="plan ok",
    )

    assert decision["decision"] == "approve"
    assert decision["approval_gate"] == "test_plan"
    assert decision["test_plan_path"].endswith("/test_plan.json")
    assert decision["resumed_from"]["pending_gate"] == "test_plan"
    assert decision["approval_comment"] == "plan ok"


def test_approval_request_and_decision_use_canonical_hitl_values() -> None:
    tracer = AgentRunTracer.create(
        {"input_path": "tests/assets/runner_pass_case.py"},
        agent_run_id="unit_tracer_canonical_approval_decisions",
    )

    request = tracer.request_approval("execution", "Approve execution", {"script_path": "tests/assets/runner_pass_case.py"})
    assert request["status"] == "pending"
    assert request["decision"] == "pending"
    assert tracer.trace["pending_approval"]["decision"] == "pending"

    decision = tracer.record_approval_decision("execution", "approved", reviewer="pytest", comment="execute")

    assert decision["decision"] == "approve"
    assert tracer.trace["human_approvals"]["execution"]["decision"] == "approve"
    assert tracer.trace["approval_requests"][0]["status"] == "approve"
    assert tracer.trace["approval_requests"][0]["decision"] == "approve"
