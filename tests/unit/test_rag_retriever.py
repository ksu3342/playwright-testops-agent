from app.rag.retriever import retrieve_testing_context


def test_retrieve_testing_context_returns_ranked_local_sources() -> None:
    result = retrieve_testing_context(input_path="data/inputs/sample_prd_login.md", max_results=5)

    assert result["result_count"] >= 3

    source_paths = [item["source_path"] for item in result["results"]]
    source_types = {item["source_type"] for item in result["results"]}

    assert "data/contracts/demo_app_selectors.json" in source_paths
    assert "data/contracts/demo_app_test_data.json" in source_paths
    assert "data/kb/product_docs/demo_app.md" in source_paths
    assert "selector_contract" in source_types
    assert "test_data_contract" in source_types


def test_retrieve_testing_context_keeps_results_bounded() -> None:
    result = retrieve_testing_context(query="login selectors and fixture data", max_results=2)

    assert result["result_count"] == 2
    assert len(result["results"]) == 2
    assert all(len(item["excerpt"]) <= 420 for item in result["results"])


def test_retrieve_testing_context_filters_by_source_types() -> None:
    result = retrieve_testing_context(
        query="login selectors and fixture data",
        max_results=5,
        source_types=["selector_contract"],
    )

    assert result["source_types"] == ["selector_contract"]
    assert result["retrieval_backend"] == "file_lexical"
    assert result["result_count"] >= 1
    assert {item["source_type"] for item in result["results"]} == {"selector_contract"}
