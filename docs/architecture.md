# Architecture

This phase-1 scaffold keeps the project intentionally small.

Flow:
1. `parser.py` reads a simple PRD/page description
2. `extractor.py` creates placeholder test points
3. `generator.py` writes a Playwright script from a template
4. `runner.py` records a placeholder run result
5. `collector.py` stores minimal run artifacts
6. `reporter.py` drafts a simple bug report

Why this shape:
- easy to demo from CLI
- easy to extend step by step
- easy to explain in interviews
- no fake production complexity
