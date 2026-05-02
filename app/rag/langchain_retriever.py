from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from app.core.collector import REPO_ROOT
from app.rag.retriever import (
    KnowledgeDocument,
    _iter_documents,
    _rank_documents,
    _relative_to_repo,
    _select_documents,
    _tokenize,
)


def build_langchain_documents(source_types: Optional[list[str]] = None) -> list[Document]:
    allowed_source_types = {source_type for source_type in (source_types or []) if source_type}
    documents: list[Document] = []
    for document in _iter_documents():
        if allowed_source_types and document.source_type not in allowed_source_types:
            continue
        documents.append(_to_langchain_document(document))
    return documents


class LocalKnowledgeRetriever(BaseRetriever):
    """LangChain retriever over the repo's deterministic local KB documents."""

    documents: list[Document]
    source_types: Optional[list[str]] = None
    max_results: int = 5

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        query_tokens = set(_tokenize(query))
        allowed_source_types = {source_type for source_type in (self.source_types or []) if source_type}
        knowledge_documents = [_from_langchain_document(document) for document in self.documents]
        selected = _select_documents(
            _rank_documents(knowledge_documents, query_tokens, allowed_source_types),
            self.max_results,
        )
        return [
            _to_langchain_document(document, score=score, rank=index)
            for index, (score, document) in enumerate(selected, start=1)
        ]


def retrieve_langchain_local_documents(
    query_text: str,
    max_results: int = 5,
    source_types: Optional[list[str]] = None,
) -> list[tuple[int, KnowledgeDocument]]:
    retriever = LocalKnowledgeRetriever(
        documents=build_langchain_documents(),
        source_types=source_types,
        max_results=max_results,
    )
    documents = retriever.invoke(query_text)
    selected: list[tuple[int, KnowledgeDocument]] = []
    for document in documents:
        score = document.metadata.get("score")
        selected.append((int(score) if isinstance(score, int) else 0, _from_langchain_document(document)))
    return selected


def _to_langchain_document(
    document: KnowledgeDocument,
    score: Optional[int] = None,
    rank: Optional[int] = None,
) -> Document:
    metadata: dict[str, Any] = {
        "source_type": document.source_type,
        "source_path": _relative_to_repo(document.source_path),
        "document_metadata": document.metadata,
    }
    if score is not None:
        metadata["score"] = score
    if rank is not None:
        metadata["rank"] = rank
    return Document(page_content=document.text, metadata=metadata)


def _from_langchain_document(document: Document) -> KnowledgeDocument:
    source_type = str(document.metadata.get("source_type", "note"))
    source_path = str(document.metadata.get("source_path", ""))
    document_metadata = document.metadata.get("document_metadata")
    resolved_path = (REPO_ROOT / source_path).resolve() if source_path else Path("").resolve()
    return KnowledgeDocument(
        source_type=source_type,
        source_path=resolved_path,
        text=document.page_content,
        metadata=dict(document_metadata) if isinstance(document_metadata, dict) else {},
    )


__all__ = [
    "LocalKnowledgeRetriever",
    "build_langchain_documents",
    "retrieve_langchain_local_documents",
]
