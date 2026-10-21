"""Validation and loading for feature 003 corpus artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinical_doc_assist.retrieval.models import (
    CorpusBundle,
    CorpusChunk,
    CorpusDocument,
    CorpusManifest,
    RetrievalInputError,
)

CORPUS_SCHEMA_VERSION = "1.0"


def load_corpus(path: Path) -> CorpusBundle:
    """Load a valid, non-empty feature 003 corpus."""

    manifest_path = path / "manifest.json"
    documents_path = path / "documents.jsonl"
    chunks_path = path / "chunks.jsonl"
    try:
        manifest_data = _read_json(manifest_path)
        document_records = _read_jsonl(documents_path)
        chunk_records = _read_jsonl(chunks_path)
    except OSError as exc:
        raise RetrievalInputError(f"Cannot read corpus {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RetrievalInputError(f"Corpus {path} contains invalid JSON: {exc}") from exc

    schema_version = manifest_data.get("schema_version")
    if schema_version != CORPUS_SCHEMA_VERSION:
        raise RetrievalInputError(f"Corpus schema_version must be {CORPUS_SCHEMA_VERSION}.")

    status = manifest_data.get("status")
    if status not in {"completed", "partial"}:
        raise RetrievalInputError("Corpus status must be completed or partial.")

    build_id = manifest_data.get("build_id")
    if not isinstance(build_id, str) or not build_id:
        raise RetrievalInputError("Corpus build_id is required.")

    document_count = _required_int(manifest_data, "document_count")
    chunk_count = _required_int(manifest_data, "chunk_count")
    if chunk_count == 0:
        raise RetrievalInputError("Corpus has no chunks.")
    if chunk_count != len(chunk_records):
        raise RetrievalInputError("Corpus chunk_count does not match chunks.jsonl.")
    if document_count != len(document_records):
        raise RetrievalInputError("Corpus document_count does not match documents.jsonl.")

    documents = tuple(_document_from_dict(item) for item in document_records)
    document_ids = {document.document_id for document in documents}
    chunks = tuple(_chunk_from_dict(item) for item in chunk_records)
    missing_documents = {
        chunk.document_id for chunk in chunks if chunk.document_id not in document_ids
    }
    if missing_documents:
        raise RetrievalInputError(
            "Corpus chunks reference missing documents: " + ", ".join(sorted(missing_documents))
        )

    return CorpusBundle(
        path=path,
        manifest=CorpusManifest(
            schema_version=schema_version,
            build_id=build_id,
            status=status,
            document_count=document_count,
            chunk_count=chunk_count,
        ),
        documents=documents,
        chunks=chunks,
    )


def _document_from_dict(record: dict[str, Any]) -> CorpusDocument:
    try:
        title = record.get("title")
        return CorpusDocument(
            document_id=_required_str(record, "document_id"),
            nct_id=_required_str(record, "nct_id"),
            title=title if isinstance(title, str) else "",
            source_url=_required_str(record, "source_url"),
        )
    except ValueError as exc:
        raise RetrievalInputError(f"Invalid corpus document: {exc}") from exc


def _chunk_from_dict(record: dict[str, Any]) -> CorpusChunk:
    try:
        return CorpusChunk(
            chunk_id=_required_str(record, "chunk_id"),
            document_id=_required_str(record, "document_id"),
            nct_id=_required_str(record, "nct_id"),
            section=_required_str(record, "section"),
            text=_required_str(record, "text"),
            source_url=_required_str(record, "source_url"),
            content_hash=_required_str(record, "content_hash"),
        )
    except ValueError as exc:
        raise RetrievalInputError(f"Invalid corpus chunk: {exc}") from exc


def _required_str(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_int(record: dict[str, Any], key: str) -> int:
    value = record.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RetrievalInputError(f"Corpus {key} must be a non-negative integer.")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise json.JSONDecodeError("Expected JSON object", "", 0)
    return payload


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise json.JSONDecodeError(
                    f"Line {line_number} must be a JSON object",
                    line,
                    line_number,
                )
            records.append(value)
    return tuple(records)
