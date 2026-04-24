from fastapi.testclient import TestClient

import demo_app.main as demo_main
from demo_app.main import DEMO_EMAIL, DEMO_PASSWORD, app


client = TestClient(app)


def test_get_login_renders_form_fields() -> None:
    response = client.get("/login")

    assert response.status_code == 200
    assert 'data-testid="login-page"' in response.text
    assert 'data-testid="login-email-input"' in response.text
    assert 'data-testid="login-password-input"' in response.text
    assert 'data-testid="login-submit-button"' in response.text
    assert "Demo Login" in response.text


def test_post_login_with_valid_credentials_redirects_to_dashboard() -> None:
    response = client.post(
        "/login",
        data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )

    assert response.status_code == 200
    assert str(response.url).endswith("/dashboard")
    assert 'data-testid="dashboard-page"' in response.text
    assert "Demo Dashboard" in response.text
    assert "login-inline-error" not in response.text


def test_post_login_with_invalid_credentials_shows_inline_error() -> None:
    response = client.post(
        "/login",
        data={"email": "wrong@example.com", "password": "bad-password"},
    )

    assert response.status_code == 200
    assert 'data-testid="login-inline-error"' in response.text
    assert "Invalid email or password." in response.text
    assert 'data-testid="dashboard-page"' not in response.text


def test_search_with_playwright_returns_result_list() -> None:
    response = client.get("/search", params={"q": "playwright"})

    assert response.status_code == 200
    assert 'data-testid="search-results-list"' in response.text
    assert 'data-testid="search-result-item"' in response.text
    assert "Playwright login smoke flow" in response.text
    assert 'data-testid="search-empty-state"' not in response.text


def test_search_with_no_hit_returns_empty_state() -> None:
    response = client.get("/search", params={"q": "no-hit"})

    assert response.status_code == 200
    assert 'data-testid="search-empty-state"' in response.text
    assert "No results matched your query." in response.text
    assert 'data-testid="search-results-list"' not in response.text


def test_demo_app_main_reads_port_from_environment(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(app_path: str, host: str, port: int, reload: bool) -> None:
        captured["app_path"] = app_path
        captured["host"] = host
        captured["port"] = port
        captured["reload"] = reload

    monkeypatch.setenv("DEMO_APP_PORT", "34567")
    monkeypatch.setattr(demo_main.uvicorn, "run", fake_run)

    demo_main.main()

    assert captured == {
        "app_path": "demo_app.main:app",
        "host": "127.0.0.1",
        "port": 34567,
        "reload": False,
    }
