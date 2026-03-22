from pathlib import Path

from app.schemas.prd_schema import PRDDocument


def parse_prd(input_path: str) -> PRDDocument:
    """Read a simple markdown/text description into a small schema."""
    text = Path(input_path).read_text(encoding="utf-8").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0].lstrip("# ").strip() if lines else "Untitled PRD"
    summary = " ".join(lines[:3])[:200]
    return PRDDocument(title=title, raw_text=text, summary=summary)


# TODO: Replace this with a parser that handles common PRD/page-description patterns.
