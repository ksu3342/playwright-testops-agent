from pathlib import Path

from app import main as cli


def test_agent_cli_parser_accepts_agent_commands() -> None:
    parser = cli.build_parser()

    run_args = parser.parse_args(
        [
            "agent-run",
            "--task",
            "Verify login",
            "--target-url",
            "/login",
            "--module",
            "login",
            "--approval-mode",
            "manual",
        ]
    )
    approve_args = parser.parse_args(
        [
            "agent-approve",
            "--agent-run-id",
            "demo",
            "--gate",
            "execution",
            "--decision",
            "approved",
        ]
    )
    trace_args = parser.parse_args(["agent-trace", "--agent-run-id", "demo", "--format", "markdown"])

    assert run_args.command == "agent-run"
    assert run_args.task_text == "Verify login"
    assert run_args.approval_mode == "manual"
    assert approve_args.command == "agent-approve"
    assert approve_args.gate == "execution"
    assert trace_args.command == "agent-trace"
    assert trace_args.format == "markdown"


def test_agent_run_cli_wraps_orchestrator(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_agent_task(input_path: str, **kwargs):
        captured["input_path"] = input_path
        captured.update(kwargs)
        return {
            "agent_run_id": "cli_agent_run",
            "final_status": "passed",
            "script_path": "generated/tests/test_login_generated.py",
            "run_id": "cli_run",
            "trace_path": "data/agent_runs/cli_agent_run/trace.json",
        }

    monkeypatch.setattr(cli, "run_agent_task", fake_run_agent_task)

    result = cli.cmd_agent_run(
        input_path="data/inputs/sample_prd_login.md",
        task_text=None,
        target_url=None,
        module=None,
        constraints=[],
        approval_mode="auto",
        retrieval_backend="file_lexical",
        planning_backend="deterministic",
        script_path=None,
        agent_run_id="cli_agent_run",
    )
    output = capsys.readouterr().out

    assert result == 0
    assert captured["input_path"] == "data/inputs/sample_prd_login.md"
    assert captured["agent_run_id"] == "cli_agent_run"
    assert "final_status: passed" in output
    assert "trace_path: data/agent_runs/cli_agent_run/trace.json" in output


def test_agent_approve_cli_wraps_orchestrator(monkeypatch, capsys) -> None:
    def fake_continue_agent_run(agent_run_id: str, gate: str, decision: str, reviewer=None, comment=None):
        return {
            "agent_run_id": agent_run_id,
            "final_status": "passed",
            "script_path": "tests/assets/runner_pass_case.py",
            "trace_path": "data/agent_runs/cli_approved/trace.json",
        }

    monkeypatch.setattr(cli, "continue_agent_run", fake_continue_agent_run)

    result = cli.cmd_agent_approve("cli_approved", "execution", "approved", reviewer="pytest")
    output = capsys.readouterr().out

    assert result == 0
    assert "agent_run_id: cli_approved" in output
    assert "final_status: passed" in output


def test_agent_trace_cli_renders_markdown_path(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "write_decision_trace_markdown",
        lambda agent_run_id: Path("data/agent_runs/cli_trace/decision_trace.md").resolve(),
    )

    result = cli.cmd_agent_trace("cli_trace", output_format="markdown")
    output = capsys.readouterr().out

    assert result == 0
    assert "decision_trace: data/agent_runs/cli_trace/decision_trace.md" in output
