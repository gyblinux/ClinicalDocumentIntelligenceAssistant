"""Typed records and configuration for embedding and retrieval."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypeAlias

from dotenv import load_dotenv

RetrievalSchemaVersion: TypeAlias = Literal["1.0"]
RetrievalStatus: TypeAlias = Literal["completed", "no_results", "failed"]
IndexStatus: TypeAlias = Literal["completed", "failed"]

RETRIEVAL_SCHEMA_VERSION: RetrievalSchemaVersion = "1.0"
MAX_RESULTS = 50


class RetrievalError(RuntimeError):
    """Base error for indexing and retrieval."""


class RetrievalInputError(RetrievalError):
    """Raised for an invalid corpus or command input."""


class RetrievalServiceError(RetrievalError):
    """Raised when TEI or Qdrant cannot complete an operation."""


class RetrievalOutputError(RetrievalError):
    """Raised when a local retrieval artifact cannot be written."""


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    """Local TEI and Qdrant configuration."""

    tei_url: str = "http://127.0.0.1:8080"
    tei_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384
    tei_batch_size: int = 32
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str | None = None

    def __post_init__(self) -> None:
        if not _is_http_url(self.tei_url):
            raise ValueError("tei_url must start with http:// or https://.")
        if not _is_http_url(self.qdrant_url):
            raise ValueError("qdrant_url must start with http:// or https://.")
        if not self.tei_model.strip():
            raise ValueError("tei_model cannot be empty.")
        if self.embedding_dimension < 1:
            raise ValueError("embedding_dimension must be at least 1.")
        if not 1 <= self.tei_batch_size <= 128:
            raise ValueError("tei_batch_size must be between 1 and 128.")

    @classmethod
    def from_env(cls, *, load_env_file: bool = True) -> RetrievalConfig:
        if load_env_file:
            load_dotenv()

        try:
            dimension = int(os.getenv("TEI_EMBEDDING_DIMENSION", "384"))
            batch_size = int(os.getenv("TEI_BATCH_SIZE", "32"))
        except ValueError as exc:
            raise ValueError("TEI dimension and batch size must be integers.") from exc

        api_key = os.getenv("QDRANT_API_KEY", "").strip() or None
        return cls(
            tei_url=os.getenv("TEI_URL", "http://127.0.0.1:8080").strip(),
            tei_model=os.getenv("TEI_MODEL", "BAAI/bge-small-en-v1.5").strip(),
            embedding_dimension=dimension,
            tei_batch_size=batch_size,
            qdrant_url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333").strip(),
            qdrant_api_key=api_key,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tei_url": self.tei_url,
            "tei_model": self.tei_model,
            "embedding_dimension": self.embedding_dimension,
            "tei_batch_size": self.tei_batch_size,
            "qdrant_url": self.qdrant_url,
            "qdrant_api_key_configured": self.qdrant_api_key is not None,
        }


@dataclass(frozen=True, slots=True)
class CorpusManifest:
    schema_version: str
    build_id: str
    status: str
    document_count: int
    chunk_count: int


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    document_id: str
    nct_id: str
    title: str
    source_url: str


@dataclass(frozen=True, slots=True)
class CorpusChunk:
    chunk_id: str
    document_id: str
    nct_id: str
    section: str
    text: str
    source_url: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class CorpusBundle:
    path: Path
    manifest: CorpusManifest
    documents: tuple[CorpusDocument, ...]
    chunks: tuple[CorpusChunk, ...]


@dataclass(frozen=True, slots=True)
class EmbeddingInfo:
    model_id: str
    dimension: int
    max_input_length: int | None
    model_sha: str | None = None


@dataclass(frozen=True, slots=True)
class IndexedPoint:
    point_id: str
    vector: tuple[float, ...]
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    score: float
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class IndexManifest:
    index_id: str
    created_at: datetime
    corpus_build_id: str
    corpus_status: str
    chunk_count: int
    point_count: int
    status: IndexStatus
    tei_model: str
    embedding_dimension: int
    qdrant_url: str
    collection: str
    replace_requested: bool
    errors: tuple[str, ...] = ()
    schema_version: RetrievalSchemaVersion = RETRIEVAL_SCHEMA_VERSION
    distance: str = "Cosine"
    tei_model_sha: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "index_id": self.index_id,
            "created_at": self.created_at.isoformat(),
            "corpus_build_id": self.corpus_build_id,
            "corpus_status": self.corpus_status,
            "chunk_count": self.chunk_count,
            "point_count": self.point_count,
            "status": self.status,
            "tei_model": self.tei_model,
            "tei_model_sha": self.tei_model_sha,
            "embedding_dimension": self.embedding_dimension,
            "qdrant_url": self.qdrant_url,
            "collection": self.collection,
            "distance": self.distance,
            "replace_requested": self.replace_requested,
            "errors": list(self.errors),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "index_id": self.index_id,
            "corpus_build_id": self.corpus_build_id,
            "collection": self.collection,
            "chunk_count": self.chunk_count,
            "point_count": self.point_count,
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class IndexOutcome:
    manifest: IndexManifest
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    text: str
    collection: str
    limit: int

    @classmethod
    def from_values(cls, text: str, collection: str, limit: int) -> RetrievalQuery:
        normalized_text = text.strip()
        normalized_collection = collection.strip()
        if not normalized_text:
            raise ValueError("query cannot be empty.")
        if not normalized_collection:
            raise ValueError("collection cannot be empty.")
        if not 1 <= limit <= MAX_RESULTS:
            raise ValueError(f"limit must be between 1 and {MAX_RESULTS}.")
        return cls(normalized_text, normalized_collection, limit)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "collection": self.collection,
            "limit": self.limit,
        }


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    rank: int
    score: float
    chunk_id: str
    document_id: str
    nct_id: str
    section: str
    text: str
    source_url: str
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "score": self.score,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "nct_id": self.nct_id,
            "section": self.section,
            "text": self.text,
            "source_url": self.source_url,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class RetrievalRun:
    retrieval_id: str
    created_at: datetime
    query: RetrievalQuery
    tei_model: str
    collection: str
    status: RetrievalStatus
    results: tuple[RetrievalResult, ...]
    errors: tuple[str, ...] = ()
    schema_version: RetrievalSchemaVersion = RETRIEVAL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "retrieval_id": self.retrieval_id,
            "created_at": self.created_at.isoformat(),
            "query": self.query.to_dict(),
            "tei_model": self.tei_model,
            "collection": self.collection,
            "results": [result.to_dict() for result in self.results],
            "status": self.status,
            "errors": list(self.errors),
        }


def _is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))
