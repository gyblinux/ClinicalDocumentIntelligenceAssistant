from __future__ import annotations

from datetime import UTC, datetime

import pytest

from clinical_doc_assist.orchestration.models import (
    ArtifactReference,
    ConfigurationSnapshot,
    PipelineRun,
    QuestionRequest,
    StageTiming,
)


def request() -> QuestionRequest:
    return QuestionRequest(
        question="  What is the trial goal?  ",
        collection=" clinical_evidence_v1 ",
        limit=5,
    )


def configuration() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        collection="clinical_evidence_v1",
        limit=5,
        embedding_model="BAAI/bge-small-en-v1.5",
        embedding_dimension=384,
        answer_model="deepseek-flash",
        prompt_version="answering-v1",
    )


def test_question_request_normalizes_values() -> None:
    normalized = request()

    assert normalized.question == "What is the trial goal?"
    assert normalized.collection == "clinical_evidence_v1"
    assert normalized.to_dict()["limit"] == 5


@pytest.mark.parametrize(
    ("question", "collection", "limit"),
    [
        (" ", "clinical_evidence_v1", 5),
        ("Question", " ", 5),
        ("Question", "clinical_evidence_v1", 0),
        ("Question", "clinical_evidence_v1", 51),
    ],
)
def test_question_request_rejects_invalid_values(
    question: str,
    collection: str,
    limit: int,
) -> None:
    with pytest.raises(ValueError):
        QuestionRequest(question=question, collection=collection, limit=limit)


def test_stage_timing_requires_total_to_cover_stage_durations() -> None:
    assert StageTiming(retrieval_ms=100, answer_ms=200, total_ms=300)

    with pytest.raises(ValueError, match="cannot be less"):
        StageTiming(retrieval_ms=200, answer_ms=200, total_ms=300)


def test_configuration_snapshot_contains_no_secrets() -> None:
    payload = configuration().to_dict()

    assert set(payload) == {
        "collection",
        "limit",
        "embedding_model",
        "embedding_dimension",
        "answer_model",
        "prompt_version",
    }
    assert not any("key" in key.lower() or "secret" in key.lower() for key in payload)


def test_failed_pipeline_requires_error() -> None:
    with pytest.raises(ValueError, match="requires at least one error"):
        PipelineRun(
            pipeline_id="pipeline-1",
            created_at=datetime.now(UTC),
            status="failed",
            request=request(),
            configuration=configuration(),
            timing=StageTiming(retrieval_ms=None, answer_ms=None, total_ms=0),
        )


def test_insufficient_pipeline_requires_linked_stage_records() -> None:
    with pytest.raises(ValueError, match="requires retrieval and answer links"):
        PipelineRun(
            pipeline_id="pipeline-1",
            created_at=datetime.now(UTC),
            status="insufficient_evidence",
            request=request(),
            configuration=configuration(),
            retrieval=ArtifactReference(
                artifact_id="retrieval-1",
                path="artifacts/retrieval/retrieval-1.json",
                status="no_results",
            ),
            timing=StageTiming(retrieval_ms=10, answer_ms=20, total_ms=30),
        )
