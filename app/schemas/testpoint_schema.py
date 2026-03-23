from dataclasses import dataclass


@dataclass
class TestPoint:
    id: str
    title: str
    type: str
    preconditions: list[str]
    steps: list[str]
    expected_result: str
    source_sections: list[str]
    rationale: str

    # TODO: Add priority only when script generation clearly needs it.
