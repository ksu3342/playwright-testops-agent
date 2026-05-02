import pytest
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.rag.langchain_retriever import LocalKnowledgeRetriever, build_langchain_documents
from app.rag.retriever import retrieve_testing_context


def test_retrieve_testing_context_returns_ranked_local_sources() -> None:
    result = retrieve_testing_context(input_path="data/inputs/sample_prd_login.md", max_results=5)

    assert result["result_count"] >= 3
    assert result["retrieval_backend"] == "file_lexical"
    assert result["retrieval_implementation"] == "deterministic_file_lexical"

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
    assert result["retrieval_implementation"] == "deterministic_file_lexical"
    assert result["result_count"] >= 1
    assert {item["source_type"] for item in result["results"]} == {"selector_contract"}


def test_langchain_adapter_wraps_local_documents() -> None:
    documents = build_langchain_documents(source_types=["selector_contract", "product_doc"])

    assert documents
    assert all(isinstance(document, Document) for document in documents)
    assert any(document.metadata["source_type"] == "selector_contract" for document in documents)
    assert any(document.metadata["source_path"] == "data/contracts/demo_app_selectors.json" for document in documents)
    assert issubclass(LocalKnowledgeRetriever, BaseRetriever)


def test_retrieve_testing_context_supports_langchain_local_backend() -> None:
    result = retrieve_testing_context(
        query="login selectors and fixture data",
        max_results=5,
        source_types=["selector_contract", "test_data_contract", "product_doc"],
        backend="langchain_local",
    )

    assert result["retrieval_backend"] == "langchain_local"
    assert result["retrieval_implementation"] == "langchain_local_documents"
    assert result["result_count"] >= 3
    source_paths = [item["source_path"] for item in result["results"]]
    assert "data/contracts/demo_app_selectors.json" in source_paths
    assert "data/contracts/demo_app_test_data.json" in source_paths


def test_retrieve_testing_context_rejects_invalid_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported retrieval backend"):
        retrieve_testing_context(query="login", backend="not_a_backend")
