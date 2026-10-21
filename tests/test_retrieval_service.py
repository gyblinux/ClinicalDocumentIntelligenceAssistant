from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from clinical_doc_assist.retrieval.models import (
    EmbeddingInfo,
    IndexedPoint,
    RetrievalConfig,
    RetrievalServiceError,
    VectorSearchHit,
)
from clinical_doc_assist.retrieval.service import RetrievalService

FIXTURE = Path(__file__).parent / "fixtures" / "retrieval" / "corpus"


class FakeTEI:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def health(self) -> None:
        return None

    def info(self) -> EmbeddingInfo:
        return EmbeddingInfo("test-model", 3, 512)

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]


class FailingTEI(FakeTEI):
    def health(self) -> None:
        raise RetrievalServiceError("TEI unavailable")


class WrongModelTEI(FakeTEI):
    def info(self) -> EmbeddingInfo:
        return EmbeddingInfo("other-model", 3, 512)


class FakeStore:
    def __init__(self) -> None:
        self.points: list[list[IndexedPoint]] = []
        self.replace: bool | None = None

    def health(self) -> None:
        return None

    def ensure_collection(self, dimension: int, *, replace: bool) -> None:
        assert dimension == 3
        self.replace = replace

    def upsert(self, points: list[IndexedPoint]) -> int:
        self.points.append(points)
        return len(points)

    def search(self, vector: list[float], *, limit: int) -> list[VectorSearchHit]:
        assert vector == [0.1, 0.2, 0.3]
        return [
            VectorSearchHit(
                score=0.9,
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
        ][:limit]


def _service(tei: FakeTEI, store: FakeStore, output: Path) -> RetrievalService:
    return RetrievalService(
        config=RetrievalConfig(
            tei_url="http://tei.test",
            tei_model="test-model",
            embedding_dimension=3,
            qdrant_url="http://qdrant.test",
        ),
        tei=tei,  # type: ignore[arg-type]
        vector_store=store,  # type: ignore[arg-type]
        now=lambda: datetime(2026, 10, 21, 10, 0, tzinfo=UTC),
        id_factory=lambda: "run-test",
        manifest_dir=output,
    )


def test_indexes_all_chunks_and_writes_manifest(tmp_path: Path) -> None:
    tei = FakeTEI()
    store = FakeStore()

    outcome = _service(tei, store, tmp_path / "manifests").index_corpus(
        FIXTURE,
        collection="clinical_evidence_v1",
        replace=True,
    )

    assert outcome.manifest.status == "completed"
    assert outcome.manifest.chunk_count == 2
    assert outcome.manifest.point_count == 2
    assert store.replace is True
    assert sum(len(batch) for batch in tei.batches) == 2
    assert outcome.manifest_path.exists()


def test_search_returns_ranked_evidence(tmp_path: Path) -> None:
    run = _service(FakeTEI(), FakeStore(), tmp_path).search_evidence(
        "question",
        collection="clinical_evidence_v1",
        limit=5,
    )

    assert run.status == "completed"
    assert run.results[0].rank == 1
    assert run.results[0].chunk_id == "chunk-001"


def test_index_reports_service_failure_in_manifest(tmp_path: Path) -> None:
    outcome = _service(FailingTEI(), FakeStore(), tmp_path).index_corpus(
        FIXTURE,
        collection="clinical_evidence_v1",
    )

    assert outcome.manifest.status == "failed"
    assert "TEI unavailable" in outcome.manifest.errors[0]
    assert outcome.manifest_path.exists()


def test_unchanged_reindex_uses_same_point_ids(tmp_path: Path) -> None:
    store = FakeStore()
    service = _service(FakeTEI(), store, tmp_path)

    service.index_corpus(FIXTURE, collection="clinical_evidence_v1")
    service.index_corpus(FIXTURE, collection="clinical_evidence_v1")

    first_ids = [point.point_id for point in store.points[0]]
    second_ids = [point.point_id for point in store.points[1]]
    assert first_ids == second_ids


def test_search_no_results(tmp_path: Path) -> None:
    class EmptyStore(FakeStore):
        def search(
            self,
            vector: list[float],
            *,
            limit: int,
        ) -> list[VectorSearchHit]:
            return []

    run = _service(FakeTEI(), EmptyStore(), tmp_path).search_evidence(
        "question",
        collection="clinical_evidence_v1",
    )

    assert run.status == "no_results"
    assert run.results == ()


def test_index_rejects_tei_model_mismatch(tmp_path: Path) -> None:
    outcome = _service(WrongModelTEI(), FakeStore(), tmp_path).index_corpus(
        FIXTURE,
        collection="clinical_evidence_v1",
    )

    assert outcome.manifest.status == "failed"
    assert "does not match" in outcome.manifest.errors[0]
