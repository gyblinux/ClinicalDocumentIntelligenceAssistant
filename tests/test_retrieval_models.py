from __future__ import annotations

from datetime import datetime

import pytest

from clinical_doc_assist.retrieval.models import (
    IndexManifest,
    RetrievalConfig,
    RetrievalQuery,
    RetrievalResult,
    RetrievalRun,
)


def test_retrieval_config_defaults_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEI_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("TEI_MODEL", "test-model")
    monkeypatch.setenv("TEI_EMBEDDING_DIMENSION", "3")
    monkeypatch.setenv("TEI_BATCH_SIZE", "8")
    monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:7000")

    config = RetrievalConfig.from_env(load_env_file=False)

    assert config.to_dict()["embedding_dimension"] == 3
    assert config.tei_batch_size == 8
    assert config.qdrant_url == "http://127.0.0.1:7000"

    with pytest.raises(ValueError, match="embedding_dimension"):
        RetrievalConfig(embedding_dimension=0)
    with pytest.raises(ValueError, match="tei_batch_size"):
        RetrievalConfig(tei_batch_size=0)


def test_retrieval_query_enforces_limit() -> None:
    assert RetrievalQuery.from_values("question", "collection", 5).limit == 5

    with pytest.raises(ValueError, match="query"):
        RetrievalQuery.from_values(" ", "collection", 5)
    with pytest.raises(ValueError, match="limit"):
        RetrievalQuery.from_values("question", "collection", 51)


def test_retrieval_run_serializes_ranked_results() -> None:
    query = RetrievalQuery.from_values("question", "clinical_evidence_v1", 2)
    result = RetrievalResult(
        rank=1,
        score=0.92,
        chunk_id="chunk-001",
        document_id="doc-NCT05214573",
        nct_id="NCT05214573",
        section="summary",
        text="Evidence",
        source_url="https://clinicaltrials.gov/study/NCT05214573",
        content_hash="hash",
    )
    run = RetrievalRun(
        retrieval_id="retrieval-test",
        created_at=datetime(2026, 10, 21, 10, 0),
        query=query,
        tei_model="test-model",
        collection="clinical_evidence_v1",
        status="completed",
        results=(result,),
        errors=(),
    )

    payload = run.to_dict()

    assert payload["schema_version"] == "1.0"
    assert payload["results"][0]["rank"] == 1
    assert payload["results"][0]["source_url"].endswith("NCT05214573")


def test_index_manifest_serializes_corpus_and_service_versions() -> None:
    manifest = IndexManifest(
        index_id="index-test",
        created_at=datetime(2026, 10, 21, 10, 0),
        corpus_build_id="corpus-fixture",
        corpus_status="completed",
        chunk_count=2,
        point_count=2,
        status="completed",
        tei_model="test-model",
        embedding_dimension=3,
        qdrant_url="http://127.0.0.1:6333",
        collection="clinical_evidence_v1",
        replace_requested=False,
        errors=(),
    )

    payload = manifest.to_dict()

    assert payload["schema_version"] == "1.0"
    assert payload["distance"] == "Cosine"
    assert payload["point_count"] == 2
