from dataclasses import dataclass


@dataclass
class PRDDocument:
    title: str
    raw_text: str
    summary: str

    # TODO: Add richer fields when the parser starts handling structured PRDs.
