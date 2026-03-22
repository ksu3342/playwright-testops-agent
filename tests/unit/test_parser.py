from app.core.parser import parse_prd


def test_parse_prd_reads_title_and_summary() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    assert document.title == "Login Page PRD"
    assert "login" in document.summary.lower()
