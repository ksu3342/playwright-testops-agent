from dataclasses import dataclass


@dataclass
class BugReport:
    title: str
    summary: str
    reproduction_steps: list[str]
    observed_result: str
    expected_result: str

    # TODO: Add attachments and environment info once real execution exists.
