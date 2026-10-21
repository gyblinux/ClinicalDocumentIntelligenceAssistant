"""Index and retrieval orchestration."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from clinical_doc_assist.retrieval.corpus import load_corpus
from clinical_doc_assist.retrieval.models import (
    CorpusChunk,
    EmbeddingInfo,
    IndexedPoint,
    IndexManifest,
    IndexOutcome,
    IndexStatus,
    RetrievalConfig,
    RetrievalOutputError,
    RetrievalQuery,
    RetrievalResult,
    RetrievalRun,
    RetrievalServiceError,
    VectorSearchHit,
)
from clinical_doc_assist.retrieval.qdrant import point_id_for_chunk


class TEIService(Protocol):
    def health(self) -> None: ...

    def info(self) -> EmbeddingInfo: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class VectorStore(Protocol):
    def health(self) -> None: ...

    def ensure_collection(self, dimension: int, *, replace: bool) -> None: ...

    def upsert(self, points: list[IndexedPoint]) -> int: ...

    def search(
        self,
        vector: list[float],
        *,
        limit: int,
    ) -> list[VectorSearchHit]: ...


class RetrievalService:
    """Coordinate TEI embedding and Qdrant storage/search."""

    def __init__(
        self,
        *,
        config: RetrievalConfig,
        tei: TEIService,
        vector_store: VectorStore,
        now: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        manifest_dir: Path = Path("artifacts/index-runs"),
    ) -> None:
        self._config = config
        self._tei = tei
        self._vector_store = vector_store
        self._now = now or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: uuid4().hex[:16])
        self._manifest_dir = manifest_dir

    def index_corpus(
        self,
        corpus_path: Path,
        *,
        collection: str,
        replace: bool = False,
    ) -> IndexOutcome:
        corpus = load_corpus(corpus_path)
        index_id = f"index-{self._id_factory()}"
        created_at = self._now()
        point_count = 0
        errors: list[str] = []
        status: IndexStatus = "completed"
        model_sha: str | None = None

        try:
            model_info = self._preflight_services()
            model_sha = model_info.model_sha
            self._vector_store.ensure_collection(
                self._config.embedding_dimension,
                replace=replace,
            )
            for start in range(0, len(corpus.chunks), self._config.tei_batch_size):
                batch = corpus.chunks[start : start + self._config.tei_batch_size]
                vectors = self._tei.embed([chunk.text for chunk in batch])
                points = [
                    _indexed_point(chunk, vector)
                    for chunk, vector in zip(batch, vectors, strict=True)
                ]
                point_count += self._vector_store.upsert(points)
        except RetrievalServiceError as exc:
            status = "failed"
            errors.append(str(exc))

        manifest = IndexManifest(
            index_id=index_id,
            created_at=created_at,
            corpus_build_id=corpus.manifest.build_id,
            corpus_status=corpus.manifest.status,
            chunk_count=len(corpus.chunks),
            point_count=point_count,
            status=status,
            tei_model=self._config.tei_model,
            embedding_dimension=self._config.embedding_dimension,
            qdrant_url=self._config.qdrant_url,
            collection=collection,
            replace_requested=replace,
            errors=tuple(errors),
            tei_model_sha=model_sha,
        )
        manifest_path = self._manifest_dir / f"{index_id}.json"
        write_json_atomic(manifest_path, manifest.to_dict())
        return IndexOutcome(manifest, manifest_path)

    def search_evidence(
        self,
        text: str,
        *,
        collection: str,
        limit: int = 5,
    ) -> RetrievalRun:
        query = RetrievalQuery.from_values(text, collection, limit)
        self._preflight_services()
        vectors = self._tei.embed([query.text])
        if len(vectors) != 1:
            raise RetrievalServiceError("TEI did not return one query embedding.")

        hits = self._vector_store.search(vectors[0], limit=query.limit)
        results = tuple(_retrieval_result(rank, hit) for rank, hit in enumerate(hits, start=1))
        return RetrievalRun(
            retrieval_id=f"retrieval-{self._id_factory()}",
            created_at=self._now(),
            query=query,
            tei_model=self._config.tei_model,
            collection=collection,
            status="completed" if results else "no_results",
            results=results,
        )

    def _preflight_services(self) -> EmbeddingInfo:
        self._tei.health()
        info = self._tei.info()
        if info.model_id != self._config.tei_model:
            raise RetrievalServiceError(
                f"TEI model {info.model_id} does not match {self._config.tei_model}."
            )
        if info.dimension != self._config.embedding_dimension:
            raise RetrievalServiceError("TEI model dimension does not match configuration.")
        self._vector_store.health()
        return info


def _indexed_point(chunk: CorpusChunk, vector: list[float]) -> IndexedPoint:
    return IndexedPoint(
        point_id=point_id_for_chunk(chunk.chunk_id),
        vector=tuple(vector),
        payload={
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "nct_id": chunk.nct_id,
            "section": chunk.section,
            "text": chunk.text,
            "source_url": chunk.source_url,
            "content_hash": chunk.content_hash,
        },
    )


def _retrieval_result(rank: int, hit: VectorSearchHit) -> RetrievalResult:
    required = (
        "chunk_id",
        "document_id",
        "nct_id",
        "section",
        "text",
        "source_url",
        "content_hash",
    )
    missing = [key for key in required if not isinstance(hit.payload.get(key), str)]
    if missing:
        raise RetrievalServiceError("Qdrant payload is missing: " + ", ".join(missing))
    return RetrievalResult(
        rank=rank,
        score=hit.score,
        chunk_id=hit.payload["chunk_id"],
        document_id=hit.payload["document_id"],
        nct_id=hit.payload["nct_id"],
        section=hit.payload["section"],
        text=hit.payload["text"],
        source_url=hit.payload["source_url"],
        content_hash=hit.payload["content_hash"],
    )


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        os.close(file_descriptor)
        temporary_path = Path(temporary_name)
        try:
            temporary_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
    except OSError as exc:
        raise RetrievalOutputError(f"Cannot write retrieval artifact {path}: {exc}") from exc
