# Playwright Test Guidelines

- Prefer stable `data-testid` selectors from `data/contracts`.
- Do not guess missing selectors. Mark missing selector coverage explicitly.
- Keep generated scripts conservative when fixture data or expected UI text is not verified.
- Store execution summaries and artifacts under `data/runs`.
- Create a bug report draft only after a failed execution has a saved run summary.
