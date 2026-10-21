"""Deterministic plain-text presentation of validated answer artifacts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from clinical_doc_assist.evaluation.artifact_io import (
    load_json_object,
    required_text,
    write_json_atomic,
    write_text_atomic,
)
from clinical_doc_assist.evaluation.models import (
    MAX_PRESENTATION_WORDS,
    MAX_SUMMARY_WORDS,
    RENDERER_VERSION,
    REVIEW_CRITERIA,
    RUBRIC_VERSION,
    EvaluationInputError,
    EvaluationVerdict,
    EvaluationVerdictArtifact,
    PresentationError,
    PresentationOutcome,
    PresentationRequest,
    PresentationReview,
    PresentationSource,
    PresentationTooLongError,
    RenderedAnswer,
    RenderedClaim,
    count_words,
)
from clinical_doc_assist.evaluation.runner import (
    compute_configuration_fingerprint,
    load_pipeline_bundle,
)


class PresentationService:
    """Render one saved pipeline and answer as deterministic plain text."""

    def __init__(
        self,
        *,
        output_dir: Path = Path("artifacts/presentations"),
        now: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._output_dir = output_dir
        self._now = now or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: uuid4().hex[:16])

    def present(self, request: PresentationRequest) -> PresentationOutcome:
        bundle = load_pipeline_bundle(request.pipeline_path)
        presentation_id = f"presentation-{self._id_factory()}"
        verdict = (
            _matching_verdict(
                request.evaluation_path,
                case_id=request.case_id,
                pipeline_id=bundle.pipeline_id,
                answer_id=bundle.answer_id,
                configuration_fingerprint=compute_configuration_fingerprint(bundle.configuration),
            )
            if request.evaluation_path is not None
            else None
        )

        status, selection = _answer_status(bundle)
        if status == "answered":
            summary, claims, sources = _render_answered(bundle)
            answer_section = summary
        else:
            summary = None
            claims = ()
            sources = ()
            answer_section = selection

        text = _compose_text(
            status=status,
            answer_section=answer_section,
            claims=claims,
            sources=sources,
            verdict=verdict,
        )
        word_count = count_words(text)
        if word_count >= MAX_PRESENTATION_WORDS:
            raise PresentationTooLongError(
                f"presentation contains {word_count} words; limit is {MAX_PRESENTATION_WORDS - 1}."
            )

        text_path = request.output_path or self._output_dir / f"{presentation_id}.txt"
        metadata_path = text_path.with_suffix(".json")
        if text_path.suffix.lower() == ".json":
            raise EvaluationInputError(
                "presentation output path must use .txt; the .json suffix is reserved for metadata."
            )
        if text_path.exists() or metadata_path.exists():
            raise EvaluationInputError(f"presentation output already exists: {text_path}")
        try:
            rendered = RenderedAnswer(
                presentation_id=presentation_id,
                created_at=self._now(),
                pipeline_id=bundle.pipeline_id,
                answer_id=bundle.answer_id,
                renderer_version=RENDERER_VERSION,
                status=status,
                summary=summary,
                claims=claims,
                sources=sources,
                evaluation=verdict,
                limitations=_limitations(verdict),
                word_count=word_count,
                output_path=text_path.as_posix(),
            )
        except ValueError as exc:
            raise PresentationError(f"invalid rendered answer: {exc}") from exc
        write_json_atomic(metadata_path, rendered.to_dict())
        write_text_atomic(text_path, text)
        return PresentationOutcome(rendered, text, text_path, metadata_path)


def persist_presentation_review(
    input_path: Path,
    *,
    output_dir: Path = Path("artifacts/evaluations/presentation-reviews"),
    now: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> tuple[PresentationReview, Path]:
    """Validate and persist a human readability review."""

    payload = load_json_object(input_path, "presentation review")
    reviewer = required_text(payload, "reviewer")
    rubric_version = required_text(payload, "rubric_version")
    if rubric_version != RUBRIC_VERSION:
        raise EvaluationInputError(f"rubric_version must be {RUBRIC_VERSION}.")
    raw_cases = payload.get("case_ids")
    if (
        not isinstance(raw_cases, list)
        or len(raw_cases) != 5
        or not all(isinstance(item, str) and item.strip() for item in raw_cases)
    ):
        raise EvaluationInputError("case_ids must contain five strings.")
    case_ids = tuple(item.strip() for item in raw_cases)
    if len(set(case_ids)) != len(case_ids):
        raise EvaluationInputError("case_ids must contain five unique cases.")
    scores = payload.get("scores")
    if not isinstance(scores, dict):
        raise EvaluationInputError("scores must be an object.")
    if set(scores) != set(REVIEW_CRITERIA):
        raise EvaluationInputError("scores must contain exactly the five readability criteria.")
    normalized_scores: dict[str, int] = {}
    for criterion in REVIEW_CRITERIA:
        score = scores.get(criterion)
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 2:
            raise EvaluationInputError(f"score for {criterion} must be an integer from 0 to 2.")
        normalized_scores[criterion] = score
    aggregate = sum(normalized_scores.values())
    passed = (
        aggregate >= 8
        and normalized_scores["citation_clarity"] > 0
        and normalized_scores["caution"] > 0
    )
    if "aggregate_score" in payload and payload["aggregate_score"] != aggregate:
        raise EvaluationInputError("aggregate_score does not match criterion scores.")
    if "passed" in payload and payload["passed"] is not passed:
        raise EvaluationInputError("passed does not match the review threshold.")
    review_id = f"review-{(id_factory or (lambda: uuid4().hex[:16]))()}"
    created = payload.get("created_at")
    created_at = (
        _datetime(created) if created is not None else (now or (lambda: datetime.now(UTC)))()
    )
    try:
        review = PresentationReview(
            review_id=review_id,
            reviewer=reviewer,
            created_at=created_at,
            rubric_version=rubric_version,
            case_ids=case_ids,
            scores=normalized_scores,
            aggregate_score=aggregate,
            passed=passed,
            notes=(payload.get("notes") if isinstance(payload.get("notes"), str) else None),
        )
    except ValueError as exc:
        raise EvaluationInputError(f"invalid presentation review: {exc}") from exc
    path = output_dir / f"{review_id}.json"
    if path.exists():
        raise EvaluationInputError(f"presentation review already exists: {path}")
    write_json_atomic(path, review.to_dict())
    return review, path


def _render_answered(
    bundle,
) -> tuple[str, tuple[RenderedClaim, ...], tuple[PresentationSource, ...]]:
    if bundle.answer is None:
        raise PresentationError("answered pipeline has no answer artifact.")
    claims = _list_of_dicts(bundle.answer.get("claims"))
    if not claims:
        raise PresentationError("answered record contains no claims.")
    citations = {
        citation_id: citation
        for citation in _list_of_dicts(bundle.answer.get("citations"))
        if (citation_id := _text(citation.get("citation_id"))) is not None
    }

    source_by_key: dict[tuple[str, str], PresentationSource] = {}
    source_markers: dict[tuple[str, str], str] = {}
    source_sections: dict[tuple[str, str], list[str]] = {}
    rendered_claims: list[RenderedClaim] = []

    for index, raw_claim in enumerate(claims, start=1):
        text = _text(raw_claim.get("text"))
        citation_ids = _string_tuple(raw_claim.get("citation_ids"))
        if text is None or not citation_ids:
            raise PresentationError("every claim requires text and citations.")
        markers: list[str] = []
        for citation_id in citation_ids:
            citation = citations.get(citation_id)
            if citation is None:
                raise PresentationError(f"unknown answer citation: {citation_id}")
            source_url = _text(citation.get("source_url"))
            nct_id = _text(citation.get("nct_id"))
            if source_url is None or nct_id is None:
                raise PresentationError(f"citation {citation_id} lacks provenance.")
            key = (source_url, nct_id)
            if key not in source_markers:
                marker = f"[{len(source_markers) + 1}]"
                source_markers[key] = marker
                source_by_key[key] = PresentationSource(
                    marker=marker,
                    nct_id=nct_id,
                    source_url=source_url,
                    sections=(),
                )
            marker = source_markers[key]
            if marker not in markers:
                markers.append(marker)
            section = _text(citation.get("section"))
            if section is not None:
                sections = source_sections.setdefault(key, [])
                if section not in sections:
                    sections.append(section)
        rendered_claims.append(
            RenderedClaim(
                claim_id=_text(raw_claim.get("claim_id")) or f"claim-{index}",
                text=text,
                citation_ids=tuple(markers),
            )
        )

    sources = tuple(
        PresentationSource(
            marker=source.marker,
            nct_id=source.nct_id,
            source_url=source.source_url,
            sections=tuple(source_sections.get((source.source_url, source.nct_id), [])),
        )
        for source in source_by_key.values()
    )
    summary = _build_summary(rendered_claims)
    return summary, tuple(rendered_claims), sources


def _build_summary(claims: tuple[RenderedClaim, ...]) -> str:
    selected: list[str] = []
    for claim in claims[:5]:
        sentence = _claim_with_markers(claim)
        candidate = " ".join([*selected, sentence])
        if count_words(candidate) > MAX_SUMMARY_WORDS:
            break
        selected.append(sentence)
    if not selected:
        raise PresentationError("first claim exceeds the summary word limit.")
    return " ".join(selected)


def _compose_text(
    *,
    status: str,
    answer_section: str,
    claims: tuple[RenderedClaim, ...],
    sources: tuple[PresentationSource, ...],
    verdict: EvaluationVerdict | None,
) -> str:
    lines = ["ANSWER", answer_section, "", "QUALITY", f"Status: {status}"]
    lines.append("Citation checks: " + ("passed" if status == "answered" else "not_applicable"))
    if verdict is None:
        lines.append("Evaluation: Not independently evaluated for this exact answer")
    else:
        lines.append(
            f"Evaluation: {verdict.status.replace('_', ' ').title()} "
            f"(suite {verdict.suite_version}, rubric {verdict.rubric_version})"
        )
        for name, value in verdict.checks.items():
            lines.append(f"  {name.replace('_', ' ').title()}: {value}")
    lines.append("Confidence percentage: Not provided")

    if claims:
        lines.extend(["", "SUPPORTING DETAIL"])
        for index, claim in enumerate(claims, start=1):
            lines.append(f"{index}. {_claim_with_markers(claim)}")
    if sources:
        lines.extend(["", "SOURCES"])
        for source in sources:
            sections = ", ".join(source.sections) if source.sections else "not specified"
            lines.append(
                f"{source.marker} {source.nct_id} - {source.source_url} - sections: {sections}"
            )
    lines.extend(["", "LIMITATIONS", *_limitations(verdict)])
    return "\n".join(lines).strip() + "\n"


def _answer_status(bundle) -> tuple[str, str]:
    if bundle.answer is None:
        errors = bundle.pipeline.get("errors")
        detail = (
            "; ".join(item for item in errors if isinstance(item, str))
            if isinstance(errors, list)
            else ""
        )
        return "failed", "Pipeline failed: " + (detail or "answer artifact unavailable")
    status = _text(bundle.answer.get("status")) or "failed"
    if status == "answered":
        return status, ""
    if status == "insufficient_evidence":
        reason = _text(bundle.answer.get("reason")) or "Evidence is insufficient."
        return status, "Insufficient evidence: " + reason
    errors = bundle.answer.get("errors")
    detail = (
        "; ".join(item for item in errors if isinstance(item, str))
        if isinstance(errors, list)
        else ""
    )
    return "failed", "Pipeline failed: " + (detail or "answer record failed")


def _matching_verdict(
    path: Path,
    *,
    case_id: str | None,
    pipeline_id: str,
    answer_id: str | None,
    configuration_fingerprint: str,
) -> EvaluationVerdict | None:
    if case_id is None or answer_id is None:
        return None
    verdict_artifact = load_verdict_artifact(path)
    if len(verdict_artifact.rubric_versions) != 1:
        return None
    rubric_version = verdict_artifact.rubric_versions[0]
    matches = [
        verdict
        for verdict in verdict_artifact.verdicts
        if verdict.matches(
            answer_id=answer_id,
            pipeline_id=pipeline_id,
            case_id=case_id,
            suite_version=verdict_artifact.suite_version,
            rubric_version=rubric_version,
            configuration_fingerprint=configuration_fingerprint,
        )
    ]
    if len(matches) > 1:
        raise PresentationError("multiple evaluation verdicts match this exact answer.")
    return matches[0] if matches else None


def load_verdict_artifact(path: Path) -> EvaluationVerdictArtifact:
    """Load one versioned verdict artifact and validate its nested verdicts."""

    payload = load_json_object(path, "evaluation verdict artifact")
    raw_verdicts = payload.get("verdicts")
    raw_rubric_versions = payload.get("rubric_versions")
    if not isinstance(raw_verdicts, list):
        raise EvaluationInputError("verdicts must be a JSON array.")
    if not isinstance(raw_rubric_versions, list) or not all(
        isinstance(value, str) and value.strip() for value in raw_rubric_versions
    ):
        raise EvaluationInputError("rubric_versions must contain one or more non-empty strings.")

    verdicts: list[EvaluationVerdict] = []
    for item in raw_verdicts:
        if not isinstance(item, dict):
            raise EvaluationInputError("each verdict must be a JSON object.")
        try:
            verdicts.append(
                EvaluationVerdict(
                    verdict_id=required_text(item, "verdict_id"),
                    answer_id=required_text(item, "answer_id"),
                    pipeline_id=required_text(item, "pipeline_id"),
                    case_id=required_text(item, "case_id"),
                    suite_version=required_text(item, "suite_version"),
                    rubric_version=required_text(item, "rubric_version"),
                    configuration_fingerprint=required_text(item, "configuration_fingerprint"),
                    checks={
                        str(key): str(value) for key, value in _mapping(item.get("checks")).items()
                    },
                    status=required_text(item, "status"),  # type: ignore[arg-type]
                    evaluated_at=_datetime(required_text(item, "evaluated_at")),
                )
            )
        except (ValueError, TypeError) as exc:
            raise EvaluationInputError(f"invalid evaluation verdict: {exc}") from exc
    try:
        return EvaluationVerdictArtifact(
            schema_version=required_text(payload, "schema_version"),
            suite_version=required_text(payload, "suite_version"),
            rubric_versions=tuple(value.strip() for value in raw_rubric_versions),
            verdicts=tuple(verdicts),
        )
    except (ValueError, TypeError) as exc:
        raise EvaluationInputError(f"invalid evaluation verdict artifact: {exc}") from exc


def _limitations(verdict: EvaluationVerdict | None) -> tuple[str, ...]:
    limitations = []
    if verdict is None:
        limitations.append(
            "Semantic quality was not independently evaluated for this exact answer."
        )
    else:
        limitations.append(
            "Evaluation reflects the versioned fixed test case, "
            "not a guarantee for other questions."
        )
        limitations.append("Evaluation and presentation do not modify the original answer.")
    limitations.append("This is a summary of public research documents, not clinical advice.")
    return tuple(limitations)


def _claim_with_markers(claim: RenderedClaim) -> str:
    return claim.text + " " + "".join(claim.citation_ids)


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise EvaluationInputError("timestamp must be an ISO 8601 string.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvaluationInputError("timestamp must be valid ISO 8601.") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
