from app.core.extractor import extract_test_points
from app.core.parser import parse_prd


def test_login_prd_produces_at_least_one_happy_path_test_point() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    happy_paths = [point for point in test_points if point.type == "happy_path"]
    assert len(happy_paths) >= 1
    assert happy_paths[0].steps == document.user_actions
    assert not any(point.type == "negative_path" for point in test_points)


def test_search_prd_produces_happy_path_and_no_result_negative_path() -> None:
    document = parse_prd("data/inputs/sample_prd_search.md")
    test_points = extract_test_points(document)
    assert any(point.type == "happy_path" for point in test_points)
    negative_paths = [point for point in test_points if point.type == "negative_path"]
    assert len(negative_paths) >= 1
    assert "empty state" in negative_paths[0].expected_result.lower()


def test_extractor_output_fields_are_structurally_valid() -> None:
    document = parse_prd("data/inputs/sample_prd_search.md")
    test_points = extract_test_points(document)
    for point in test_points:
        assert point.id.startswith("TP-")
        assert point.title
        assert point.type in {"happy_path", "negative_path"}
        assert isinstance(point.preconditions, list)
        assert isinstance(point.steps, list)
        assert point.expected_result
        assert point.source_sections == ["Preconditions", "User Actions", "Expected Results"]
        assert point.rationale
