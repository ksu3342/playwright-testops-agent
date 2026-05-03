from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from app.core.collector import REPO_ROOT


AGENT_RUNS_DIR = REPO_ROOT / "data" / "agent_runs"
T = TypeVar("T")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "agent_run"


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


def build_agent_run_id(input_path: str) -> str:
    timestamp = _utc_now().strftime("%Y%m%dT%H%M%S%fZ")
    stem = Path(input_path).stem or "input"
    return f"{timestamp}_{_slugify(stem)}"


class AgentRunTracer:
    def __init__(self, agent_run_id: str, initial_input: dict[str, Any]) -> None:
        self.agent_run_id = agent_run_id
        self.run_dir = AGENT_RUNS_DIR / agent_run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.run_dir / "trace.json"

        start_time = _utc_now().isoformat()
        self.trace: dict[str, Any] = {
            "agent_run_id": agent_run_id,
            "status": "running",
            "final_status": None,
            "input": _json_safe(initial_input),
            "start_time": start_time,
            "end_time": None,
            "duration_seconds": None,
            "tool_calls": [],
            "approval_requests": [],
            "human_approvals": {},
            "decision_trace": [],
            "checkpoint_mode": "trace_resume_state",
            "resume_state": None,
            "state_keys": [],
            "pending_approval": None,
            "final_output": None,
            "error": None,
            "artifact_paths": {
                "agent_run_dir": _relative_to_repo(self.run_dir),
                "trace": _relative_to_repo(self.trace_path),
            },
        }
        self._write()

    @classmethod
    def create(cls, initial_input: dict[str, Any], agent_run_id: Optional[str] = None) -> "AgentRunTracer":
        input_path = str(initial_input.get("input_path", "input"))
        return cls(agent_run_id or build_agent_run_id(input_path), initial_input)

    @classmethod
    def resume(cls, agent_run_id: str) -> "AgentRunTracer":
        tracer = cls.__new__(cls)
        tracer.agent_run_id = agent_run_id
        tracer.run_dir = AGENT_RUNS_DIR / agent_run_id
        tracer.trace_path = tracer.run_dir / "trace.json"
        if not tracer.trace_path.is_file():
            raise FileNotFoundError(f"Agent run trace was not found: {_relative_to_repo(tracer.trace_path)}")
        payload = json.loads(tracer.trace_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Agent run trace is not a JSON object: {_relative_to_repo(tracer.trace_path)}")
        tracer.trace = payload
        return tracer

    def _write(self) -> None:
        self.trace_path.write_text(json.dumps(self.trace, indent=2), encoding="utf-8")

    def mark_running(self) -> None:
        self.trace["status"] = "running"
        self.trace["error"] = None
        self._write()

    def save_test_plan(self, test_plan: dict[str, Any]) -> str:
        test_plan_path = self.run_dir / "test_plan.json"
        test_plan_path.write_text(json.dumps(_json_safe(test_plan), indent=2), encoding="utf-8")
        artifact_paths = self.trace.setdefault("artifact_paths", {})
        if not isinstance(artifact_paths, dict):
            artifact_paths = {}
            self.trace["artifact_paths"] = artifact_paths
        artifact_paths["test_plan"] = _relative_to_repo(test_plan_path)
        self._write()
        return str(artifact_paths["test_plan"])

    def record_decision(self, step: str, status: str, reason: str, next_action: Optional[str]) -> dict[str, Any]:
        decisions = self.trace.setdefault("decision_trace", [])
        if not isinstance(decisions, list):
            decisions = []
            self.trace["decision_trace"] = decisions

        decision_payload = {
            "step": str(step),
            "status": str(status),
            "reason": str(reason),
            "next_action": next_action,
        }
        for existing in decisions:
            if not isinstance(existing, dict):
                continue
            if all(existing.get(key) == value for key, value in decision_payload.items()):
                return existing

        decision_record = {
            "sequence": len(decisions) + 1,
            **decision_payload,
            "recorded_at": _utc_now().isoformat(),
        }
        decisions.append(_json_safe(decision_record))
        self._write()
        return decision_record

    def call_tool(self, tool_name: str, tool_input: dict[str, Any], tool_func: Callable[[], T]) -> T:
        sequence = len(self.trace["tool_calls"]) + 1
        start = _utc_now()
        call_record: dict[str, Any] = {
            "sequence": sequence,
            "tool_name": tool_name,
            "status": "running",
            "input": _json_safe(tool_input),
            "output": None,
            "error": None,
            "start_time": start.isoformat(),
            "end_time": None,
            "duration_seconds": None,
        }
        self.trace["tool_calls"].append(call_record)
        self._write()

        try:
            output = tool_func()
        except Exception as exc:
            end = _utc_now()
            call_record.update(
                {
                    "status": "failed",
                    "error": {
                        "type": exc.__class__.__name__,
                        "message": str(exc),
                    },
                    "end_time": end.isoformat(),
                    "duration_seconds": round((end - start).total_seconds(), 6),
                }
            )
            self._write()
            raise

        end = _utc_now()
        call_record.update(
            {
                "status": "succeeded",
                "output": _json_safe(output),
                "end_time": end.isoformat(),
                "duration_seconds": round((end - start).total_seconds(), 6),
            }
        )
        self._write()
        return output

    def request_approval(self, gate: str, title: str, payload: dict[str, Any]) -> dict[str, Any]:
        requests = self.trace.setdefault("approval_requests", [])
        if not isinstance(requests, list):
            requests = []
            self.trace["approval_requests"] = requests

        for request in requests:
            if isinstance(request, dict) and request.get("gate") == gate and request.get("status") == "pending":
                return request

        request_record = {
            "gate": gate,
            "title": title,
            "status": "pending",
            "requested_at": _utc_now().isoformat(),
            "decided_at": None,
            "reviewer": None,
            "comment": None,
            "payload": _json_safe(payload),
        }
        requests.append(request_record)
        self.trace["pending_approval"] = _json_safe(request_record)
        self._write()
        return request_record

    def record_approval_decision(
        self,
        gate: str,
        decision: str,
        reviewer: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise ValueError("Approval decision must be either 'approved' or 'rejected'.")

        decided_at = _utc_now().isoformat()
        decision_record = {
            "gate": gate,
            "decision": decision,
            "reviewer": reviewer,
            "comment": comment,
            "decided_at": decided_at,
        }

        approvals = self.trace.setdefault("human_approvals", {})
        if not isinstance(approvals, dict):
            approvals = {}
            self.trace["human_approvals"] = approvals
        approvals[gate] = decision_record

        requests = self.trace.setdefault("approval_requests", [])
        if isinstance(requests, list):
            for request in reversed(requests):
                if isinstance(request, dict) and request.get("gate") == gate and request.get("status") == "pending":
                    request.update(
                        {
                            "status": decision,
                            "decided_at": decided_at,
                            "reviewer": reviewer,
                            "comment": comment,
                        }
                    )
                    break

        self._write()
        return decision_record

    def finalize(
        self,
        final_status: str,
        final_output: Optional[dict[str, Any]] = None,
        error: Optional[BaseException | str] = None,
        trace_status: Optional[str] = None,
        resume_state: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        end = _utc_now()
        start = datetime.fromisoformat(str(self.trace["start_time"]))
        self.trace["status"] = trace_status or ("completed" if error is None else "failed")
        self.trace["final_status"] = final_status
        self.trace["final_output"] = _json_safe(final_output)
        self.trace["end_time"] = end.isoformat()
        self.trace["duration_seconds"] = round((end - start).total_seconds(), 6)
        self.trace["resume_state"] = _json_safe(resume_state)
        self.trace["checkpoint_mode"] = "trace_resume_state"
        self.trace["state_keys"] = sorted(resume_state.keys()) if isinstance(resume_state, dict) else []
        if isinstance(final_output, dict):
            self.trace["pending_approval"] = _json_safe(final_output.get("pending_approval"))
        else:
            self.trace["pending_approval"] = None
        if error is not None:
            self.trace["error"] = str(error)
        self._write()
        return self.trace
