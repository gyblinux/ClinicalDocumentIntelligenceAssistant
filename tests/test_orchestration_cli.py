from __future__ import annotations

import json
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

from clinical_doc_assist.orchestration.cli import main
from clinical_doc_assist.orchestration.models import (
    OrchestrationOutputError,
    PipelineOutcome,
    QuestionRequest,
)
from clinical_doc_assist.orchestration.service import OrchestrationService
from clinical_doc_assist.retrieval.models import RetrievalServiceError
from tests.fixtures.orchestration.fakes import (
    QUESTION,
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
) -> OrchestrationService:
    return OrchestrationService(
        retrieval=retrieval,
        answering=answering,
        embedding_dimension=384,
        retrieval_dir=tmp_path / "retrieval",
        pipeline_dir=tmp_path / "pipelines",
        now=fixed_now,
        monotonic=count(0.0, 0.1).__next__,
        id_factory=lambda: "cli-fixture",
    )


def test_cli_prints_answered_pipeline_json(
    tmp_path: Path,
    capsys,
) -> None:
    retrieval = FakeRetrievalService(retrieval_run())
    answering = FakeAnsweringService(
        answer_outcome(tmp_path / "answers" / "answer.json")
    )
    service = make_service(tmp_path, retrieval, answering)

    exit_code = main(
        [
            QUESTION,
            "--collection",
            "clinical_evidence_v1",
            "--limit",
            "5",
        ],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["status"] == "answered"
    assert payload["request"]["question"] == QUESTION


def test_cli_returns_zero_for_insufficient_evidence(
    tmp_path: Path,
    capsys,
) -> None:
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

    exit_code = main(
        [QUESTION, "--collection", "clinical_evidence_v1"],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["status"] == "insufficient_evidence"


def test_cli_returns_one_for_failed_pipeline(
    tmp_path: Path,
    capsys,
) -> None:
    service = make_service(
        tmp_path,
        FakeRetrievalService(RetrievalServiceError("retrieval unavailable")),
        FakeAnsweringService(),
    )

    exit_code = main(
        [QUESTION, "--collection", "clinical_evidence_v1"],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out)["status"] == "failed"


def test_cli_rejects_empty_question_before_service_call(capsys) -> None:
    class RecordingService:
        def __init__(self) -> None:
            self.calls: list[QuestionRequest] = []

        def ask(
            self,
            request: QuestionRequest,
            *,
            output: Path | None = None,
        ) -> PipelineOutcome:
            del output
            self.calls.append(request)
            raise AssertionError("service should not be called")

    service = RecordingService()

    exit_code = main(
        ["   ", "--collection", "clinical_evidence_v1"],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "question cannot be empty" in captured.err
    assert service.calls == []


def test_cli_maps_output_failure_to_exit_one(capsys) -> None:
    class FailingService:
        def ask(
            self,
            request: QuestionRequest,
            *,
            output: Path | None = None,
        ) -> PipelineOutcome:
            del request, output
            raise OrchestrationOutputError("disk unavailable")

    exit_code = main(
        [QUESTION, "--collection", "clinical_evidence_v1"],
        service=FailingService(),
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "disk unavailable" in captured.err
