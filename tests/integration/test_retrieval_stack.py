from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from clinical_doc_assist.retrieval.models import RetrievalConfig
from clinical_doc_assist.retrieval.qdrant import QdrantVectorStore
from clinical_doc_assist.retrieval.service import RetrievalService
from clinical_doc_assist.retrieval.tei import TEIClient

FIXTURE = Path(__file__).parents[1] / "fixtures" / "retrieval" / "corpus"


@pytest.mark.skipif(
    os.getenv("RUN_DOCKER_INTEGRATION") != "1",
    reason="Set RUN_DOCKER_INTEGRATION=1 with TEI and Qdrant running.",
)
def test_live_tei_and_qdrant_retrieval() -> None:
    config = RetrievalConfig.from_env()
    tei = TEIClient(
        base_url=config.tei_url,
        model=config.tei_model,
        embedding_dimension=config.embedding_dimension,
    )
    store = QdrantVectorStore(
        collection=f"test_{uuid4().hex[:8]}",
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
    )
    service = RetrievalService(
        config=config,
        tei=tei,
        vector_store=store,
        manifest_dir=Path("artifacts/index-runs"),
    )

    try:
        indexed = service.index_corpus(
            FIXTURE,
            collection=store.collection,
            replace=True,
        )
        retrieved = service.search_evidence(
            "cardiovascular events",
            collection=store.collection,
            limit=2,
        )
    finally:
        try:
            store.delete_collection()
        finally:
            store.close()
            tei.close()

    assert indexed.manifest.status == "completed"
    assert indexed.manifest.point_count == 2
    assert retrieved.status == "completed"
    assert retrieved.results
