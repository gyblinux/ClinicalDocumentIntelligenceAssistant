from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from clinical_doc_assist.answering.models import (
    AnswerCitation,
    AnswerClaim,
    AnswerConfig,
    AnswerOutcome,
    AnswerRun,
    EvidenceItem,
    ModelUsage,
)
from clinical_doc_assist.evaluation.runner import EvaluationService
from clinical_doc_assist.orchestration.service import OrchestrationService
from clinical_doc_assist.retrieval.models import RetrievalConfig
from clinical_doc_assist.retrieval.qdrant import QdrantVectorStore
from clinical_doc_assist.retrieval.service import RetrievalService
from clinical_doc_assist.retrieval.tei import TEIClient

FIXTURE = Path(__file__).parents[1] / "fixtures" / "retrieval" / "corpus"
CASES = Path(__file__).parents[1] / "fixtures" / "evaluation" / "cases-valid.json"


class EchoAnswerService:
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def answer(
        self,
        retrieval_run: Path,
        *,
        output: Path | None = None,
    ) -> AnswerOutcome:
        del output
        payload = json.loads(retrieval_run.read_text(encoding="utf-8"))
        answer_id = f"answer-{uuid4().hex[:16]}"
        path = self._output_dir / f"{answer_id}.json"
        if not payload["results"]:
            run = AnswerRun(
                answer_id=answer_id,
                created_at=datetime.now(UTC),
                status="insufficient_evidence",
                question=payload["query"]["text"],
                retrieval_id=payload["retrieval_id"],
                retrieval_created_at=datetime.fromisoformat(
                    payload["created_at"].replace("Z", "+00:00")
                ),
                evidence=(),
                model=AnswerConfig(provider="test", model="echo"),
                reason="No results were retrieved.",
                usage=ModelUsage(),
                latency_ms=1,
            )
        else:
            first = payload["results"][0]
            item = EvidenceItem(
                rank=first["rank"],
                score=first["score"],
                chunk_id=first["chunk_id"],
                document_id=first["document_id"],
                nct_id=first["nct_id"],
                section=first["section"],
                text=first["text"],
                source_url=first["source_url"],
                content_hash=first["content_hash"],
            )
            run = AnswerRun(
                answer_id=answer_id,
                created_at=datetime.now(UTC),
                status="answered",
                question=payload["query"]["text"],
                retrieval_id=payload["retrieval_id"],
                retrieval_created_at=datetime.fromisoformat(
                    payload["created_at"].replace("Z", "+00:00")
                ),
                evidence=(item,),
                model=AnswerConfig(provider="test", model="echo"),
                claims=(
                    AnswerClaim(
                        claim_id="claim-1",
                        text="Retrieved evidence is available.",
                        citation_ids=(item.chunk_id,),
                    ),
                ),
                citations=(
                    AnswerCitation(
                        citation_id=item.chunk_id,
                        source_type="retrieval_evidence",
                        nct_id=item.nct_id,
                        section=item.section,
                        source_url=item.source_url,
                        content_hash=item.content_hash,
                    ),
                ),
                usage=ModelUsage(),
                latency_ms=1,
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(run.to_dict()), encoding="utf-8")
        return AnswerOutcome(run=run, path=path)


@pytest.mark.skipif(
    os.getenv("RUN_DOCKER_INTEGRATION") != "1",
    reason="Set RUN_DOCKER_INTEGRATION=1 with TEI and Qdrant running.",
)
def test_docker_evaluation_pipeline(tmp_path: Path) -> None:
    config = RetrievalConfig.from_env()
    tei = TEIClient(
        base_url=config.tei_url,
        model=config.tei_model,
        embedding_dimension=config.embedding_dimension,
    )
    store = QdrantVectorStore(
        collection=f"test_eval_{uuid4().hex[:8]}",
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
    )
    retrieval = RetrievalService(
        config=config,
        tei=tei,
        vector_store=store,
        manifest_dir=tmp_path / "index-runs",
    )
    answering = EchoAnswerService(tmp_path / "answers")
    orchestration = OrchestrationService(
        retrieval=retrieval,
        answering=answering,
        embedding_dimension=config.embedding_dimension,
        retrieval_dir=tmp_path / "retrieval",
        pipeline_dir=tmp_path / "pipelines",
    )
    evaluation = EvaluationService(
        orchestrator=orchestration,
        output_dir=tmp_path / "evaluations",
    )

    try:
        indexed = retrieval.index_corpus(
            FIXTURE,
            collection=store.collection,
            replace=True,
        )
        outcome = evaluation.run(
            CASES,
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
    assert len(outcome.run.cases) == 20
    assert outcome.path.is_file()
    assert outcome.verdicts_path.is_file()
