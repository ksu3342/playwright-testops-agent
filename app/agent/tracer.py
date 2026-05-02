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

    def _write(self) -> None:
        self.trace_path.write_text(json.dumps(self.trace, indent=2), encoding="utf-8")

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

    def finalize(
        self,
        final_status: str,
        final_output: Optional[dict[str, Any]] = None,
        error: Optional[BaseException | str] = None,
    ) -> dict[str, Any]:
        end = _utc_now()
        start = datetime.fromisoformat(str(self.trace["start_time"]))
        self.trace["status"] = "completed" if error is None else "failed"
        self.trace["final_status"] = final_status
        self.trace["final_output"] = _json_safe(final_output)
        self.trace["end_time"] = end.isoformat()
        self.trace["duration_seconds"] = round((end - start).total_seconds(), 6)
        if error is not None:
            self.trace["error"] = str(error)
        self._write()
        return self.trace
