"""Typed records for evaluation and plain-text presentation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypeAlias

EVALUATION_SCHEMA_VERSION = "1.0"
PRESENTATION_SCHEMA_VERSION = "1.0"
RENDERER_VERSION = "presentation-v1"
RUBRIC_VERSION = "human-readability-v1"
VERDICT_CHECKS = frozenset(
    {
        "retrieval_relevance",
        "citation_validity",
        "faithfulness",
        "refusal_correctness",
    }
)
MIN_EVALUATION_CASES = 20
MAX_EVALUATION_CASES = 40
MAX_SUMMARY_WORDS = 180
MAX_PRESENTATION_WORDS = 1_000
DEFAULT_COLLECTION = "clinical_evidence_v1"
DEFAULT_RETRIEVAL_LIMIT = 5

Answerability: TypeAlias = Literal["answerable", "unanswerable"]
EvaluationMode: TypeAlias = Literal["saved", "generated"]
VerdictStatus: TypeAlias = Literal["passed", "failed", "not_applicable"]
AffectedStage: TypeAlias = Literal[
    "retrieval",
    "answering",
    "presentation",
    "evaluation",
    "none",
]
Intervention: TypeAlias = Literal[
    "prompt",
    "retrieval",
    "indexing",
    "abstention",
    "presentation",
    "case_or_rubric",
    "none",
]

FAILURE_CODES = frozenset(
    {
        "retrieval_miss",
        "retrieval_low_rank",
        "missing_citation",
        "invalid_citation",
        "missing_required_fact",
        "forbidden_claim",
        "false_answer",
        "over_refusal",
        "stage_failure",
        "presentation_integrity_error",
        "presentation_too_long",
    }
)
REVIEW_CRITERIA = (
    "direct_answer",
    "claim_completeness",
    "citation_clarity",
    "structure",
    "caution",
)


class EvaluationError(RuntimeError):
    """Base error for evaluation and presentation."""


class EvaluationInputError(EvaluationError):
    """Raised for invalid cases, arguments, or artifact links."""


class EvaluationOutputError(EvaluationError):
    """Raised when an evaluation artifact cannot be persisted."""


class PresentationError(EvaluationError):
    """Raised when a safe readable presentation cannot be produced."""


class PresentationTooLongError(PresentationError):
    """Raised when non-lossy presentation cannot fit below the word limit."""


def expected_verdict_status(checks: dict[str, str]) -> VerdictStatus:
    """Return the only status consistent with one complete verdict check set."""

    if set(checks) != VERDICT_CHECKS:
        raise ValueError("verdict checks must contain the four named checks.")
    if any(value not in {"passed", "failed", "not_applicable"} for value in checks.values()):
        raise ValueError("verdict checks use an unknown status.")
    applicable = [value for value in checks.values() if value != "not_applicable"]
    if not applicable:
        return "not_applicable"
    return "passed" if all(value == "passed" for value in applicable) else "failed"


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    question: str
    answerability: Answerability
    expected_evidence_ids: tuple[str, ...]
    required_key_points: tuple[str, ...]
    forbidden_statements: tuple[str, ...]
    rubric_version: str

    def __post_init__(self) -> None:
        for field_name in ("case_id", "question", "rubric_version"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} cannot be empty.")
            object.__setattr__(self, field_name, value.strip())
        if self.answerability not in {"answerable", "unanswerable"}:
            raise ValueError(f"unknown answerability: {self.answerability}")
        if self.answerability == "answerable":
            if not self.expected_evidence_ids:
                raise ValueError("answerable case requires expected evidence.")
            if not self.required_key_points:
                raise ValueError("answerable case requires key points.")
        else:
            if self.expected_evidence_ids:
                raise ValueError("unanswerable case cannot define expected evidence.")
            if self.required_key_points:
                raise ValueError("unanswerable case cannot define required key points.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "question": self.question,
            "answerability": self.answerability,
            "expected_evidence_ids": list(self.expected_evidence_ids),
            "required_key_points": list(self.required_key_points),
            "forbidden_statements": list(self.forbidden_statements),
            "rubric_version": self.rubric_version,
        }


@dataclass(frozen=True, slots=True)
class EvaluationSet:
    set_version: str
    cases: tuple[EvaluationCase, ...]
    schema_version: str = EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EVALUATION_SCHEMA_VERSION:
            raise ValueError(f"evaluation schema_version must be {EVALUATION_SCHEMA_VERSION}.")
        if not self.set_version.strip():
            raise ValueError("set_version cannot be empty.")
        if not MIN_EVALUATION_CASES <= len(self.cases) <= MAX_EVALUATION_CASES:
            raise ValueError(
                f"evaluation set must contain {MIN_EVALUATION_CASES}-{MAX_EVALUATION_CASES} cases."
            )
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case_id values must be unique.")

    @property
    def rubric_versions(self) -> tuple[str, ...]:
        return tuple(sorted({case.rubric_version for case in self.cases}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "set_version": self.set_version,
            "cases": [case.to_dict() for case in self.cases],
        }


@dataclass(frozen=True, slots=True)
class MetricValue:
    name: str
    value: float
    passed: bool | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "passed": self.passed,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class FailureDiagnosis:
    failure_codes: tuple[str, ...] = ()
    affected_stage: AffectedStage = "none"
    intervention: Intervention = "none"
    notes: str | None = None

    def __post_init__(self) -> None:
        unknown = set(self.failure_codes) - FAILURE_CODES
        if unknown:
            raise ValueError(f"unknown failure codes: {sorted(unknown)}")
        if self.affected_stage not in {
            "retrieval",
            "answering",
            "presentation",
            "evaluation",
            "none",
        }:
            raise ValueError(f"unknown affected stage: {self.affected_stage}")
        if self.intervention not in {
            "prompt",
            "retrieval",
            "indexing",
            "abstention",
            "presentation",
            "case_or_rubric",
            "none",
        }:
            raise ValueError(f"unknown intervention: {self.intervention}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_codes": list(self.failure_codes),
            "affected_stage": self.affected_stage,
            "intervention": self.intervention,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    case_id: str
    rubric_version: str
    pipeline_id: str
    retrieval_id: str | None
    answer_id: str | None
    configuration_fingerprint: str
    metrics: tuple[MetricValue, ...]
    diagnosis: FailureDiagnosis
    latency_ms: int
    usage: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "rubric_version": self.rubric_version,
            "pipeline_id": self.pipeline_id,
            "retrieval_id": self.retrieval_id,
            "answer_id": self.answer_id,
            "configuration_fingerprint": self.configuration_fingerprint,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "diagnosis": self.diagnosis.to_dict(),
            "latency_ms": self.latency_ms,
            "usage": self.usage,
        }


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    evaluation_id: str
    created_at: datetime
    set_version: str
    mode: EvaluationMode
    rubric_versions: tuple[str, ...]
    configuration: dict[str, Any]
    configuration_fingerprint: str
    cases: tuple[CaseEvaluation, ...]
    aggregates: tuple[MetricValue, ...]
    errors: tuple[str, ...] = ()
    schema_version: str = EVALUATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evaluation_id": self.evaluation_id,
            "created_at": _datetime_value(self.created_at),
            "set_version": self.set_version,
            "mode": self.mode,
            "rubric_versions": list(self.rubric_versions),
            "configuration": self.configuration,
            "configuration_fingerprint": self.configuration_fingerprint,
            "cases": [case.to_dict() for case in self.cases],
            "aggregates": [metric.to_dict() for metric in self.aggregates],
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class EvaluationVerdict:
    verdict_id: str
    answer_id: str
    pipeline_id: str
    case_id: str
    suite_version: str
    rubric_version: str
    configuration_fingerprint: str
    checks: dict[str, str]
    status: VerdictStatus
    evaluated_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "verdict_id",
            "answer_id",
            "pipeline_id",
            "case_id",
            "suite_version",
            "rubric_version",
            "configuration_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} cannot be empty.")
            object.__setattr__(self, field_name, value.strip())
        if self.status not in {"passed", "failed", "not_applicable"}:
            raise ValueError(f"unknown verdict status: {self.status}")
        if self.status != expected_verdict_status(self.checks):
            raise ValueError("verdict status does not match its checks.")

    def matches(
        self,
        *,
        answer_id: str,
        pipeline_id: str,
        case_id: str | None,
        suite_version: str,
        rubric_version: str,
        configuration_fingerprint: str,
    ) -> bool:
        return (
            case_id is not None
            and self.answer_id == answer_id
            and self.pipeline_id == pipeline_id
            and self.case_id == case_id
            and self.suite_version == suite_version
            and self.rubric_version == rubric_version
            and self.configuration_fingerprint == configuration_fingerprint
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict_id": self.verdict_id,
            "answer_id": self.answer_id,
            "pipeline_id": self.pipeline_id,
            "case_id": self.case_id,
            "suite_version": self.suite_version,
            "rubric_version": self.rubric_version,
            "configuration_fingerprint": self.configuration_fingerprint,
            "checks": self.checks,
            "status": self.status,
            "evaluated_at": _datetime_value(self.evaluated_at),
        }


@dataclass(frozen=True, slots=True)
class EvaluationVerdictArtifact:
    """Versioned metadata accompanying the verdicts from one evaluation run."""

    suite_version: str
    rubric_versions: tuple[str, ...]
    verdicts: tuple[EvaluationVerdict, ...]
    schema_version: str = EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EVALUATION_SCHEMA_VERSION:
            raise ValueError(f"verdict schema_version must be {EVALUATION_SCHEMA_VERSION}.")
        if not self.suite_version.strip():
            raise ValueError("suite_version cannot be empty.")
        if not self.rubric_versions or any(not value.strip() for value in self.rubric_versions):
            raise ValueError("rubric_versions must contain non-empty strings.")
        if len(self.rubric_versions) != len(set(self.rubric_versions)):
            raise ValueError("rubric_versions must be unique.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "suite_version": self.suite_version,
            "rubric_versions": list(self.rubric_versions),
            "verdicts": [verdict.to_dict() for verdict in self.verdicts],
        }


@dataclass(frozen=True, slots=True)
class ComparisonRun:
    baseline_id: str
    candidate_id: str
    changed_variable: str
    baseline_value: Any
    candidate_value: Any
    metric_deltas: dict[str, float]
    latency_delta_ms: int
    cost_delta: float | None
    status: Literal["valid", "rejected"]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "candidate_id": self.candidate_id,
            "changed_variable": self.changed_variable,
            "baseline_value": self.baseline_value,
            "candidate_value": self.candidate_value,
            "metric_deltas": self.metric_deltas,
            "latency_delta_ms": self.latency_delta_ms,
            "cost_delta": self.cost_delta,
            "status": self.status,
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class PresentationReview:
    review_id: str
    reviewer: str
    created_at: datetime
    rubric_version: str
    case_ids: tuple[str, ...]
    scores: dict[str, int]
    aggregate_score: int
    passed: bool
    notes: str | None = None

    def __post_init__(self) -> None:
        if len(self.case_ids) != 5 or len(set(self.case_ids)) != 5:
            raise ValueError("presentation review requires five unique case IDs.")
        if set(self.scores) != set(REVIEW_CRITERIA):
            raise ValueError("presentation review has incomplete criteria.")
        if any(not isinstance(score, int) or not 0 <= score <= 2 for score in self.scores.values()):
            raise ValueError("presentation scores must be integers from 0 to 2.")
        expected_total = sum(self.scores.values())
        if self.aggregate_score != expected_total:
            raise ValueError("aggregate_score must equal the criterion sum.")
        expected_pass = (
            expected_total >= 8
            and self.scores["citation_clarity"] > 0
            and self.scores["caution"] > 0
        )
        if self.passed != expected_pass:
            raise ValueError("presentation review passed flag does not match rubric.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "reviewer": self.reviewer,
            "created_at": _datetime_value(self.created_at),
            "rubric_version": self.rubric_version,
            "case_ids": list(self.case_ids),
            "scores": self.scores,
            "aggregate_score": self.aggregate_score,
            "passed": self.passed,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class PresentationRequest:
    pipeline_path: Path
    case_id: str | None = None
    evaluation_path: Path | None = None
    output_path: Path | None = None
    format: Literal["text"] = "text"
    renderer_version: str = RENDERER_VERSION


@dataclass(frozen=True, slots=True)
class RenderedClaim:
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
class PresentationSource:
    marker: str
    nct_id: str
    source_url: str
    sections: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker": self.marker,
            "nct_id": self.nct_id,
            "source_url": self.source_url,
            "sections": list(self.sections),
        }


@dataclass(frozen=True, slots=True)
class RenderedAnswer:
    presentation_id: str
    created_at: datetime
    pipeline_id: str
    answer_id: str | None
    renderer_version: str
    status: str
    summary: str | None
    claims: tuple[RenderedClaim, ...]
    sources: tuple[PresentationSource, ...]
    evaluation: EvaluationVerdict | None
    limitations: tuple[str, ...]
    word_count: int
    output_path: str
    schema_version: str = PRESENTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.output_path.strip():
            raise ValueError("presentation output_path cannot be empty.")
        if self.word_count >= MAX_PRESENTATION_WORDS:
            raise ValueError("presentation word_count must be below 1,000.")
        if self.summary is not None and count_words(self.summary) > MAX_SUMMARY_WORDS:
            raise ValueError("presentation summary must not exceed 180 words.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "presentation_id": self.presentation_id,
            "created_at": _datetime_value(self.created_at),
            "pipeline_id": self.pipeline_id,
            "answer_id": self.answer_id,
            "renderer_version": self.renderer_version,
            "status": self.status,
            "summary": self.summary,
            "claims": [claim.to_dict() for claim in self.claims],
            "sources": [source.to_dict() for source in self.sources],
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "limitations": list(self.limitations),
            "word_count": self.word_count,
            "output_path": self.output_path,
        }


@dataclass(frozen=True, slots=True)
class PresentationOutcome:
    rendered: RenderedAnswer
    text: str
    text_path: Path
    metadata_path: Path


@dataclass(frozen=True, slots=True)
class PipelineBundle:
    path: Path
    pipeline: dict[str, Any]
    retrieval: dict[str, Any]
    answer: dict[str, Any] | None

    @property
    def pipeline_id(self) -> str:
        return str(self.pipeline["pipeline_id"])

    @property
    def question(self) -> str:
        return str(self.pipeline["request"]["question"])

    @property
    def configuration(self) -> dict[str, Any]:
        value = self.pipeline.get("configuration")
        return value if isinstance(value, dict) else {}

    @property
    def retrieval_id(self) -> str | None:
        value = self.pipeline.get("retrieval")
        return str(value["artifact_id"]) if isinstance(value, dict) else None

    @property
    def answer_id(self) -> str | None:
        value = self.pipeline.get("answer")
        return str(value["artifact_id"]) if isinstance(value, dict) else None


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    run: EvaluationRun
    path: Path
    verdicts_path: Path


@dataclass(frozen=True, slots=True)
class ComparisonOutcome:
    run: ComparisonRun
    path: Path


def count_words(text: str) -> int:
    return len(text.split())


def _datetime_value(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
