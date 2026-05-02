from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.collector import REPO_ROOT


KB_DIR = REPO_ROOT / "data" / "kb"
KB_INDEX_PATH = KB_DIR / "index.json"
KB_UPLOADED_DIR = KB_DIR / "uploaded"

ALLOWED_SOURCE_TYPES = {
    "product_doc",
    "test_guideline",
    "selector_contract",
    "test_data_contract",
    "run_history",
    "bug_report",
    "note",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative_to_repo(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _resolve_repo_file(path: str) -> Path:
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (REPO_ROOT / candidate).resolve()
    repo_root = REPO_ROOT.resolve()
    if resolved != repo_root and repo_root not in resolved.parents:
        raise ValueError(f"source_path must stay inside the repository: {path}")
    if not resolved.is_file():
        raise FileNotFoundError(f"source_path was not found: {path}")
    return resolved


def _validate_metadata(metadata: Optional[dict[str, Any]]) -> dict[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a JSON object.")
    try:
        json.dumps(metadata, ensure_ascii=False)
    except TypeError as exc:
        raise ValueError("metadata must be JSON serializable.") from exc
    return dict(metadata)


def _document_id_for(source_type: str, source_path: Optional[str], content: Optional[str]) -> str:
    if source_path:
        seed = f"path:{source_path}"
    else:
        content_digest = hashlib.sha256((content or "").encode("utf-8")).hexdigest()
        seed = f"content:{source_type}:{content_digest}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"kb_{digest[:16]}"


def load_kb_index(index_path: Optional[Path] = None) -> dict[str, list[dict[str, Any]]]:
    index_path = index_path or KB_INDEX_PATH
    if not index_path.is_file():
        return {"documents": []}

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("KB index must be a JSON object.")

    documents = payload.get("documents", [])
    if not isinstance(documents, list):
        raise ValueError("KB index field 'documents' must be a list.")

    return {"documents": [document for document in documents if isinstance(document, dict)]}


def save_kb_index(index: dict[str, list[dict[str, Any]]], index_path: Optional[Path] = None) -> None:
    index_path = index_path or KB_INDEX_PATH
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def ingest_document(
    source_type: str,
    source_path: Optional[str] = None,
    content: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Add or update one file-backed KB document.

    Content ingestion writes a markdown file under data/kb/uploaded and indexes
    that file. Existing file ingestion indexes the repo-relative source path.
    """
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise ValueError(f"Unsupported source_type: {source_type}")

    normalized_content = content if content and content.strip() else None
    if not source_path and normalized_content is None:
        raise ValueError("Provide source_path or non-empty content.")

    metadata_payload = _validate_metadata(metadata)
    original_source_path: Optional[str] = None
    if source_path:
        original_source_path = _relative_to_repo(_resolve_repo_file(source_path))

    document_id = _document_id_for(source_type, original_source_path, normalized_content)
    indexed_source_path = original_source_path

    if normalized_content is not None:
        KB_UPLOADED_DIR.mkdir(parents=True, exist_ok=True)
        uploaded_path = KB_UPLOADED_DIR / f"{document_id}.md"
        uploaded_path.write_text(normalized_content, encoding="utf-8")
        indexed_source_path = _relative_to_repo(uploaded_path)
        if original_source_path:
            metadata_payload.setdefault("original_source_path", original_source_path)

    if indexed_source_path is None:
        raise ValueError("No indexable source path was resolved.")

    record = {
        "document_id": document_id,
        "source_type": source_type,
        "source_path": indexed_source_path,
        "indexed_at": _utc_now(),
        "metadata": metadata_payload,
    }

    index = load_kb_index()
    documents = [document for document in index["documents"] if document.get("document_id") != document_id]
    documents.append(record)
    documents.sort(key=lambda item: str(item.get("source_path", "")))
    save_kb_index({"documents": documents})
    return record
