from typing import Optional

from app.schemas.prd_schema import PRDDocument
from app.schemas.testpoint_schema import TestPoint


def _find_supported_negative_expected_result(document: PRDDocument) -> Optional[str]:
    explicit_negative_markers = [
        "empty state",
        "no result",
        "no matching",
        "invalid credentials",
        "invalid input",
        "error message",
    ]
    for expected_result in document.expected_results:
        lowered = expected_result.lower()
        if any(marker in lowered for marker in explicit_negative_markers):
            return expected_result
    return None


def _build_happy_path_test_point(document: PRDDocument) -> TestPoint:
    title_base = document.feature_name or document.title or "Feature"
    expected_result = document.expected_results[0] if document.expected_results else "Expected result was not provided."
    return TestPoint(
        id="TP-001",
        title=f"{title_base} happy path works as described",
        type="happy_path",
        preconditions=document.preconditions,
        steps=document.user_actions,
        expected_result=expected_result,
        source_sections=["Preconditions", "User Actions", "Expected Results"],
        rationale="The PRD includes a clear primary flow and at least one expected outcome.",
    )


def _build_negative_path_test_point(document: PRDDocument) -> Optional[TestPoint]:
    negative_expected = _find_supported_negative_expected_result(document)
    if not negative_expected:
        return None

    title_base = document.feature_name or document.title or "Feature"
    steps = list(document.user_actions)
    lowered = negative_expected.lower()

    if "no result" in lowered or "empty state" in lowered:
        if steps:
            steps[0] = "Enter a keyword that should return no matching results"
        else:
            steps = ["Enter a keyword that should return no matching results"]
    elif "invalid credentials" in lowered or "invalid input" in lowered:
        if steps:
            steps[0] = "Enter invalid input for the flow under test"
        else:
            steps = ["Enter invalid input for the flow under test"]

    return TestPoint(
        id="TP-002",
        title=f"{title_base} handles a basic negative path",
        type="negative_path",
        preconditions=document.preconditions,
        steps=steps,
        expected_result=negative_expected,
        source_sections=["Preconditions", "User Actions", "Expected Results"],
        rationale="The PRD explicitly mentions a negative outcome that should be covered.",
    )


def extract_test_points(document: PRDDocument) -> list[TestPoint]:
    """Extract simple, deterministic test points from a parsed PRD document."""
    test_points = [_build_happy_path_test_point(document)]
    negative_path = _build_negative_path_test_point(document)
    if negative_path:
        test_points.append(negative_path)
    return test_points


# TODO: Add a few more deterministic extraction patterns before script generation starts.
