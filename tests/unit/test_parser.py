from app.core.parser import parse_prd


def test_parse_prd_reads_structured_sections() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    assert document.title == "Login Page PRD"
    assert document.feature_name == "User Login"
    assert document.page_url == "/login"
    assert document.preconditions == [
        "User account already exists",
        "User can access the login page",
    ]
    assert document.user_actions[0] == "Enter a valid email address"
    assert document.expected_results[-1] == "No blocking validation error is shown for valid credentials"
    assert document.missing_sections == []


def test_parse_prd_reports_missing_sections_honestly() -> None:
    document = parse_prd("data/inputs/sample_prd_search.md")
    assert document.title == "Search Page PRD"
    assert document.feature_name == "Keyword Search"
    assert "Preconditions" not in document.missing_sections
