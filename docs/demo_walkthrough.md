# Demo Walkthrough

Start the local demo app:

```powershell
.\.venv\Scripts\python.exe -m demo_app.main
```

Run the demo smoke test:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\demo\test_demo_app.py -q
```

Fixed demo behaviors:

1. `GET /login` renders email and password inputs plus a submit button.
2. `POST /login` with `demo@example.com` / `password123` redirects to `/dashboard`.
3. `POST /login` with invalid credentials shows an inline error on the page.
4. `GET /search?q=playwright` returns a visible results list.
5. `GET /search?q=no-hit` returns an empty state.
