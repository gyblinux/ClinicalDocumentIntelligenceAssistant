"""Qdrant vector index operations."""

from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from clinical_doc_assist.retrieval.models import (
    IndexedPoint,
    RetrievalServiceError,
    VectorSearchHit,
)


def point_id_for_chunk(chunk_id: str) -> str:
    """Return a stable Qdrant UUID for a feature 003 chunk ID."""

    return str(uuid5(NAMESPACE_URL, f"clinical-doc-assist:{chunk_id}"))


class QdrantVectorStore:
    """Minimal collection, upsert, and search wrapper."""

    def __init__(
        self,
        *,
        collection: str,
        url: str = "http://127.0.0.1:6333",
        api_key: str | None = None,
        client: QdrantClient | None = None,
    ) -> None:
        self._collection = collection
        self._owns_client = client is None
        self._client = client or QdrantClient(url=url, api_key=api_key)

    @property
    def collection(self) -> str:
        return self._collection

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def health(self) -> None:
        try:
            self._client.get_collections()
        except Exception as exc:
            raise RetrievalServiceError(f"Qdrant is unavailable: {exc}") from exc

    def ensure_collection(self, dimension: int, *, replace: bool) -> None:
        try:
            exists = self._client.collection_exists(self._collection)
            if replace and exists:
                self._client.delete_collection(self._collection)
                exists = False

            if not exists:
                self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(
                        size=dimension,
                        distance=Distance.COSINE,
                    ),
                )
                return

            vectors = self._client.get_collection(self._collection).config.params.vectors
            if isinstance(vectors, dict):
                vectors = next(iter(vectors.values()), None)
            if vectors is None or vectors.size != dimension:
                raise RetrievalServiceError(
                    "Qdrant collection dimension does not match configuration."
                )
            if str(vectors.distance).lower() != str(Distance.COSINE).lower():
                raise RetrievalServiceError("Qdrant collection distance must be Cosine.")
        except RetrievalServiceError:
            raise
        except Exception as exc:
            raise RetrievalServiceError(f"Qdrant collection validation failed: {exc}") from exc

    def upsert(self, points: list[IndexedPoint]) -> int:
        if not points:
            return 0
        try:
            self._client.upsert(
                collection_name=self._collection,
                points=[
                    PointStruct(
                        id=point.point_id,
                        vector=list(point.vector),
                        payload=point.payload,
                    )
                    for point in points
                ],
                wait=True,
            )
        except Exception as exc:
            raise RetrievalServiceError(f"Qdrant upsert failed: {exc}") from exc
        return len(points)

    def delete_collection(self) -> None:
        try:
            if self._client.collection_exists(self._collection):
                self._client.delete_collection(self._collection)
        except Exception as exc:
            raise RetrievalServiceError(f"Qdrant collection deletion failed: {exc}") from exc

    def search(
        self,
        vector: list[float],
        *,
        limit: int,
    ) -> list[VectorSearchHit]:
        try:
            response = self._client.query_points(
                collection_name=self._collection,
                query=vector,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            raise RetrievalServiceError(f"Qdrant search failed: {exc}") from exc

        hits: list[VectorSearchHit] = []
        for point in response.points:
            payload: Any = point.payload
            if not isinstance(payload, dict):
                raise RetrievalServiceError("Qdrant search returned a point without payload.")
            hits.append(
                VectorSearchHit(
                    score=float(point.score),
                    payload=payload,
                )
            )
        return hits
