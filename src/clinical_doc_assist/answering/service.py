"""Load retrieval evidence, orchestrate answering, and persist answer records."""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

from clinical_doc_assist.answering.citations import parse_model_response, resolve_citations
from clinical_doc_assist.answering.models import (
    ANSWER_SCHEMA_VERSION,
    DISCLAIMER,
    MAX_EVIDENCE_ITEMS,
    AgentResult,
    AnswerCitation,
    AnswerClaim,
    AnswerConfig,
    AnsweringError,
    AnsweringInputError,
    AnsweringOutputError,
    AnswerOutcome,
    AnswerRun,
    EvidenceItem,
    ModelUsage,
    RetrievalInput,
)


class AnswerAgentProtocol(Protocol):
    def run(self, question: str, evidence: tuple[EvidenceItem, ...]) -> AgentResult: ...


class AgentFactory(Protocol):
    def __call__(self, allowed_nct_ids: frozenset[str]) -> AnswerAgentProtocol: ...


class AnsweringCommands(Protocol):
    def answer(
        self,
        retrieval_run: Path,
        *,
        output: Path | None = None,
    ) -> AnswerOutcome: ...


class AnswerService:
    """Coordinate one saved retrieval run into one persisted answer record."""

    def __init__(
        self,
        *,
        config: AnswerConfig,
        agent_factory: AgentFactory,
        output_dir: Path = Path("artifacts/answers"),
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._config = config
        self._agent_factory = agent_factory
        self._output_dir = output_dir
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.perf_counter
        self._id_factory = id_factory or (lambda: uuid4().hex[:16])

    def answer(
        self,
        retrieval_run: Path,
        *,
        output: Path | None = None,
    ) -> AnswerOutcome:
        started_at = self._monotonic()
        source = load_retrieval_input(retrieval_run)
        answer_id = f"answer-{self._id_factory()}"
        output_path = output or self._output_dir / f"{answer_id}.json"
        if output_path.exists():
            if output is not None:
                raise AnsweringInputError(f"output path already exists: {output}")
            raise AnsweringOutputError(f"answer record already exists: {output_path}")

        if source.status == "no_results":
            run = self._run_record(
                source,
                answer_id=answer_id,
                status="insufficient_evidence",
                reason="The retrieval run contained no evidence.",
                started_at=started_at,
            )
            return self._persist(run, output_path)

        agent = self._agent_factory(source.nct_ids)
        result = agent.run(source.question, source.evidence)
        if result.error is not None:
            run = self._failed_record(
                source,
                answer_id=answer_id,
                result=result,
                error=result.error,
                started_at=started_at,
            )
            return self._persist(run, output_path)

        try:
            response = parse_model_response(result.content)
        except AnsweringError as exc:
            run = self._failed_record(
                source,
                answer_id=answer_id,
                result=result,
                error=str(exc),
                started_at=started_at,
            )
            return self._persist(run, output_path)

        if response.status == "insufficient_evidence":
            run = self._run_record(
                source,
                answer_id=answer_id,
                status="insufficient_evidence",
                reason=response.reason,
                result=result,
                started_at=started_at,
            )
            return self._persist(run, output_path)

        try:
            resolved = resolve_citations(
                response,
                source.evidence,
                result.tool_calls,
            )
        except AnsweringError as exc:
            run = self._failed_record(
                source,
                answer_id=answer_id,
                result=result,
                error=str(exc),
                started_at=started_at,
            )
            return self._persist(run, output_path)

        run = self._run_record(
            source,
            answer_id=answer_id,
            status="answered",
            claims=resolved.claims,
            citations=resolved.citations,
            result=result,
            started_at=started_at,
        )
        return self._persist(run, output_path)

    def _failed_record(
        self,
        source: RetrievalInput,
        *,
        answer_id: str,
        result: AgentResult,
        error: str,
        started_at: float,
    ) -> AnswerRun:
        return AnswerRun(
            answer_id=answer_id,
            created_at=self._now(),
            status="failed",
            question=source.question,
            retrieval_id=source.retrieval_id,
            retrieval_created_at=source.created_at,
            evidence=source.evidence,
            model=self._config,
            model_output=result.content,
            tool_calls=result.tool_calls,
            usage=result.usage,
            latency_ms=_latency_ms(started_at, self._monotonic()),
            errors=(error,),
            disclaimer=DISCLAIMER,
        )

    def _run_record(
        self,
        source: RetrievalInput,
        *,
        answer_id: str,
        status: Literal["answered", "insufficient_evidence"],
        reason: str | None = None,
        claims: tuple[AnswerClaim, ...] = (),
        citations: tuple[AnswerCitation, ...] = (),
        result: AgentResult | None = None,
        started_at: float,
    ) -> AnswerRun:
        return AnswerRun(
            answer_id=answer_id,
            created_at=self._now(),
            status=status,
            question=source.question,
            retrieval_id=source.retrieval_id,
            retrieval_created_at=source.created_at,
            evidence=source.evidence,
            model=self._config,
            claims=claims,
            reason=reason,
            model_output=result.content if result is not None else None,
            citations=citations,
            tool_calls=result.tool_calls if result is not None else (),
            usage=result.usage if result is not None else ModelUsage(),
            latency_ms=_latency_ms(started_at, self._monotonic()),
            disclaimer=DISCLAIMER,
        )

    def _persist(self, run: AnswerRun, path: Path) -> AnswerOutcome:
        write_json_atomic(path, run.to_dict())
        return AnswerOutcome(run=run, path=path)


def load_retrieval_input(path: Path) -> RetrievalInput:
    """Load and validate one feature 004 retrieval artifact."""

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AnsweringInputError(f"Cannot read retrieval artifact {path}: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AnsweringInputError(f"Retrieval artifact is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise AnsweringInputError("Retrieval artifact must be one JSON object.")

    schema_version = payload.get("schema_version")
    if schema_version != ANSWER_SCHEMA_VERSION:
        raise AnsweringInputError(
            f"retrieval schema_version must be {ANSWER_SCHEMA_VERSION}."
        )
    status = payload.get("status")
    if status == "failed":
        raise AnsweringInputError("retrieval artifact status is failed.")
    if status not in {"completed", "no_results"}:
        raise AnsweringInputError(f"unsupported retrieval status: {status!r}.")

    retrieval_id = _required_text(payload, "retrieval_id")
    created_at = _datetime_field(payload, "created_at")
    query = payload.get("query")
    if not isinstance(query, dict):
        raise AnsweringInputError("retrieval artifact query must be an object.")
    question = _required_text(query, "text")
    collection = _required_text(query, "collection")
    limit = query.get("limit")
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise AnsweringInputError("retrieval query limit must be an integer.")

    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise AnsweringInputError("retrieval results must be a list.")
    if len(raw_results) > MAX_EVIDENCE_ITEMS:
        raise AnsweringInputError(
            f"retrieval artifact cannot exceed {MAX_EVIDENCE_ITEMS} evidence items."
        )
    evidence = tuple(
        sorted(
            (_evidence_item(item) for item in raw_results),
            key=lambda item: item.rank,
        )
    )
    errors = _string_list(payload.get("errors", []), "retrieval errors")

    try:
        return RetrievalInput(
            retrieval_id=retrieval_id,
            created_at=created_at,
            question=question,
            collection=collection,
            query_limit=limit,
            evidence=evidence,
            status=status,
            errors=errors,
        )
    except ValueError as exc:
        raise AnsweringInputError(str(exc)) from exc


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write one answer artifact using an atomic local replacement."""

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
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
    except OSError as exc:
        raise AnsweringOutputError(f"Cannot write answer record {path}: {exc}") from exc


def _evidence_item(value: object) -> EvidenceItem:
    if not isinstance(value, dict):
        raise AnsweringInputError("each retrieval result must be an object.")
    try:
        return EvidenceItem(
            rank=_integer_field(value, "rank"),
            score=_number_field(value, "score"),
            chunk_id=_required_text(value, "chunk_id"),
            document_id=_required_text(value, "document_id"),
            nct_id=_required_text(value, "nct_id"),
            section=_required_text(value, "section"),
            text=_required_text(value, "text"),
            source_url=_required_text(value, "source_url"),
            content_hash=_required_text(value, "content_hash"),
        )
    except ValueError as exc:
        raise AnsweringInputError(str(exc)) from exc


def _required_text(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise AnsweringInputError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _integer_field(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnsweringInputError(f"{field_name} must be an integer.")
    return value


def _number_field(payload: dict[str, Any], field_name: str) -> float:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnsweringInputError(f"{field_name} must be numeric.")
    return float(value)


def _datetime_field(payload: dict[str, Any], field_name: str) -> datetime:
    value = _required_text(payload, field_name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnsweringInputError(f"{field_name} must be an ISO 8601 timestamp.") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _string_list(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AnsweringInputError(f"{field_name} must be a string list.")
    return tuple(value)


def _latency_ms(started_at: float, finished_at: float) -> int:
    return max(0, int(round((finished_at - started_at) * 1000)))
