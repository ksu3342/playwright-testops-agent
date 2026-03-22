from dataclasses import dataclass


@dataclass
class TestPoint:
    id: str
    title: str
    rationale: str

    # TODO: Add priority/severity fields after extraction becomes more realistic.
