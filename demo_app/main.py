import os
from html import escape
from typing import Iterable, Optional
from urllib.parse import parse_qs

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn


DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "password123"
SEARCH_FIXTURES = [
    {
        "title": "Playwright login smoke flow",
        "description": "Covers a login path with stable test hooks.",
    },
    {
        "title": "Playwright search regression notes",
        "description": "Records search scenarios and empty-state checks.",
    },
    {
        "title": "Playwright dashboard navigation checklist",
        "description": "Lists the minimal dashboard assertions for the demo target.",
    },
]

app = FastAPI(title="Playwright TestOps Demo App")


def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <style>
      body {{
        font-family: Arial, sans-serif;
        max-width: 760px;
        margin: 40px auto;
        padding: 0 16px;
        color: #1f2937;
      }}
      main {{
        border: 1px solid #d1d5db;
        border-radius: 12px;
        padding: 24px;
        background: #ffffff;
      }}
      form {{
        display: grid;
        gap: 12px;
      }}
      label {{
        font-weight: 600;
      }}
      input {{
        padding: 10px 12px;
        border: 1px solid #9ca3af;
        border-radius: 8px;
      }}
      button {{
        width: fit-content;
        padding: 10px 16px;
        border: 0;
        border-radius: 8px;
        background: #2563eb;
        color: white;
        cursor: pointer;
      }}
      .error {{
        color: #b91c1c;
        font-weight: 600;
      }}
      .hint {{
        color: #4b5563;
      }}
      .card {{
        border: 1px solid #d1d5db;
        border-radius: 10px;
        padding: 12px;
        margin-top: 12px;
      }}
      ul {{
        padding-left: 20px;
      }}
    </style>
  </head>
  <body>
    {body}
  </body>
</html>
"""


def _login_page(error: Optional[str] = None, email: str = "") -> str:
    safe_email = escape(email)
    error_html = ""
    if error:
        error_html = (
            f'<p class="error" role="alert" data-testid="login-inline-error">{escape(error)}</p>'
        )

    return _page(
        "Demo Login",
        f"""
<main data-testid="login-page">
  <h1 data-testid="login-heading">Demo Login</h1>
  <p class="hint">Use the fixed demo credentials to continue to the dashboard.</p>
  {error_html}
  <form method="post" action="/login" data-testid="login-form">
    <div>
      <label for="email">Email</label><br />
      <input id="email" name="email" type="email" value="{safe_email}" data-testid="login-email-input" />
    </div>
    <div>
      <label for="password">Password</label><br />
      <input id="password" name="password" type="password" data-testid="login-password-input" />
    </div>
    <button type="submit" data-testid="login-submit-button">Sign in</button>
  </form>
</main>
""",
    )


def _dashboard_page() -> str:
    return _page(
        "Demo Dashboard",
        """
<main data-testid="dashboard-page">
  <h1 data-testid="dashboard-heading">Demo Dashboard</h1>
  <p>Login request is submitted successfully and the user reaches the dashboard.</p>
  <nav>
    <a href="/search" data-testid="dashboard-search-link">Go to search</a>
  </nav>
</main>
""",
    )


def _matching_results(query: str) -> list[dict[str, str]]:
    normalized = query.strip().lower()
    if not normalized:
        return []
    return [
        item
        for item in SEARCH_FIXTURES
        if normalized in item["title"].lower() or normalized in item["description"].lower()
    ]


def _results_markup(items: Iterable[dict[str, str]]) -> str:
    rows = []
    for item in items:
        rows.append(
            "<li data-testid=\"search-result-item\">"
            f"<strong>{escape(item['title'])}</strong><br />"
            f"<span>{escape(item['description'])}</span>"
            "</li>"
        )
    return "".join(rows)


def _search_page(query: str = "") -> str:
    safe_query = escape(query)
    results = _matching_results(query)

    state_html = '<p class="hint">Try the demo queries <code>playwright</code> or <code>no-hit</code>.</p>'
    if query:
        if results:
            state_html = (
                '<section data-testid="search-results-section">'
                '<h2>Results</h2>'
                f'<ul data-testid="search-results-list">{_results_markup(results)}</ul>'
                "</section>"
            )
        else:
            state_html = (
                '<p class="hint" data-testid="search-empty-state">'
                "No results matched your query."
                "</p>"
            )

    return _page(
        "Demo Search",
        f"""
<main data-testid="search-page">
  <h1 data-testid="search-heading">Keyword Search</h1>
  <p class="hint">Search data is available in the demo app.</p>
  <form method="get" action="/search" data-testid="search-form">
    <div>
      <label for="query">Search</label><br />
      <input id="query" name="q" type="search" value="{safe_query}" data-testid="search-input" />
    </div>
    <button type="submit" data-testid="search-submit-button">Search</button>
  </form>
  {state_html}
</main>
""",
    )


@app.get("/login", response_class=HTMLResponse)
async def get_login() -> HTMLResponse:
    return HTMLResponse(_login_page())


@app.post("/login")
async def post_login(request: Request):
    raw_body = await request.body()
    parsed = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
    email = parsed.get("email", [""])[0]
    password = parsed.get("password", [""])[0]

    if email == DEMO_EMAIL and password == DEMO_PASSWORD:
        return RedirectResponse(url="/dashboard", status_code=303)

    return HTMLResponse(
        _login_page(error="Invalid email or password.", email=email),
        status_code=200,
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard() -> HTMLResponse:
    return HTMLResponse(_dashboard_page())


@app.get("/search", response_class=HTMLResponse)
async def get_search(q: str = Query(default="")) -> HTMLResponse:
    return HTMLResponse(_search_page(query=q))


def main() -> None:
    port = int(os.getenv("DEMO_APP_PORT", "3000"))
    uvicorn.run("demo_app.main:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
