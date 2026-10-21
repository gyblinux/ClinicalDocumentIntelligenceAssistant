from __future__ import annotations

import json
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

import pytest

from clinical_doc_assist.answering.models import AnsweringOutputError
from clinical_doc_assist.orchestration.models import (
    OrchestrationInputError,
    QuestionRequest,
)
from clinical_doc_assist.orchestration.service import OrchestrationService
from clinical_doc_assist.retrieval.models import RetrievalServiceError
from tests.fixtures.orchestration.fakes import (
    ANSWER_ID,
    QUESTION,
    RETRIEVAL_ID,
    FakeAnsweringService,
    FakeRetrievalService,
    answer_outcome,
    retrieval_run,
)


def fixed_now() -> datetime:
    return datetime(2026, 10, 21, 12, 0, 10, tzinfo=UTC)


def make_service(
    tmp_path: Path,
    retrieval: FakeRetrievalService,
    answering: FakeAnsweringService,
    *,
    ids: list[str] | None = None,
) -> OrchestrationService:
    pipeline_ids = iter(ids or ["fixture-1"])
    return OrchestrationService(
        retrieval=retrieval,
        answering=answering,
        embedding_dimension=384,
        retrieval_dir=tmp_path / "retrieval",
        pipeline_dir=tmp_path / "pipelines",
        now=fixed_now,
        monotonic=count(0.0, 0.1).__next__,
        id_factory=pipeline_ids.__next__,
    )


def request(question: str = QUESTION) -> QuestionRequest:
    return QuestionRequest(
        question=question,
        collection="clinical_evidence_v1",
        limit=5,
    )


def test_service_composes_fresh_retrieval_and_answering(
    tmp_path: Path,
) -> None:
    retrieval = FakeRetrievalService(retrieval_run())
    answer_path = tmp_path / "answers" / f"{ANSWER_ID}.json"
    answering = FakeAnsweringService(answer_outcome(answer_path))
    service = make_service(tmp_path, retrieval, answering)

    outcome = service.ask(request())

    assert outcome.run.status == "answered"
    assert outcome.run.request.question == QUESTION
    assert outcome.run.retrieval is not None
    assert outcome.run.retrieval.artifact_id == RETRIEVAL_ID
    assert outcome.run.answer is not None
    assert outcome.run.answer.path.endswith(f"{ANSWER_ID}.json")
    assert outcome.run.answer_summary is not None
    assert outcome.run.answer_summary.claims[0].text
    assert outcome.run.timing.total_ms >= outcome.run.timing.retrieval_ms
    assert retrieval.calls == [
        (QUESTION, "clinical_evidence_v1", 5)
    ]
    assert answering.calls == [
        tmp_path / "retrieval" / f"{RETRIEVAL_ID}.json"
    ]
    assert outcome.path.is_file()
    assert json.loads(outcome.path.read_text(encoding="utf-8"))["status"] == "answered"


def test_service_records_configuration_and_linked_answer_summary(
    tmp_path: Path,
) -> None:
    retrieval = FakeRetrievalService(retrieval_run())
    answer_path = tmp_path / "answers" / f"{ANSWER_ID}.json"
    answering = FakeAnsweringService(answer_outcome(answer_path))
    service = make_service(tmp_path, retrieval, answering)

    payload = service.ask(request()).run.to_dict()

    assert payload["configuration"] == {
        "collection": "clinical_evidence_v1",
        "limit": 5,
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "embedding_dimension": 384,
        "answer_model": "deepseek-flash",
        "prompt_version": "answering-v1",
    }
    assert payload["retrieval"]["artifact_id"] == RETRIEVAL_ID
    assert payload["answer"]["artifact_id"] == ANSWER_ID
    assert payload["answer_summary"]["answer_id"] == ANSWER_ID
    assert payload["answer_summary"]["citation_ids"] == [
        "chunk-7f7563be8042d8cdfa51a2fa"
    ]


def test_repeated_question_still_creates_new_artifacts(tmp_path: Path) -> None:
    retrieval = FakeRetrievalService(
        retrieval_run(retrieval_id="retrieval-1"),
        retrieval_run(retrieval_id="retrieval-2"),
    )
    answering = FakeAnsweringService(
        answer_outcome(tmp_path / "answers" / "one.json"),
        answer_outcome(tmp_path / "answers" / "two.json"),
    )
    service = make_service(
        tmp_path,
        retrieval,
        answering,
        ids=["pipeline-1", "pipeline-2"],
    )

    first = service.ask(request())
    second = service.ask(request())

    assert first.run.retrieval.artifact_id == "retrieval-1"
    assert second.run.retrieval.artifact_id == "retrieval-2"
    assert first.run.answer.path != second.run.answer.path
    assert retrieval.calls == [
        (QUESTION, "clinical_evidence_v1", 5),
        (QUESTION, "clinical_evidence_v1", 5),
    ]
    assert len(list((tmp_path / "pipelines").glob("*.json"))) == 2


def test_no_results_produces_linked_abstention(tmp_path: Path) -> None:
    retrieval = FakeRetrievalService(
        retrieval_run(status="no_results", retrieval_id="retrieval-empty")
    )
    answering = FakeAnsweringService(
        answer_outcome(
            tmp_path / "answers" / "empty.json",
            retrieval_id="retrieval-empty",
            status="insufficient_evidence",
            include_evidence=False,
        )
    )
    service = make_service(tmp_path, retrieval, answering)

    outcome = service.ask(request())

    assert outcome.run.status == "insufficient_evidence"
    assert outcome.run.retrieval is not None
    assert outcome.run.retrieval.status == "no_results"
    assert outcome.run.answer_summary is not None
    assert outcome.run.answer_summary.reason == "The evidence is insufficient."
    assert outcome.exit_code == 0


def test_retrieval_failure_does_not_call_answering(tmp_path: Path) -> None:
    retrieval = FakeRetrievalService(RetrievalServiceError("TEI unavailable"))
    answering = FakeAnsweringService()
    service = make_service(tmp_path, retrieval, answering)

    outcome = service.ask(request())

    assert outcome.run.status == "failed"
    assert outcome.run.retrieval is None
    assert outcome.run.answer is None
    assert "retrieval failed" in outcome.run.errors[0]
    assert answering.calls == []
    assert outcome.path.is_file()


def test_question_mismatch_is_rejected_before_stage_persistence(
    tmp_path: Path,
) -> None:
    retrieval = FakeRetrievalService(retrieval_run(question="Different question"))
    answering = FakeAnsweringService()
    service = make_service(tmp_path, retrieval, answering)

    outcome = service.ask(request(QUESTION))

    assert outcome.run.status == "failed"
    assert "does not match" in outcome.run.errors[0]
    assert not (tmp_path / "retrieval" / f"{RETRIEVAL_ID}.json").exists()
    assert answering.calls == []


def test_answer_failure_record_is_linked_to_retrieval(tmp_path: Path) -> None:
    retrieval = FakeRetrievalService(retrieval_run())
    answering = FakeAnsweringService(
        answer_outcome(
            tmp_path / "answers" / "failed.json",
            status="failed",
        )
    )
    service = make_service(tmp_path, retrieval, answering)

    outcome = service.ask(request())

    assert outcome.run.status == "failed"
    assert outcome.run.retrieval is not None
    assert outcome.run.answer is not None
    assert "model response invalid" in outcome.run.errors
    assert outcome.exit_code == 1


def test_answer_exception_preserves_retrieval_reference(tmp_path: Path) -> None:
    retrieval = FakeRetrievalService(retrieval_run())
    answering = FakeAnsweringService(AnsweringOutputError("write failed"))
    service = make_service(tmp_path, retrieval, answering)

    outcome = service.ask(request())

    assert outcome.run.status == "failed"
    assert outcome.run.retrieval is not None
    assert outcome.run.answer is None
    assert "answering failed" in outcome.run.errors[0]


def test_answer_record_must_match_retrieval_question_and_id(
    tmp_path: Path,
) -> None:
    retrieval = FakeRetrievalService(retrieval_run())
    answering = FakeAnsweringService(
        answer_outcome(
            tmp_path / "answers" / "mismatch.json",
            question="Different question",
        )
    )
    service = make_service(tmp_path, retrieval, answering)

    outcome = service.ask(request())

    assert outcome.run.status == "failed"
    assert outcome.run.retrieval is not None
    assert outcome.run.answer is not None
    assert "does not match" in outcome.run.errors[0]


def test_existing_pipeline_output_fails_before_retrieval(tmp_path: Path) -> None:
    retrieval = FakeRetrievalService(retrieval_run())
    answering = FakeAnsweringService(
        answer_outcome(tmp_path / "answers" / "unused.json")
    )
    service = make_service(tmp_path, retrieval, answering)
    output = tmp_path / "existing.json"
    output.write_text("keep", encoding="utf-8")

    with pytest.raises(OrchestrationInputError, match="already exists"):
        service.ask(request(), output=output)

    assert retrieval.calls == []
    assert output.read_text(encoding="utf-8") == "keep"
