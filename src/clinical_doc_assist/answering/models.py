"""Typed records and errors for evidence-grounded answering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypeAlias

ANSWER_SCHEMA_VERSION = "1.0"
PROMPT_VERSION = "answering-v1"
MAX_MODEL_TURNS = 2
MAX_TOOL_CALLS = 3
MAX_EVIDENCE_ITEMS = 10
MAX_OUTPUT_TOKENS = 1600
MAX_CLAIMS = 10
DISCLAIMER = (
    "This is a summary of public research documents, not clinical advice or a "
    "substitute for professional medical judgment."
)
NCT_ID_PATTERN = re.compile(r"^NCT\d{8}$")
METADATA_CITATION_PATTERN = re.compile(r"^trial-metadata:(NCT\d{8})$")

RetrievalStatus: TypeAlias = Literal["completed", "no_results", "failed"]
AnswerStatus: TypeAlias = Literal["answered", "insufficient_evidence", "failed"]
ModelStatus: TypeAlias = Literal["answered", "insufficient_evidence"]
CitationSource: TypeAlias = Literal["retrieval_evidence", "trial_metadata"]


class AnsweringError(RuntimeError):
    """Base error for the answering stage."""


class AnsweringInputError(AnsweringError):
    """Raised when a retrieval artifact or CLI input is unusable."""


class AnsweringOutputError(AnsweringError):
    """Raised when an answer record cannot be persisted."""


class AnsweringModelError(AnsweringError):
    """Raised when the model client cannot complete a turn."""


class AnsweringToolError(AnsweringError):
    """Raised when an attempted metadata tool call cannot be recorded safely."""


class AnsweringResponseError(AnsweringError):
    """Raised when a model response does not match the answer contract."""


class CitationValidationError(AnsweringError):
    """Raised when model citations cannot be resolved safely."""


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    rank: int
    score: float
    chunk_id: str
    document_id: str
    nct_id: str
    section: str
    text: str
    source_url: str
    content_hash: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.rank, bool)
            or not isinstance(self.rank, int)
            or self.rank < 1
        ):
            raise ValueError("evidence rank must be a positive integer.")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise ValueError("evidence score must be numeric.")

        for field_name in (
            "chunk_id",
            "document_id",
            "section",
            "text",
            "source_url",
            "content_hash",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"evidence {field_name} cannot be empty.")
            object.__setattr__(self, field_name, value.strip())

        if not isinstance(self.nct_id, str) or not self.nct_id.strip():
            raise ValueError("evidence nct_id cannot be empty.")
        object.__setattr__(self, "nct_id", self.nct_id.strip())
        if not NCT_ID_PATTERN.fullmatch(self.nct_id):
            raise ValueError(f"invalid NCT identifier: {self.nct_id}")
        if not self.source_url.startswith(("http://", "https://")):
            raise ValueError("evidence source_url must start with http:// or https://.")
        object.__setattr__(self, "score", float(self.score))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "score": self.score,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "nct_id": self.nct_id,
            "section": self.section,
            "text": self.text,
            "source_url": self.source_url,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class RetrievalInput:
    retrieval_id: str
    created_at: datetime
    question: str
    collection: str
    query_limit: int
    evidence: tuple[EvidenceItem, ...]
    status: RetrievalStatus
    errors: tuple[str, ...] = ()
    schema_version: str = ANSWER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ANSWER_SCHEMA_VERSION:
            raise ValueError(f"retrieval schema_version must be {ANSWER_SCHEMA_VERSION}.")
        for field_name in ("retrieval_id", "question", "collection"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"retrieval {field_name} cannot be empty.")
            object.__setattr__(self, field_name, value.strip())
        if (
            isinstance(self.query_limit, bool)
            or not isinstance(self.query_limit, int)
            or not 1 <= self.query_limit <= 50
        ):
            raise ValueError("retrieval query limit must be between 1 and 50.")
        if self.status not in {"completed", "no_results", "failed"}:
            raise ValueError(f"unknown retrieval status: {self.status}")

        ranks = [item.rank for item in self.evidence]
        if len(ranks) != len(set(ranks)):
            raise ValueError("evidence ranks must be unique.")
        chunk_ids = [item.chunk_id for item in self.evidence]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("evidence chunk_id values must be unique.")
        if self.status == "completed" and not 1 <= len(self.evidence) <= MAX_EVIDENCE_ITEMS:
            raise ValueError(
                f"completed retrieval must contain 1-{MAX_EVIDENCE_ITEMS} evidence items."
            )
        if self.status == "no_results" and self.evidence:
            raise ValueError("no_results retrieval cannot contain evidence items.")

    @property
    def nct_ids(self) -> frozenset[str]:
        return frozenset(item.nct_id for item in self.evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "retrieval_id": self.retrieval_id,
            "created_at": _datetime_value(self.created_at),
            "query": {
                "text": self.question,
                "collection": self.collection,
                "limit": self.query_limit,
            },
            "results": [item.to_dict() for item in self.evidence],
            "status": self.status,
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class AnswerConfig:
    provider: str
    model: str
    prompt_version: str = PROMPT_VERSION
    max_model_turns: int = MAX_MODEL_TURNS
    max_tool_calls: int = MAX_TOOL_CALLS
    max_evidence_items: int = MAX_EVIDENCE_ITEMS
    max_output_tokens: int = MAX_OUTPUT_TOKENS
    max_claims: int = MAX_CLAIMS

    def __post_init__(self) -> None:
        for field_name in ("provider", "model", "prompt_version"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"answer {field_name} cannot be empty.")
            object.__setattr__(self, field_name, value.strip())
        expected = {
            "max_model_turns": MAX_MODEL_TURNS,
            "max_tool_calls": MAX_TOOL_CALLS,
            "max_evidence_items": MAX_EVIDENCE_ITEMS,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "max_claims": MAX_CLAIMS,
        }
        actual = {
            "max_model_turns": self.max_model_turns,
            "max_tool_calls": self.max_tool_calls,
            "max_evidence_items": self.max_evidence_items,
            "max_output_tokens": self.max_output_tokens,
            "max_claims": self.max_claims,
        }
        if actual != expected:
            raise ValueError(f"answer limits are fixed at {expected}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "max_model_turns": self.max_model_turns,
            "max_tool_calls": self.max_tool_calls,
            "max_evidence_items": self.max_evidence_items,
            "max_output_tokens": self.max_output_tokens,
            "max_claims": self.max_claims,
        }


@dataclass(frozen=True, slots=True)
class ModelClaim:
    text: str
    citation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("model claim text cannot be empty.")
        object.__setattr__(self, "text", self.text.strip())
        normalized_ids = tuple(
            dict.fromkeys(
                citation_id.strip()
                for citation_id in self.citation_ids
                if isinstance(citation_id, str) and citation_id.strip()
            )
        )
        if not normalized_ids:
            raise ValueError("model claim must contain at least one citation_id.")
        object.__setattr__(self, "citation_ids", normalized_ids)


@dataclass(frozen=True, slots=True)
class ModelResponse:
    status: ModelStatus
    claims: tuple[ModelClaim, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status == "answered":
            if not self.claims:
                raise ValueError("answered model response requires at least one claim.")
        elif self.status == "insufficient_evidence":
            if self.claims:
                raise ValueError("insufficient_evidence response cannot contain claims.")
            if not isinstance(self.reason, str) or not self.reason.strip():
                raise ValueError("insufficient_evidence response requires a reason.")
            object.__setattr__(self, "reason", self.reason.strip())
        else:
            raise ValueError(f"unknown model status: {self.status}")


@dataclass(frozen=True, slots=True)
class ModelToolCall:
    call_id: str
    name: str
    arguments: str

    def __post_init__(self) -> None:
        for field_name in ("call_id", "name", "arguments"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"model tool {field_name} cannot be empty.")
            object.__setattr__(self, field_name, value.strip())


@dataclass(frozen=True, slots=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: None = None

    def __post_init__(self) -> None:
        for field_name in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"model usage {field_name} must be non-negative.")

    def add(self, other: ModelUsage) -> ModelUsage:
        if (
            self.input_tokens is None
            and self.output_tokens is None
            and self.total_tokens is None
        ):
            return other
        if (
            other.input_tokens is None
            and other.output_tokens is None
            and other.total_tokens is None
        ):
            return self
        return ModelUsage(
            input_tokens=_optional_sum(self.input_tokens, other.input_tokens),
            output_tokens=_optional_sum(self.output_tokens, other.output_tokens),
            total_tokens=_optional_sum(self.total_tokens, other.total_tokens),
        )

    def to_dict(self) -> dict[str, int | None]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": None,
        }


@dataclass(frozen=True, slots=True)
class ModelTurn:
    content: str | None
    tool_calls: tuple[ModelToolCall, ...] = ()
    usage: ModelUsage = ModelUsage()


@dataclass(frozen=True, slots=True)
class MetadataLookup:
    lookup_id: str
    nct_id: str
    requested_at: datetime
    status: Literal["completed", "failed"]
    data: dict[str, Any] | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not NCT_ID_PATTERN.fullmatch(self.nct_id):
            raise ValueError(f"invalid metadata NCT identifier: {self.nct_id}")
        if self.status == "completed" and self.data is None:
            raise ValueError("completed metadata lookup requires data.")
        if self.status == "failed" and not self.error:
            raise ValueError("failed metadata lookup requires an error.")

    @property
    def citation_id(self) -> str:
        return f"trial-metadata:{self.nct_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "lookup_id": self.lookup_id,
            "nct_id": self.nct_id,
            "requested_at": _datetime_value(self.requested_at),
            "status": self.status,
            "data": self.data,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class AnswerCitation:
    citation_id: str
    source_type: CitationSource
    nct_id: str
    section: str | None
    source_url: str
    content_hash: str | None
    lookup_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "source_type": self.source_type,
            "nct_id": self.nct_id,
            "section": self.section,
            "source_url": self.source_url,
            "content_hash": self.content_hash,
            "lookup_id": self.lookup_id,
        }


@dataclass(frozen=True, slots=True)
class AnswerClaim:
    claim_id: str
    text: str
    citation_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "citation_ids": list(self.citation_ids),
        }


@dataclass(frozen=True, slots=True)
class AgentResult:
    content: str | None
    usage: ModelUsage
    tool_calls: tuple[MetadataLookup, ...] = ()
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AnswerRun:
    answer_id: str
    created_at: datetime
    status: AnswerStatus
    question: str
    retrieval_id: str
    retrieval_created_at: datetime
    evidence: tuple[EvidenceItem, ...]
    model: AnswerConfig
    claims: tuple[AnswerClaim, ...] = ()
    reason: str | None = None
    model_output: str | None = None
    citations: tuple[AnswerCitation, ...] = ()
    tool_calls: tuple[MetadataLookup, ...] = ()
    usage: ModelUsage = ModelUsage()
    latency_ms: int = 0
    errors: tuple[str, ...] = ()
    disclaimer: str = DISCLAIMER
    schema_version: str = ANSWER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status == "answered" and not self.claims:
            raise ValueError("answered run requires at least one claim.")
        if self.status == "insufficient_evidence":
            if self.claims:
                raise ValueError("insufficient_evidence run cannot contain claims.")
            if not self.reason:
                raise ValueError("insufficient_evidence run requires a reason.")
        if self.status == "failed" and not self.errors:
            raise ValueError("failed run requires at least one error.")
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "answer_id": self.answer_id,
            "created_at": _datetime_value(self.created_at),
            "status": self.status,
            "question": self.question,
            "retrieval_id": self.retrieval_id,
            "retrieval_created_at": _datetime_value(self.retrieval_created_at),
            "evidence": [item.to_dict() for item in self.evidence],
            "model": self.model.to_dict(),
            "claims": [claim.to_dict() for claim in self.claims],
            "reason": self.reason,
            "model_output": self.model_output,
            "citations": [citation.to_dict() for citation in self.citations],
            "tool_calls": [lookup.to_dict() for lookup in self.tool_calls],
            "usage": self.usage.to_dict(),
            "latency_ms": self.latency_ms,
            "errors": list(self.errors),
            "disclaimer": self.disclaimer,
        }


@dataclass(frozen=True, slots=True)
class AnswerOutcome:
    run: AnswerRun
    path: Path

    @property
    def exit_code(self) -> int:
        return 0 if self.run.status in {"answered", "insufficient_evidence"} else 1


def _optional_sum(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    return left + right


def _datetime_value(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
