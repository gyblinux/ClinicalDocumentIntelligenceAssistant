"""Typed records for question-to-answer orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypeAlias

from clinical_doc_assist.answering.models import AnswerClaim, AnswerStatus

PIPELINE_SCHEMA_VERSION = "1.0"
DEFAULT_RETRIEVAL_LIMIT = 5
MAX_RETRIEVAL_LIMIT = 50

StageStatus: TypeAlias = Literal[
    "not_started",
    "completed",
    "no_results",
    "insufficient_evidence",
    "failed",
]
PipelineStatus: TypeAlias = Literal["answered", "insufficient_evidence", "failed"]


class OrchestrationError(RuntimeError):
    """Base error for question-to-answer orchestration."""


class OrchestrationInputError(OrchestrationError):
    """Raised when a question request or output path is invalid."""


class OrchestrationOutputError(OrchestrationError):
    """Raised when a pipeline artifact cannot be persisted."""


@dataclass(frozen=True, slots=True)
class QuestionRequest:
    question: str
    collection: str
    limit: int = DEFAULT_RETRIEVAL_LIMIT

    def __post_init__(self) -> None:
        for field_name in ("question", "collection"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} cannot be empty.")
            object.__setattr__(self, field_name, value.strip())
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= MAX_RETRIEVAL_LIMIT
        ):
            raise ValueError(
                f"limit must be between 1 and {MAX_RETRIEVAL_LIMIT}."
            )

    def to_dict(self) -> dict[str, str | int]:
        return {
            "question": self.question,
            "collection": self.collection,
            "limit": self.limit,
        }


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    artifact_id: str
    path: str
    status: StageStatus

    def __post_init__(self) -> None:
        if self.status not in {
            "not_started",
            "completed",
            "no_results",
            "insufficient_evidence",
            "failed",
        }:
            raise ValueError(f"unknown artifact status: {self.status}")
        for field_name in ("artifact_id", "path"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} cannot be empty.")
            object.__setattr__(self, field_name, value.strip())

    def to_dict(self) -> dict[str, str]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class StageTiming:
    retrieval_ms: int | None
    answer_ms: int | None
    total_ms: int

    def __post_init__(self) -> None:
        for field_name in ("retrieval_ms", "answer_ms", "total_ms"):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer.")
        stage_total = sum(
            value
            for value in (self.retrieval_ms, self.answer_ms)
            if value is not None
        )
        if self.total_ms < stage_total:
            raise ValueError("total_ms cannot be less than combined stage durations.")

    def to_dict(self) -> dict[str, int | None]:
        return {
            "retrieval_ms": self.retrieval_ms,
            "answer_ms": self.answer_ms,
            "total_ms": self.total_ms,
        }


@dataclass(frozen=True, slots=True)
class ConfigurationSnapshot:
    collection: str
    limit: int
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    answer_model: str | None = None
    prompt_version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.collection, str) or not self.collection.strip():
            raise ValueError("configuration collection cannot be empty.")
        object.__setattr__(self, "collection", self.collection.strip())
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= MAX_RETRIEVAL_LIMIT
        ):
            raise ValueError("configuration limit must be between 1 and 50.")
        if self.embedding_dimension is not None and (
            isinstance(self.embedding_dimension, bool)
            or not isinstance(self.embedding_dimension, int)
            or self.embedding_dimension < 1
        ):
            raise ValueError("embedding_dimension must be positive.")

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "collection": self.collection,
            "limit": self.limit,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "answer_model": self.answer_model,
            "prompt_version": self.prompt_version,
        }


@dataclass(frozen=True, slots=True)
class AnswerSummary:
    answer_id: str
    status: AnswerStatus
    claims: tuple[AnswerClaim, ...] = ()
    reason: str | None = None
    citation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.answer_id.strip():
            raise ValueError("answer_id cannot be empty.")
        if self.status not in {"answered", "insufficient_evidence", "failed"}:
            raise ValueError(f"unknown answer status: {self.status}")
        if self.status == "answered" and not self.claims:
            raise ValueError("answered summary requires claims.")
        if self.status == "insufficient_evidence":
            if self.claims:
                raise ValueError("insufficient_evidence summary cannot contain claims.")
            if not self.reason:
                raise ValueError("insufficient_evidence summary requires a reason.")
        if not all(isinstance(value, str) and value.strip() for value in self.citation_ids):
            raise ValueError("citation_ids must contain non-empty strings.")
        normalized_ids = tuple(
            dict.fromkeys(value.strip() for value in self.citation_ids)
        )
        object.__setattr__(self, "citation_ids", normalized_ids)

    def to_dict(self) -> dict[str, object]:
        return {
            "answer_id": self.answer_id,
            "status": self.status,
            "claims": [claim.to_dict() for claim in self.claims],
            "reason": self.reason,
            "citation_ids": list(self.citation_ids),
        }


@dataclass(frozen=True, slots=True)
class PipelineRun:
    pipeline_id: str
    created_at: datetime
    status: PipelineStatus
    request: QuestionRequest
    configuration: ConfigurationSnapshot
    timing: StageTiming
    retrieval: ArtifactReference | None = None
    answer: ArtifactReference | None = None
    answer_summary: AnswerSummary | None = None
    errors: tuple[str, ...] = ()
    schema_version: str = PIPELINE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PIPELINE_SCHEMA_VERSION:
            raise ValueError(
                f"pipeline schema_version must be {PIPELINE_SCHEMA_VERSION}."
            )
        if not self.pipeline_id.strip():
            raise ValueError("pipeline_id cannot be empty.")
        if self.status not in {"answered", "insufficient_evidence", "failed"}:
            raise ValueError(f"unknown pipeline status: {self.status}")
        if self.status == "failed" and not self.errors:
            raise ValueError("failed pipeline requires at least one error.")
        if self.status == "answered":
            if self.retrieval is None or self.answer is None:
                raise ValueError("answered pipeline requires retrieval and answer links.")
            if self.answer_summary is None or self.answer_summary.status != "answered":
                raise ValueError("answered pipeline requires an answered summary.")
        if self.status == "insufficient_evidence":
            if self.retrieval is None or self.answer is None:
                raise ValueError(
                    "insufficient_evidence pipeline requires retrieval and answer links."
                )
            if (
                self.answer_summary is None
                or self.answer_summary.status != "insufficient_evidence"
            ):
                raise ValueError(
                    "insufficient_evidence pipeline requires an abstention summary."
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "pipeline_id": self.pipeline_id,
            "created_at": _datetime_value(self.created_at),
            "status": self.status,
            "request": self.request.to_dict(),
            "configuration": self.configuration.to_dict(),
            "retrieval": self.retrieval.to_dict() if self.retrieval else None,
            "answer": self.answer.to_dict() if self.answer else None,
            "answer_summary": (
                self.answer_summary.to_dict() if self.answer_summary else None
            ),
            "timing": self.timing.to_dict(),
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class PipelineOutcome:
    run: PipelineRun
    path: Path

    @property
    def exit_code(self) -> int:
        return 0 if self.run.status in {"answered", "insufficient_evidence"} else 1


def _datetime_value(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
