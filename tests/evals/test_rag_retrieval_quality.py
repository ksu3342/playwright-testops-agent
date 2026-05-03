from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.reporter import create_bug_report_from_run
from app.core.runner import run_test_script
from app.rag.retriever import retrieve_testing_context


@dataclass(frozen=True)
class RetrievalEvalCase:
    name: str
    query: str
    source_types: list[str]
    expected_source_type: str
    expected_source_path: str | None
    min_hits: int


STATIC_EVAL_CASES = [
    RetrievalEvalCase(
        name="login_selector_contract",
        query="login email_input password_input submit_button selector contract",
        source_types=["selector_contract"],
        expected_source_type="selector_contract",
        expected_source_path="data/contracts/demo_app_selectors.json",
        min_hits=1,
    ),
    RetrievalEvalCase(
        name="login_test_data_contract",
        query="login valid_email valid_password test fixture data",
        source_types=["test_data_contract"],
        expected_source_type="test_data_contract",
        expected_source_path="data/contracts/demo_app_test_data.json",
        min_hits=1,
    ),
    RetrievalEvalCase(
        name="search_selector_contract",
        query="search input submit button empty_state results_list selector",
        source_types=["selector_contract"],
        expected_source_type="selector_contract",
        expected_source_path="data/contracts/demo_app_selectors.json",
        min_hits=1,
    ),
    RetrievalEvalCase(
        name="product_doc_login",
        query="login dashboard visible success signal product notes",
        source_types=["product_doc"],
        expected_source_type="product_doc",
        expected_source_path="data/kb/product_docs/demo_app.md",
        min_hits=1,
    ),
    RetrievalEvalCase(
        name="test_guideline_selector_policy",
        query="do not guess missing selectors stable data-testid guideline",
        source_types=["test_guideline"],
        expected_source_type="test_guideline",
        expected_source_path="data/kb/test_guidelines/playwright_guidelines.md",
        min_hits=1,
    ),
]


@pytest.mark.parametrize("case", STATIC_EVAL_CASES, ids=[case.name for case in STATIC_EVAL_CASES])
def test_static_retrieval_eval_cases_hit_expected_sources(case: RetrievalEvalCase) -> None:
    result = retrieve_testing_context(
        query=case.query,
        source_types=case.source_types,
        max_results=5,
    )

    assert result["result_count"] >= case.min_hits
    assert any(item["source_type"] == case.expected_source_type for item in result["results"])
    if case.expected_source_path:
        assert case.expected_source_path in [item["source_path"] for item in result["results"]]


def test_historical_failure_eval_hits_run_summary_and_bug_report() -> None:
    run_result = run_test_script("tests/assets/runner_fail_case.py")
    report_result = create_bug_report_from_run(run_result["run_dir"])

    result = retrieve_testing_context(
        query=f"{run_result['run_id']} failed run bug report draft",
        source_types=["run_history", "bug_report"],
        max_results=5,
    )

    source_types = {item["source_type"] for item in result["results"]}
    source_paths = [item["source_path"] for item in result["results"]]
    assert "run_history" in source_types
    assert "bug_report" in source_types
    assert run_result["artifact_paths"]["summary"] in source_paths
    assert report_result["report_path"] in source_paths


def test_missing_context_eval_returns_no_false_positive_for_unknown_selector() -> None:
    result = retrieve_testing_context(
        query="nonexistent_semantic_key_zzzzzz",
        source_types=["selector_contract"],
        max_results=5,
    )

    assert result["result_count"] == 0
    assert result["results"] == []
