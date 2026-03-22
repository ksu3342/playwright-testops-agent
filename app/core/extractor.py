from app.schemas.prd_schema import PRDDocument
from app.schemas.testpoint_schema import TestPoint


def extract_test_points(document: PRDDocument) -> list[TestPoint]:
    """Create a few obvious test points from a simple text description."""
    text = document.raw_text.lower()
    test_points = [
        TestPoint(
            id="TP-001",
            title="Page loads without blocking errors",
            rationale="Basic smoke coverage for the described page or flow.",
        )
    ]
    if "login" in text:
        test_points.append(
            TestPoint(
                id="TP-002",
                title="User can submit login credentials",
                rationale="Login is explicitly mentioned in the input.",
            )
        )
    if "search" in text:
        test_points.append(
            TestPoint(
                id="TP-003",
                title="User can perform a search and view results",
                rationale="Search behavior is explicitly mentioned in the input.",
            )
        )
    return test_points


# TODO: Add extraction rules that map user flows to clearer assertions.
