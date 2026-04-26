from __future__ import annotations

import contextlib
import os
import socket
import threading
import time
import urllib.request
from pathlib import Path
from typing import Iterator, Optional

from app.core.collector import RUN_DIR_ENV_VAR
import uvicorn
from demo_app.main import app
from playwright.sync_api import expect, sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_HOST = "127.0.0.1"
SERVER_START_TIMEOUT_SECONDS = float(os.getenv("DEMO_SERVER_START_TIMEOUT_SECONDS", "20"))
DEFAULT_RUN_DIR = REPO_ROOT / "data" / "runs" / "manual_playwright_login_failure_case"


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((DEMO_HOST, 0))
        return int(sock.getsockname()[1])


def _login_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/login"


def _wait_for_login_page(base_url: str, thread: Optional[threading.Thread] = None) -> None:
    deadline = time.time() + SERVER_START_TIMEOUT_SECONDS
    last_error: Optional[Exception] = None
    while time.time() < deadline:
        if thread is not None and not thread.is_alive():
            raise RuntimeError("Demo app server thread exited before /login became ready.")
        try:
            with urllib.request.urlopen(_login_url(base_url), timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"Demo app did not become ready at {_login_url(base_url)}: {last_error}")


@contextlib.contextmanager
def _demo_server() -> Iterator[str]:
    demo_port = _pick_free_port()
    base_url = f"http://{DEMO_HOST}:{demo_port}"
    config = uvicorn.Config(
        app,
        host=DEMO_HOST,
        port=demo_port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        _wait_for_login_page(base_url, thread=thread)
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _failure_screenshot_path() -> Path:
    run_dir = Path(os.getenv(RUN_DIR_ENV_VAR, str(DEFAULT_RUN_DIR)))
    return run_dir / "screenshots" / "login_failure.png"


def test_login_failure_case_records_screenshot_on_real_playwright_failure() -> None:
    screenshot_path = _failure_screenshot_path()
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    with _demo_server() as base_url:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                target_url = _login_url(base_url)
                expected_dashboard_url = base_url.rstrip("/") + "/dashboard"
                page.goto(target_url, wait_until="domcontentloaded")
                page.get_by_test_id("login-email-input").fill("demo@example.com")
                page.get_by_test_id("login-password-input").fill("password123")
                page.get_by_test_id("login-submit-button").click()
                page.wait_for_url(expected_dashboard_url)
                expect(page.get_by_test_id("dashboard-heading")).to_have_text(
                    "Definitely Wrong Dashboard Heading",
                    timeout=3000,
                )
            except Exception:
                page.screenshot(path=str(screenshot_path), full_page=True)
                raise
            finally:
                page.close()
                browser.close()
