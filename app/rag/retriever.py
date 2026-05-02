from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.collector import REPO_ROOT, RUNS_DIR
from app.rag.ingest import KB_INDEX_PATH, load_kb_index


SUPPORTED_TEXT_SUFFIXES = {".md", ".txt", ".json"}
MAX_EXCERPT_CHARS = 420
RUN_HISTORY_LIMIT = 20
BUG_REPORT_LIMIT = 20
MAX_RESULTS_PER_SOURCE_TYPE = 2
SOURCE_TYPE_PRIORITY = {
    "selector_contract": 40,
    "test_data_contract": 35,
    "product_doc": 20,
    "test_guideline": 15,
    "run_history": 5,
    "bug_report": 0,
    "note": 0,
}


@dataclass(frozen=True)
class KnowledgeSource:
    source_type: str
    root: Path


@dataclass(frozen=True)
class KnowledgeDocument:
    source_type: str
    source_path: Path
    text: str
    metadata: dict[str, Any]


KNOWLEDGE_SOURCES = (
    KnowledgeSource("product_doc", REPO_ROOT / "data" / "kb" / "product_docs"),
    KnowledgeSource("test_guideline", REPO_ROOT / "data" / "kb" / "test_guidelines"),
    KnowledgeSource("contract", REPO_ROOT / "data" / "contracts"),
    KnowledgeSource("run_history", RUNS_DIR),
    KnowledgeSource("bug_report", REPO_ROOT / "generated" / "reports"),
)


def _relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    repo_candidate = (REPO_ROOT / candidate).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return candidate.resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _json_metadata(path: Path, fallback_source_type: str) -> tuple[str, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    source_type = fallback_source_type
    try:
        payload = json.loads(_read_text(path))
    except json.JSONDecodeError:
        return source_type, metadata

    if not isinstance(payload, dict):
        return source_type, metadata

    app_name = payload.get("app")
    if isinstance(app_name, str):
        metadata["app"] = app_name

    selectors = payload.get("selectors")
    if isinstance(selectors, dict):
        source_type = "selector_contract"
        metadata["selector_keys"] = sorted(str(key) for key in selectors)

    fixtures = payload.get("fixtures")
    if isinstance(fixtures, dict):
        source_type = "test_data_contract"
        metadata["fixture_keys"] = sorted(str(key) for key in fixtures)

    if path.name == "summary.json":
        source_type = "run_history"
        for key in ("run_id", "status", "target_script", "reason", "report_path"):
            value = payload.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                metadata[key] = value

    return source_type, metadata


def _iter_static_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return ()
    return (
        path
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file() and path.suffix.lower() in SUPPORTED_TEXT_SUFFIXES
    )


def _iter_recent_files(root: Path, pattern: str, limit: int) -> Iterable[Path]:
    if not root.is_dir():
        return ()
    candidates = [path for path in root.glob(pattern) if path.is_file()]
    candidates.sort(key=lambda item: (item.stat().st_mtime, item.as_posix()), reverse=True)
    return candidates[:limit]


def _iter_source_files(source: KnowledgeSource) -> Iterable[Path]:
    if source.source_type == "run_history":
        return _iter_recent_files(source.root, "*/summary.json", RUN_HISTORY_LIMIT)
    if source.source_type == "bug_report":
        return _iter_recent_files(source.root, "*.md", BUG_REPORT_LIMIT)
    return _iter_static_files(source.root)


def _load_document(source: KnowledgeSource, path: Path) -> Optional[KnowledgeDocument]:
    try:
        text = _read_text(path)
    except OSError:
        return None

    source_type = source.source_type
    metadata: dict[str, Any] = {}
    if path.suffix.lower() == ".json":
        source_type, metadata = _json_metadata(path, source.source_type)

    return KnowledgeDocument(
        source_type=source_type,
        source_path=path,
        text=text,
        metadata=metadata,
    )


def _resolve_indexed_path(path: str) -> Optional[Path]:
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (REPO_ROOT / candidate).resolve()
    repo_root = REPO_ROOT.resolve()
    if resolved != repo_root and repo_root not in resolved.parents:
        return None
    if not resolved.is_file() or resolved.suffix.lower() not in SUPPORTED_TEXT_SUFFIXES:
        return None
    return resolved


def _iter_index_documents() -> Iterable[KnowledgeDocument]:
    try:
        index = load_kb_index(KB_INDEX_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        return ()

    documents: list[KnowledgeDocument] = []
    for record in index["documents"]:
        source_type = record.get("source_type")
        source_path = record.get("source_path")
        if not isinstance(source_type, str) or not isinstance(source_path, str):
            continue

        resolved_path = _resolve_indexed_path(source_path)
        if resolved_path is None:
            continue

        try:
            text = _read_text(resolved_path)
        except OSError:
            continue

        metadata = record.get("metadata")
        metadata_payload = dict(metadata) if isinstance(metadata, dict) else {}
        metadata_payload["document_id"] = record.get("document_id")
        metadata_payload["indexed_at"] = record.get("indexed_at")

        if resolved_path.suffix.lower() == ".json":
            inferred_source_type, json_metadata = _json_metadata(resolved_path, source_type)
            metadata_payload = {**json_metadata, **metadata_payload}
            if source_type not in SOURCE_TYPE_PRIORITY:
                source_type = inferred_source_type

        documents.append(
            KnowledgeDocument(
                source_type=source_type,
                source_path=resolved_path,
                text=text,
                metadata=metadata_payload,
            )
        )
    return documents


def _iter_documents() -> Iterable[KnowledgeDocument]:
    seen: set[tuple[str, Path]] = set()
    for document in _iter_index_documents():
        key = (document.source_type, document.source_path.resolve())
        if key in seen:
            continue
        seen.add(key)
        yield document

    for source in KNOWLEDGE_SOURCES:
        for path in _iter_source_files(source):
            document = _load_document(source, path)
            if document is not None:
                key = (document.source_type, document.source_path.resolve())
                if key in seen:
                    continue
                seen.add(key)
                yield document


def _query_text(input_path: Optional[str], query: Optional[str]) -> str:
    if query and query.strip():
        return query.strip()
    if not input_path:
        return ""

    resolved = _resolve_repo_path(input_path)
    if resolved.is_file():
        return _read_text(resolved)
    return input_path


def _score_document(query_tokens: set[str], document: KnowledgeDocument) -> int:
    if not query_tokens:
        return 0

    metadata_text = json.dumps(document.metadata, ensure_ascii=False, sort_keys=True)
    searchable = f"{document.source_path.stem} {document.source_type} {metadata_text} {document.text}"
    token_counts = Counter(_tokenize(searchable))
    lexical_score = sum(token_counts.get(token, 0) for token in query_tokens)
    if lexical_score <= 0:
        return 0
    return lexical_score + SOURCE_TYPE_PRIORITY.get(document.source_type, 0)


def _excerpt(text: str, query_tokens: set[str]) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= MAX_EXCERPT_CHARS:
        return normalized

    lowered = normalized.lower()
    positions = [lowered.find(token) for token in query_tokens if lowered.find(token) >= 0]
    center = min(positions) if positions else 0
    start = max(center - MAX_EXCERPT_CHARS // 3, 0)
    end = min(start + MAX_EXCERPT_CHARS, len(normalized))
    return normalized[start:end].strip()


def _knowledge_root_payload() -> list[dict[str, str]]:
    roots = [
        {
            "source_type": source.source_type,
            "root": _relative_to_repo(source.root),
        }
        for source in KNOWLEDGE_SOURCES
    ]
    roots.append({"source_type": "kb_index", "root": _relative_to_repo(KB_INDEX_PATH)})
    return roots


def retrieve_testing_context(
    input_path: Optional[str] = None,
    query: Optional[str] = None,
    max_results: int = 5,
    source_types: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Retrieve local testing context before scaffold generation.

    This is deliberately deterministic and file-backed. It is RAG plumbing for
    product docs, test guidelines, selector/test-data contracts, recent run
    summaries, and bug report drafts; it is not a vector database.
    """
    query_text = _query_text(input_path, query)
    query_tokens = set(_tokenize(query_text))
    allowed_source_types = {source_type for source_type in (source_types or []) if source_type}
    scored: list[tuple[int, KnowledgeDocument]] = []

    for document in _iter_documents():
        if allowed_source_types and document.source_type not in allowed_source_types:
            continue
        score = _score_document(query_tokens, document)
        if score > 0:
            scored.append((score, document))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].source_type,
            _relative_to_repo(item[1].source_path),
        )
    )

    desired_count = max(max_results, 0)
    selected: list[tuple[int, KnowledgeDocument]] = []
    source_type_counts: dict[str, int] = {}
    for score, document in scored:
        if len(selected) >= desired_count:
            break
        current_count = source_type_counts.get(document.source_type, 0)
        if current_count >= MAX_RESULTS_PER_SOURCE_TYPE:
            continue
        selected.append((score, document))
        source_type_counts[document.source_type] = current_count + 1

    if len(selected) < desired_count:
        selected_paths = {document.source_path for _, document in selected}
        for score, document in scored:
            if len(selected) >= desired_count:
                break
            if document.source_path in selected_paths:
                continue
            selected.append((score, document))
            selected_paths.add(document.source_path)

    results = [
        {
            "rank": index,
            "source_type": document.source_type,
            "source_path": _relative_to_repo(document.source_path),
            "score": score,
            "excerpt": _excerpt(document.text, query_tokens),
            "metadata": document.metadata,
        }
        for index, (score, document) in enumerate(selected, start=1)
    ]

    return {
        "input_path": input_path,
        "query": query if query is not None else None,
        "source_types": sorted(allowed_source_types) if allowed_source_types else None,
        "retrieval_backend": "file_lexical",
        "query_token_count": len(query_tokens),
        "knowledge_roots": _knowledge_root_payload(),
        "result_count": len(results),
        "results": results,
    }
