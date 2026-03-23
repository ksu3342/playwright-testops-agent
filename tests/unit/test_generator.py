from pathlib import Path

from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.parser import parse_prd


def test_login_input_generates_script_under_generated_tests() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    output_path = generate_test_script(document, test_points)
    content = output_path.read_text(encoding="utf-8")

    assert output_path == Path("generated/tests/test_login_generated.py")
    assert output_path.exists()
    assert "TP-001" in content
    assert "User Login happy path works as described" in content
    assert "# TODO:" in content
    assert "page.goto" in content


def test_search_input_generates_script_without_invented_selectors() -> None:
    document = parse_prd("data/inputs/sample_prd_search.md")
    test_points = extract_test_points(document)
    output_path = generate_test_script(document, test_points)
    content = output_path.read_text(encoding="utf-8")

    assert output_path == Path("generated/tests/test_search_generated.py")
    assert output_path.exists()
    assert "TP-002" in content
    assert "Empty state is shown when no result matches the keyword" in content
    assert "# TODO: Locate the relevant input selector" in content
    assert "#email" not in content
    assert "#password" not in content
    assert "#login-button" not in content
