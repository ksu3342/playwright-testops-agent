from dataclasses import dataclass
from typing import Optional


@dataclass
class PRDDocument:
    title: Optional[str]
    feature_name: Optional[str]
    page_url: Optional[str]
    preconditions: list[str]
    user_actions: list[str]
    expected_results: list[str]
    raw_text: str
    missing_sections: list[str]

    # TODO: Add lightweight metadata only when parsing needs clearly justify it.
