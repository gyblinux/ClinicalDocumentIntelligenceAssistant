from __future__ import annotations

from types import SimpleNamespace

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance

from clinical_doc_assist.retrieval.models import (
    IndexedPoint,
    RetrievalServiceError,
)
from clinical_doc_assist.retrieval.qdrant import (
    QdrantVectorStore,
    point_id_for_chunk,
)


class FakeQdrant:
    def __init__(
        self,
        *,
        exists: bool = False,
        size: int = 3,
        distance: Distance = Distance.COSINE,
    ) -> None:
        self.exists = exists
        self.size = size
        self.distance = distance
        self.created = False
        self.deleted = False
        self.upserted: list[object] = []
        self.closed = False

    def collection_exists(self, _: str) -> bool:
        return self.exists

    def create_collection(self, **_: object) -> None:
        self.created = True
        self.exists = True

    def delete_collection(self, _: str) -> None:
        self.deleted = True
        self.exists = False

    def get_collection(self, _: str) -> SimpleNamespace:
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(
                    vectors=SimpleNamespace(size=self.size, distance=self.distance)
                )
            )
        )

    def get_collections(self) -> object:
        return object()

    def upsert(self, **kwargs: object) -> None:
        self.upserted.append(kwargs)

    def query_points(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    score=0.91,
                    payload={
                        "chunk_id": "chunk-001",
                        "document_id": "doc-NCT05214573",
                        "nct_id": "NCT05214573",
                        "section": "summary",
                        "text": "Evidence",
                        "source_url": "https://clinicaltrials.gov/study/NCT05214573",
                        "content_hash": "hash",
                    },
                )
            ]
        )

    def close(self) -> None:
        self.closed = True


def test_creates_collection_and_uses_stable_point_ids() -> None:
    client = FakeQdrant()
    store = QdrantVectorStore(
        client=client,  # type: ignore[arg-type]
        collection="clinical_evidence_v1",
    )
    point = IndexedPoint(
        point_id=point_id_for_chunk("chunk-001"),
        vector=(0.1, 0.2, 0.3),
        payload={"chunk_id": "chunk-001"},
    )

    store.ensure_collection(3, replace=False)
    count = store.upsert([point])

    assert client.created is True
    assert count == 1
    assert client.upserted[0]["points"][0].id == point_id_for_chunk("chunk-001")
    assert point_id_for_chunk("chunk-001") == point_id_for_chunk("chunk-001")


def test_replace_and_dimension_guards() -> None:
    client = FakeQdrant(exists=True, size=4)
    store = QdrantVectorStore(
        client=client,  # type: ignore[arg-type]
        collection="clinical_evidence_v1",
    )

    with pytest.raises(RetrievalServiceError, match="dimension"):
        store.ensure_collection(3, replace=False)

    store.ensure_collection(3, replace=True)
    assert client.deleted is True
    assert client.created is True


def test_reuses_compatible_collection() -> None:
    client = FakeQdrant(exists=True, size=3)
    store = QdrantVectorStore(
        client=client,  # type: ignore[arg-type]
        collection="clinical_evidence_v1",
    )

    store.ensure_collection(3, replace=False)

    assert client.created is False
    assert client.deleted is False


def test_maps_qdrant_search_results() -> None:
    client = FakeQdrant(exists=True)
    store = QdrantVectorStore(
        client=client,  # type: ignore[arg-type]
        collection="clinical_evidence_v1",
    )

    hits = store.search((0.1, 0.2, 0.3), limit=1)

    assert hits[0].score == 0.91
    assert hits[0].payload["chunk_id"] == "chunk-001"


def test_deletes_existing_collection() -> None:
    client = FakeQdrant(exists=True)
    store = QdrantVectorStore(
        client=client,  # type: ignore[arg-type]
        collection="clinical_evidence_v1",
    )

    store.delete_collection()

    assert client.deleted is True


def test_real_qdrant_client_in_memory_roundtrip() -> None:
    client = QdrantClient(location=":memory:")
    store = QdrantVectorStore(
        client=client,
        collection="roundtrip",
    )
    try:
        store.ensure_collection(3, replace=False)
        store.upsert(
            [
                IndexedPoint(
                    point_id=point_id_for_chunk("chunk-001"),
                    vector=(0.1, 0.2, 0.3),
                    payload={"chunk_id": "chunk-001", "text": "Evidence"},
                )
            ]
        )

        hits = store.search([0.1, 0.2, 0.3], limit=1)
    finally:
        client.close()

    assert len(hits) == 1
    assert hits[0].payload["chunk_id"] == "chunk-001"
