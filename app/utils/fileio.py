import json
from pathlib import Path
from typing import Any


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str, content: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output


def write_json(path: str, payload: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output
