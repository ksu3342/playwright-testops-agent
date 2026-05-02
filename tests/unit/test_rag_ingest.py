import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.collector import REPO_ROOT
from app.rag import ingest as ingest_module
from app.rag import retriever as retriever_module


@pytest.fixture()
def isolated_kb(monkeypatch: pytest.MonkeyPatch):
    test_root = REPO_ROOT / "data" / "kb" / f"_test_{uuid4().hex}"
    index_path = test_root / "index.json"
    uploaded_dir = test_root / "uploaded"

    monkeypatch.setattr(ingest_module, "KB_INDEX_PATH", index_path)
    monkeypatch.setattr(ingest_module, "KB_UPLOADED_DIR", uploaded_dir)
    monkeypatch.setattr(retriever_module, "KB_INDEX_PATH", index_path)

    try:
        yield index_path
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def test_ingest_document_writes_file_backed_index(isolated_kb: Path) -> None:
    unique_token = f"p5unitwrite{uuid4().hex}"

    record = ingest_module.ingest_document(
        source_type="note",
        content=f"{unique_token} should be indexed.",
        metadata={"module": "p5"},
    )

    assert isolated_kb.is_file()
    payload = json.loads(isolated_kb.read_text(encoding="utf-8"))

    assert payload["documents"] == [record]
    assert record["document_id"].startswith("kb_")
    assert record["source_type"] == "note"
    assert record["source_path"].startswith("data/kb/_test_")
    assert record["indexed_at"]
    assert record["metadata"] == {"module": "p5"}


def test_ingest_same_source_path_updates_without_duplicate_index_records(isolated_kb: Path) -> None:
    first = ingest_module.ingest_document(
        source_type="product_doc",
        source_path="data/kb/product_docs/demo_app.md",
        metadata={"version": 1},
    )
    second = ingest_module.ingest_document(
        source_type="product_doc",
        source_path="data/kb/product_docs/demo_app.md",
        metadata={"version": 2},
    )

    payload = json.loads(isolated_kb.read_text(encoding="utf-8"))

    assert first["document_id"] == second["document_id"]
    assert len(payload["documents"]) == 1
    assert payload["documents"][0]["metadata"] == {"version": 2}


def test_ingest_rejects_source_path_outside_repo(isolated_kb: Path) -> None:
    with pytest.raises(ValueError, match="inside the repository"):
        ingest_module.ingest_document(
            source_type="note",
            source_path="../outside_repo.md",
        )


def test_retriever_returns_indexed_document(isolated_kb: Path) -> None:
    unique_token = f"p5unitsearch{uuid4().hex}"
    record = ingest_module.ingest_document(
        source_type="note",
        content=f"{unique_token} is only present in the uploaded KB document.",
    )

    result = retriever_module.retrieve_testing_context(query=unique_token, max_results=5)

    assert result["result_count"] >= 1
    assert any(item["source_path"] == record["source_path"] for item in result["results"])
    assert any(item["metadata"]["document_id"] == record["document_id"] for item in result["results"])


def test_retriever_keeps_indexed_search_results_bounded(isolated_kb: Path) -> None:
    unique_token = f"p5unitlimit{uuid4().hex}"
    for source_type in ("note", "product_doc", "test_guideline", "bug_report"):
        ingest_module.ingest_document(
            source_type=source_type,
            content=f"{unique_token} indexed content for {source_type}.",
        )

    result = retriever_module.retrieve_testing_context(query=unique_token, max_results=2)

    assert result["result_count"] == 2
    assert len(result["results"]) == 2
