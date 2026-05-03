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
