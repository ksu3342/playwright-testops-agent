import json
from pathlib import Path


def collect_run_artifacts(run_result: dict[str, str]) -> Path:
    """Persist a minimal run summary for later reporting."""
    output_path = Path("data/runs/latest.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(run_result, indent=2), encoding="utf-8")
    return output_path


# TODO: Store screenshots, console logs, and traces once real execution exists.
