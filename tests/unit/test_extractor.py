from app.core.extractor import extract_test_points
from app.core.parser import parse_prd


def test_extract_test_points_for_search_document() -> None:
    document = parse_prd("data/inputs/sample_prd_search.md")
    test_points = extract_test_points(document)
    assert any("search" in point.title.lower() for point in test_points)
