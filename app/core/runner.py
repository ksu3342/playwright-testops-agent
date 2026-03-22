from pathlib import Path

from app.config import get_settings


def run_generated_test(script_path: str) -> dict[str, str]:
    """Placeholder runner that records intent instead of launching a browser."""
    settings = get_settings()
    run_log = Path("data/runs/latest.log")
    run_log.parent.mkdir(parents=True, exist_ok=True)
    run_log.write_text(
        "\n".join(
            [
                "Phase-1 placeholder run",
                f"script_path={script_path}",
                f"browser={settings.playwright_browser}",
                f"headless={settings.headless}",
                "status=placeholder_success",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"status": "placeholder_success", "log_path": str(run_log)}


# TODO: Replace this with actual Playwright execution in the next phase.
