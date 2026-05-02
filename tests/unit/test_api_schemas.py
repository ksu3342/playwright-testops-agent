import pytest
from pydantic import ValidationError

from app.api.main import _resolve_agent_run_input
from app.api.schemas import AgentRunRequest


def test_agent_run_request_keeps_input_path_compatibility() -> None:
    request = AgentRunRequest(input_path="data/inputs/sample_prd_login.md")

    assert request.input_path == "data/inputs/sample_prd_login.md"
    assert request.task_text is None
    assert request.approval_mode == "auto"
    assert request.retrieval_backend == "file_lexical"
    assert request.planning_backend == "deterministic"


def test_agent_run_request_accepts_task_text_payload() -> None:
    request = AgentRunRequest(
        task_text="Verify login happy path",
        target_url="/login",
        module="login",
        constraints=["Use selector contracts"],
        approval_mode="manual",
        retrieval_backend="langchain_local",
        planning_backend="llm_assisted",
    )

    assert request.input_path is None
    assert request.task_text == "Verify login happy path"
    assert request.target_url == "/login"
    assert request.module == "login"
    assert request.constraints == ["Use selector contracts"]
    assert request.approval_mode == "manual"
    assert request.retrieval_backend == "langchain_local"
    assert request.planning_backend == "llm_assisted"


def test_agent_run_request_accepts_script_path_payload() -> None:
    request = AgentRunRequest(script_path="tests/assets/runner_pass_case.py")

    assert request.input_path is None
    assert request.script_path == "tests/assets/runner_pass_case.py"
    assert request.task_text is None


def test_agent_run_request_requires_input_path_task_text_or_script_path() -> None:
    with pytest.raises(ValidationError):
        AgentRunRequest()


def test_agent_task_text_resolves_to_api_input_file() -> None:
    request = AgentRunRequest(
        task_text="Verify login happy path",
        target_url="/login",
        module="login",
    )

    input_path, task, script_path = _resolve_agent_run_input(request)

    assert input_path.startswith("data/api_inputs/")
    assert input_path.endswith("_agent_task.md")
    assert script_path is None
    assert task["generated_input_path"] == input_path
    assert task["module"] == "login"


def test_script_path_resolves_to_existing_script_agent_input() -> None:
    request = AgentRunRequest(script_path="tests/assets/runner_pass_case.py", module="existing script")

    input_path, task, script_path = _resolve_agent_run_input(request)

    assert input_path == "tests/assets/runner_pass_case.py"
    assert script_path == "tests/assets/runner_pass_case.py"
    assert task["script_path"] == "tests/assets/runner_pass_case.py"
    assert task["execution_mode"] == "existing_script"
    assert task["module"] == "existing script"
