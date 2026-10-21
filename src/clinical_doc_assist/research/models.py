"""Typed records for the research discovery stage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, TypeAlias

MAX_TOPIC_LENGTH = 500
MAX_CANDIDATES = 20

ScreeningStatus: TypeAlias = Literal["accepted", "rejected", "needs_review"]
RunStatus: TypeAlias = Literal["completed", "no_results", "failed"]
ReasonCode: TypeAlias = Literal[
    "approved_source",
    "within_date_window",
    "unique_identifier",
    "relevant_topic",
    "off_topic",
    "missing_identifier",
    "invalid_date",
    "outside_date_window",
    "duplicate",
    "ambiguous_metadata",
    "missing_reflection",
]

VALID_SCREENING_STATUSES = frozenset({"accepted", "rejected", "needs_review"})


class DiscoveryError(RuntimeError):
    """Base error for research discovery."""


class ClockUnavailableError(DiscoveryError):
    """Raised when the current time cannot be obtained."""


class SourceError(DiscoveryError):
    """Raised when the approved source cannot return usable data."""


class AgentError(DiscoveryError):
    """Raised when the research agent cannot complete a bounded run."""


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    """A validated topic and inclusive update-date window."""

    topic: str
    updated_after: date
    updated_before: date
    limit: int = 5

    def __post_init__(self) -> None:
        topic = self.topic.strip()
        object.__setattr__(self, "topic", topic)

        if not topic:
            raise ValueError("topic cannot be empty.")
        if len(topic) > MAX_TOPIC_LENGTH:
            raise ValueError(f"topic cannot exceed {MAX_TOPIC_LENGTH} characters.")
        if self.updated_before < self.updated_after:
            raise ValueError("updated_before cannot be before updated_after.")
        if isinstance(self.limit, bool) or not 1 <= self.limit <= MAX_CANDIDATES:
            raise ValueError(f"limit must be between 1 and {MAX_CANDIDATES}.")

    def to_dict(self) -> dict[str, str | int]:
        return {
            "topic": self.topic,
            "updated_after": self.updated_after.isoformat(),
            "updated_before": self.updated_before.isoformat(),
            "limit": self.limit,
        }


@dataclass(frozen=True, slots=True)
class ResearchCandidate:
    """One normalized record returned by an approved source."""

    nct_id: str | None
    title: str
    source_url: str
    source_type: str
    updated_date: date | None
    first_posted_date: date | None
    status: str | None
    study_type: str | None
    sponsor: str | None
    evidence_snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "nct_id": self.nct_id,
            "title": self.title,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "updated_date": _date_value(self.updated_date),
            "first_posted_date": _date_value(self.first_posted_date),
            "status": self.status,
            "study_type": self.study_type,
            "sponsor": self.sponsor,
            "evidence_snippet": self.evidence_snippet,
        }


@dataclass(frozen=True, slots=True)
class ModelDecision:
    """The model's advisory classification for one candidate."""

    nct_id: str
    status: ScreeningStatus
    reason_codes: tuple[ReasonCode, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in VALID_SCREENING_STATUSES:
            raise ValueError(f"Unknown screening status: {self.status}")


@dataclass(frozen=True, slots=True)
class SearchRecord:
    """An executed source query."""

    query: str
    updated_after: date
    updated_before: date
    result_count: int

    def to_dict(self) -> dict[str, str | int]:
        return {
            "query": self.query,
            "updated_after": self.updated_after.isoformat(),
            "updated_before": self.updated_before.isoformat(),
            "result_count": self.result_count,
        }


@dataclass(frozen=True, slots=True)
class ScreeningDecision:
    """The final application-authoritative screening result."""

    candidate: ResearchCandidate
    status: ScreeningStatus
    reason_codes: tuple[ReasonCode, ...]
    duplicate_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "duplicate_of": self.duplicate_of,
        }


@dataclass(frozen=True, slots=True)
class ScreeningResult:
    """Candidates grouped by final screening status."""

    accepted: tuple[ScreeningDecision, ...]
    rejected: tuple[ScreeningDecision, ...]
    needs_review: tuple[ScreeningDecision, ...]


@dataclass(frozen=True, slots=True)
class DiscoveryRun:
    """One inspectable discovery run."""

    status: RunStatus
    request: DiscoveryRequest
    current_time: str | None
    searches: tuple[SearchRecord, ...]
    accepted: tuple[ScreeningDecision, ...]
    rejected: tuple[ScreeningDecision, ...]
    needs_review: tuple[ScreeningDecision, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "request": self.request.to_dict(),
            "current_time": self.current_time,
            "searches": [search.to_dict() for search in self.searches],
            "accepted": [decision.to_dict() for decision in self.accepted],
            "rejected": [decision.to_dict() for decision in self.rejected],
            "needs_review": [decision.to_dict() for decision in self.needs_review],
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class ToolResult:
    """A typed success or failure returned by an agent tool."""

    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None

    @classmethod
    def success(cls, data: dict[str, Any]) -> ToolResult:
        return cls(ok=True, data=data)

    @classmethod
    def failure(cls, error: str) -> ToolResult:
        return cls(ok=False, error=error)

    def to_dict(self) -> dict[str, Any]:
        if self.ok:
            return {"ok": True, "result": self.data or {}}
        return {"ok": False, "error": self.error or "unknown tool error"}


def _date_value(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None
