from pathlib import Path
import re
from typing import Optional

from app.schemas.prd_schema import PRDDocument


SECTION_ORDER = [
    "Title",
    "Feature Name",
    "Page URL",
    "Preconditions",
    "User Actions",
    "Expected Results",
]
LIST_SECTIONS = {"Preconditions", "User Actions", "Expected Results"}
SCALAR_SECTIONS = {"Title", "Feature Name", "Page URL"}
SECTION_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(Title|Feature Name|Page URL|Preconditions|User Actions|Expected Results)\s*$")
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.*)$")


def _normalize_list_item(line: str) -> str:
    match = LIST_ITEM_PATTERN.match(line)
    if match:
        return match.group(1).strip()
    return line.strip()


def _parse_sections(text: str) -> dict[str, list[str]]:
    sections = {section: [] for section in SECTION_ORDER}
    current_section: Optional[str] = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        section_match = SECTION_PATTERN.match(raw_line)
        if section_match:
            current_section = section_match.group(1)
            continue

        if current_section is None:
            continue

        sections[current_section].append(stripped)

    return sections


def parse_prd(input_path: str) -> PRDDocument:
    """Parse a simple markdown PRD using fixed, interview-friendly headings."""
    text = Path(input_path).read_text(encoding="utf-8").strip()
    sections = _parse_sections(text)

    scalar_values: dict[str, Optional[str]] = {}
    for section_name in SCALAR_SECTIONS:
        values = sections[section_name]
        scalar_values[section_name] = " ".join(values).strip() if values else None

    preconditions = [_normalize_list_item(line) for line in sections["Preconditions"] if _normalize_list_item(line)]
    user_actions = [_normalize_list_item(line) for line in sections["User Actions"] if _normalize_list_item(line)]
    expected_results = [_normalize_list_item(line) for line in sections["Expected Results"] if _normalize_list_item(line)]

    missing_sections: list[str] = []
    for section_name in SECTION_ORDER:
        if section_name in SCALAR_SECTIONS and not scalar_values[section_name]:
            missing_sections.append(section_name)
        if section_name in LIST_SECTIONS and not sections[section_name]:
            missing_sections.append(section_name)

    return PRDDocument(
        title=scalar_values["Title"],
        feature_name=scalar_values["Feature Name"],
        page_url=scalar_values["Page URL"],
        preconditions=preconditions,
        user_actions=user_actions,
        expected_results=expected_results,
        raw_text=text,
        missing_sections=missing_sections,
    )


# TODO: Expand the parser only when new markdown patterns show up in real sample inputs.
