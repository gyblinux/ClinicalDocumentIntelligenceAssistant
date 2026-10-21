"""Compose retrieval and answering into a question-specific pipeline."""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from clinical_doc_assist.answering.models import (
    AnsweringError,
    AnswerOutcome,
    AnswerRun,
)
from clinical_doc_assist.orchestration.models import (
    AnswerSummary,
    ArtifactReference,
    ConfigurationSnapshot,
    OrchestrationInputError,
    OrchestrationOutputError,
    PipelineOutcome,
    PipelineRun,
    PipelineStatus,
    QuestionRequest,
    StageTiming,
)
from clinical_doc_assist.retrieval.models import RetrievalError, RetrievalRun


class RetrievalCommands(Protocol):
    def search_evidence(
        self,
        text: str,
        *,
        collection: str,
        limit: int = 5,
    ) -> RetrievalRun: ...


class AnswerCommands(Protocol):
    def answer(
        self,
        retrieval_run: Path,
        *,
        output: Path | None = None,
    ) -> AnswerOutcome: ...


class OrchestrationService:
    """Execute fresh retrieval followed by one evidence-grounded answer."""

    def __init__(
        self,
        *,
        retrieval: RetrievalCommands,
        answering: AnswerCommands,
        embedding_dimension: int = 384,
        retrieval_dir: Path = Path("artifacts/retrieval"),
        pipeline_dir: Path = Path("artifacts/pipelines"),
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if (
            isinstance(embedding_dimension, bool)
            or not isinstance(embedding_dimension, int)
            or embedding_dimension < 1
        ):
            raise ValueError("embedding_dimension must be positive.")
        self._retrieval = retrieval
        self._answering = answering
        self._embedding_dimension = embedding_dimension
        self._retrieval_dir = retrieval_dir
        self._pipeline_dir = pipeline_dir
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.perf_counter
        self._id_factory = id_factory or (lambda: uuid4().hex[:16])

    def ask(
        self,
        request: QuestionRequest,
        *,
        output: Path | None = None,
    ) -> PipelineOutcome:
        """Run one fresh retrieval/answer pipeline."""

        pipeline_id = f"pipeline-{self._id_factory()}"
        pipeline_path = output or self._pipeline_dir / f"{pipeline_id}.json"
        if pipeline_path.exists():
            if output is not None:
                raise OrchestrationInputError(
                    f"pipeline output path already exists: {output}"
                )
            raise OrchestrationOutputError(
                f"pipeline record already exists: {pipeline_path}"
            )

        total_started = self._monotonic()
        retrieval_started = self._monotonic()
        try:
            retrieval_run = self._retrieval.search_evidence(
                request.question,
                collection=request.collection,
                limit=request.limit,
            )
        except RetrievalError as exc:
            retrieval_ms = _elapsed_ms(retrieval_started, self._monotonic())
            return self._finish_failure(
                request=request,
                pipeline_id=pipeline_id,
                pipeline_path=pipeline_path,
                total_started=total_started,
                retrieval_ms=retrieval_ms,
                error=f"retrieval failed: {exc}",
            )

        retrieval_ms = _elapsed_ms(retrieval_started, self._monotonic())
        if retrieval_run.query.text != request.question:
            return self._finish_failure(
                request=request,
                pipeline_id=pipeline_id,
                pipeline_path=pipeline_path,
                total_started=total_started,
                retrieval_ms=retrieval_ms,
                error="retrieval run question does not match the request.",
                configuration=self._configuration(
                    request,
                    retrieval_run=retrieval_run,
                ),
            )
        retrieval_path = self._retrieval_dir / f"{retrieval_run.retrieval_id}.json"
        try:
            write_json_atomic(retrieval_path, retrieval_run.to_dict())
        except OrchestrationOutputError as exc:
            return self._finish_failure(
                request=request,
                pipeline_id=pipeline_id,
                pipeline_path=pipeline_path,
                total_started=total_started,
                retrieval_ms=retrieval_ms,
                error=str(exc),
                configuration=self._configuration(
                    request,
                    retrieval_run=retrieval_run,
                ),
            )

        retrieval_ref = ArtifactReference(
            artifact_id=retrieval_run.retrieval_id,
            path=_display_path(retrieval_path),
            status=retrieval_run.status,
        )
        if retrieval_run.status == "failed":
            return self._finish_failure(
                request=request,
                pipeline_id=pipeline_id,
                pipeline_path=pipeline_path,
                total_started=total_started,
                retrieval_ms=retrieval_ms,
                error="retrieval stage returned failed status.",
                retrieval=retrieval_ref,
                configuration=self._configuration(
                    request,
                    retrieval_run=retrieval_run,
                ),
            )

        answer_started = self._monotonic()
        try:
            answer_outcome = self._answering.answer(retrieval_path)
        except AnsweringError as exc:
            answer_ms = _elapsed_ms(answer_started, self._monotonic())
            return self._finish_failure(
                request=request,
                pipeline_id=pipeline_id,
                pipeline_path=pipeline_path,
                total_started=total_started,
                retrieval_ms=retrieval_ms,
                answer_ms=answer_ms,
                error=f"answering failed: {exc}",
                retrieval=retrieval_ref,
                configuration=self._configuration(
                    request,
                    retrieval_run=retrieval_run,
                ),
            )

        answer_ms = _elapsed_ms(answer_started, self._monotonic())
        if not answer_outcome.path.is_file():
            return self._finish_failure(
                request=request,
                pipeline_id=pipeline_id,
                pipeline_path=pipeline_path,
                total_started=total_started,
                retrieval_ms=retrieval_ms,
                answer_ms=answer_ms,
                error=f"answer artifact was not persisted: {answer_outcome.path}",
                retrieval=retrieval_ref,
                configuration=self._configuration(
                    request,
                    retrieval_run=retrieval_run,
                    answer_run=answer_outcome.run,
                ),
            )
        answer_ref = _answer_reference(answer_outcome)
        if (
            answer_outcome.run.question != retrieval_run.query.text
            or answer_outcome.run.retrieval_id != retrieval_run.retrieval_id
        ):
            return self._finish_failure(
                request=request,
                pipeline_id=pipeline_id,
                pipeline_path=pipeline_path,
                total_started=total_started,
                retrieval_ms=retrieval_ms,
                answer_ms=answer_ms,
                error="answer record does not match the retrieval run.",
                retrieval=retrieval_ref,
                answer=answer_ref,
                configuration=self._configuration(
                    request,
                    retrieval_run=retrieval_run,
                    answer_run=answer_outcome.run,
                ),
            )
        answer_summary = _answer_summary(answer_outcome.run)
        pipeline_status: PipelineStatus
        errors = list(retrieval_run.errors) + list(answer_outcome.run.errors)
        if answer_outcome.run.status == "failed":
            pipeline_status = "failed"
        elif answer_outcome.run.status == "insufficient_evidence":
            pipeline_status = "insufficient_evidence"
        else:
            pipeline_status = "answered"

        run = PipelineRun(
            pipeline_id=pipeline_id,
            created_at=self._now(),
            status=pipeline_status,
            request=request,
            configuration=self._configuration(
                request,
                retrieval_run=retrieval_run,
                answer_run=answer_outcome.run,
            ),
            retrieval=retrieval_ref,
            answer=answer_ref,
            answer_summary=answer_summary,
            timing=StageTiming(
                retrieval_ms=retrieval_ms,
                answer_ms=answer_ms,
                total_ms=_elapsed_ms(total_started, self._monotonic()),
            ),
            errors=tuple(errors),
        )
        return self._persist(run, pipeline_path)

    def _finish_failure(
        self,
        *,
        request: QuestionRequest,
        pipeline_id: str,
        pipeline_path: Path,
        total_started: float,
        error: str,
        retrieval_ms: int | None = None,
        answer_ms: int | None = None,
        retrieval: ArtifactReference | None = None,
        answer: ArtifactReference | None = None,
        configuration: ConfigurationSnapshot | None = None,
    ) -> PipelineOutcome:
        total_ms = _elapsed_ms(total_started, self._monotonic())
        stage_total = (retrieval_ms or 0) + (answer_ms or 0)
        if total_ms < stage_total:
            total_ms = stage_total
        run = PipelineRun(
            pipeline_id=pipeline_id,
            created_at=self._now(),
            status="failed",
            request=request,
            configuration=configuration or self._configuration(request),
            retrieval=retrieval,
            answer=answer,
            timing=StageTiming(
                retrieval_ms=retrieval_ms,
                answer_ms=answer_ms,
                total_ms=total_ms,
            ),
            errors=(error,),
        )
        return self._persist(run, pipeline_path)

    def _configuration(
        self,
        request: QuestionRequest,
        *,
        retrieval_run: RetrievalRun | None = None,
        answer_run: AnswerRun | None = None,
    ) -> ConfigurationSnapshot:
        return ConfigurationSnapshot(
            collection=request.collection,
            limit=request.limit,
            embedding_model=(
                retrieval_run.tei_model if retrieval_run is not None else None
            ),
            embedding_dimension=self._embedding_dimension,
            answer_model=answer_run.model.model if answer_run is not None else None,
            prompt_version=(
                answer_run.model.prompt_version if answer_run is not None else None
            ),
        )

    def _persist(self, run: PipelineRun, path: Path) -> PipelineOutcome:
        write_json_atomic(path, run.to_dict())
        return PipelineOutcome(run=run, path=path)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write one orchestration artifact without overwriting an existing file."""

    if path.exists():
        raise OrchestrationOutputError(f"artifact already exists: {path}")
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
            if path.exists():
                raise OrchestrationOutputError(f"artifact already exists: {path}")
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
    except OrchestrationOutputError:
        raise
    except OSError as exc:
        raise OrchestrationOutputError(f"Cannot write artifact {path}: {exc}") from exc


def _answer_reference(outcome: AnswerOutcome) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=outcome.run.answer_id,
        path=_display_path(outcome.path),
        status={
            "answered": "completed",
            "insufficient_evidence": "insufficient_evidence",
            "failed": "failed",
        }[outcome.run.status],
    )


def _answer_summary(run: AnswerRun) -> AnswerSummary:
    return AnswerSummary(
        answer_id=run.answer_id,
        status=run.status,
        claims=run.claims,
        reason=run.reason,
        citation_ids=tuple(
            dict.fromkeys(citation.citation_id for citation in run.citations)
        ),
    )


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _elapsed_ms(started_at: float, finished_at: float) -> int:
    return max(0, int(round((finished_at - started_at) * 1000)))
