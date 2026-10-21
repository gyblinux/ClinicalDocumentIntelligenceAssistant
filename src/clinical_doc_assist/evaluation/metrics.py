"""Deterministic retrieval and answer metrics for fixed evaluation cases."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from clinical_doc_assist.evaluation.models import (
    CaseEvaluation,
    EvaluationCase,
    EvaluationVerdict,
    FailureDiagnosis,
    MetricValue,
    PipelineBundle,
    expected_verdict_status,
)

_NON_WORD = re.compile(r"[^a-z0-9]+")


def evaluate_case(
    case: EvaluationCase,
    bundle: PipelineBundle,
    *,
    suite_version: str,
    configuration_fingerprint: str,
    now: datetime | None = None,
    verdict_id: str | None = None,
) -> tuple[CaseEvaluation, EvaluationVerdict | None]:
    """Calculate one case result and optional exact-key verdict."""

    retrieval_results = _list_of_dicts(bundle.retrieval.get("results"))
    answer = bundle.answer
    answer_status = _text(answer.get("status")) if answer else "failed"
    claims = _list_of_dicts(answer.get("claims")) if answer else []
    answer_citations = _list_of_dicts(answer.get("citations")) if answer else []
    answer_evidence = _list_of_dicts(answer.get("evidence")) if answer else []
    tool_calls = _list_of_dicts(answer.get("tool_calls")) if answer else []
    claim_texts = [_text(claim.get("text")) or "" for claim in claims]
    combined_claims = normalize_text(" ".join(claim_texts))

    hit, recall, mrr, retrieval_details = retrieval_metrics(
        case,
        retrieval_results,
    )
    citation_validity, citation_coverage = citation_metrics(
        claims,
        answer_citations,
        answer_evidence,
        retrieval_results,
        tool_calls=tool_calls,
        expected_answer=case.answerability == "answerable",
    )
    key_point_coverage = key_point_metric(case, combined_claims)
    forbidden_count = forbidden_count_metric(case, combined_claims)
    refusal_correct = refusal_metric(case, answer_status)

    metrics = (
        MetricValue(
            name="retrieval_hit_at_k",
            value=hit,
            passed=(hit == 1.0) if case.answerability == "answerable" else None,
            details=retrieval_details,
        ),
        MetricValue(
            name="retrieval_recall_at_k",
            value=recall,
            passed=(recall == 1.0) if case.answerability == "answerable" else None,
            details=retrieval_details,
        ),
        MetricValue(
            name="retrieval_mrr",
            value=mrr,
            passed=(mrr > 0.0) if case.answerability == "answerable" else None,
            details=retrieval_details,
        ),
        MetricValue(
            name="citation_validity",
            value=citation_validity,
            passed=(citation_validity == 1.0) if case.answerability == "answerable" else None,
            details=None,
        ),
        MetricValue(
            name="citation_coverage",
            value=citation_coverage,
            passed=(citation_coverage == 1.0) if case.answerability == "answerable" else None,
            details=None,
        ),
        MetricValue(
            name="required_key_point_coverage",
            value=key_point_coverage,
            passed=(key_point_coverage == 1.0) if case.answerability == "answerable" else None,
            details=None,
        ),
        MetricValue(
            name="forbidden_statement_violations",
            value=float(forbidden_count),
            passed=forbidden_count == 0,
            details={"count": forbidden_count},
        ),
        MetricValue(
            name="refusal_correctness",
            value=1.0 if refusal_correct else 0.0,
            passed=refusal_correct,
            details={"answer_status": answer_status},
        ),
    )
    diagnosis = diagnose_case(
        case,
        pipeline_status=_text(bundle.pipeline.get("status")),
        answer_status=answer_status,
        retrieval_hit=hit,
        retrieval_recall=recall,
        citation_validity=citation_validity,
        citation_coverage=citation_coverage,
        key_point_coverage=key_point_coverage,
        forbidden_count=forbidden_count,
        refusal_correct=refusal_correct,
    )
    timing = _mapping(bundle.pipeline.get("timing"))
    latency_ms = _integer(timing.get("total_ms"))
    usage = _mapping(answer.get("usage")) if answer else {}
    result = CaseEvaluation(
        case_id=case.case_id,
        rubric_version=case.rubric_version,
        pipeline_id=bundle.pipeline_id,
        retrieval_id=bundle.retrieval_id,
        answer_id=bundle.answer_id,
        configuration_fingerprint=configuration_fingerprint,
        metrics=metrics,
        diagnosis=diagnosis,
        latency_ms=latency_ms,
        usage=usage,
    )

    if bundle.answer_id is None:
        return result, None
    verdict = build_verdict(
        case,
        result,
        suite_version=suite_version,
        now=now or datetime.now(UTC),
        verdict_id=verdict_id or f"verdict-{uuid4().hex[:16]}",
    )
    return result, verdict


def retrieval_metrics(
    case: EvaluationCase,
    results: list[dict[str, Any]],
) -> tuple[float, float, float, dict[str, Any]]:
    expected = set(case.expected_evidence_ids)
    if not expected:
        return 0.0, 0.0, 0.0, {"expected": 0, "found": 0, "first_rank": None}

    ranked_ids = [
        value for result in results if (value := _text(result.get("chunk_id"))) is not None
    ]
    matching_ranks = [
        index for index, chunk_id in enumerate(ranked_ids, start=1) if chunk_id in expected
    ]
    found = len(set(ranked_ids) & expected)
    hit = 1.0 if matching_ranks else 0.0
    recall = found / len(expected)
    mrr = 1.0 / matching_ranks[0] if matching_ranks else 0.0
    return (
        hit,
        recall,
        mrr,
        {
            "expected": len(expected),
            "found": found,
            "first_rank": matching_ranks[0] if matching_ranks else None,
        },
    )


def citation_metrics(
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    answer_evidence: list[dict[str, Any]],
    retrieval_results: list[dict[str, Any]],
    *,
    tool_calls: list[dict[str, Any]],
    expected_answer: bool,
) -> tuple[float, float]:
    if not expected_answer:
        return 1.0, 1.0

    citation_by_id = {
        citation_id: citation
        for citation in citations
        if (citation_id := _text(citation.get("citation_id"))) is not None
    }
    allowed_chunks = {
        chunk_id
        for item in answer_evidence + retrieval_results
        if (chunk_id := _text(item.get("chunk_id"))) is not None
    }
    evidence_nct_ids = {
        nct_id for item in answer_evidence if (nct_id := _text(item.get("nct_id"))) is not None
    }
    allowed_metadata = {
        f"trial-metadata:{nct_id}"
        for lookup in tool_calls
        if _text(lookup.get("status")) == "completed"
        and (nct_id := _text(lookup.get("nct_id"))) in evidence_nct_ids
    }
    invalid = False
    covered = 0
    for claim in claims:
        ids = _string_tuple(claim.get("citation_ids"))
        if ids:
            covered += 1
        for citation_id in ids:
            citation = citation_by_id.get(citation_id)
            if citation is None:
                invalid = True
                continue
            source_type = _text(citation.get("source_type"))
            if source_type == "retrieval_evidence" and citation_id not in allowed_chunks:
                invalid = True
            if source_type == "trial_metadata" and citation_id not in allowed_metadata:
                invalid = True
            if source_type not in {"retrieval_evidence", "trial_metadata"}:
                invalid = True
    validity = 0.0 if invalid else 1.0
    coverage = covered / len(claims) if claims else 0.0
    return validity, coverage


def key_point_metric(case: EvaluationCase, normalized_answer: str) -> float:
    if case.answerability != "answerable":
        return 0.0
    matched = sum(
        1 for phrase in case.required_key_points if normalize_text(phrase) in normalized_answer
    )
    return matched / len(case.required_key_points)


def forbidden_count_metric(case: EvaluationCase, normalized_answer: str) -> int:
    return sum(
        1 for phrase in case.forbidden_statements if normalize_text(phrase) in normalized_answer
    )


def refusal_metric(case: EvaluationCase, answer_status: str) -> bool:
    if case.answerability == "answerable":
        return answer_status == "answered"
    return answer_status == "insufficient_evidence"


def diagnose_case(
    case: EvaluationCase,
    *,
    pipeline_status: str,
    answer_status: str,
    retrieval_hit: float,
    retrieval_recall: float,
    citation_validity: float,
    citation_coverage: float,
    key_point_coverage: float,
    forbidden_count: int,
    refusal_correct: bool,
) -> FailureDiagnosis:
    codes: list[str] = []
    stage: str = "none"
    intervention: str = "none"
    notes: list[str] = []

    if pipeline_status == "failed":
        codes.append("stage_failure")
        stage = "retrieval" if case.expected_evidence_ids and retrieval_hit == 0 else "answering"
        intervention = "retrieval" if stage == "retrieval" else "prompt"
        notes.append("One or more pipeline stages failed.")
    if case.answerability == "answerable":
        if retrieval_hit == 0:
            codes.append("retrieval_miss")
            stage = "retrieval"
            intervention = "retrieval"
            notes.append("No expected evidence was retrieved.")
        elif retrieval_recall < 1.0:
            codes.append("retrieval_low_rank")
            if stage == "none":
                stage = "retrieval"
                intervention = "retrieval"
            notes.append("Only part of the expected evidence was retrieved.")
        if citation_coverage < 1.0:
            codes.append("missing_citation")
            if stage == "none":
                stage = "answering"
                intervention = "prompt"
            notes.append("One or more claims lack citations.")
        if citation_validity < 1.0:
            codes.append("invalid_citation")
            if stage == "none":
                stage = "answering"
                intervention = "prompt"
            notes.append("One or more citations are invalid.")
        if key_point_coverage < 1.0:
            codes.append("missing_required_fact")
            if stage == "none":
                stage = "answering"
                intervention = "prompt"
            notes.append("The answer is missing expected facts.")
        if not refusal_correct and answer_status == "insufficient_evidence":
            codes.append("over_refusal")
            if stage == "none":
                stage = "answering"
                intervention = "abstention"
            notes.append("The answer abstained despite an answerable case.")
    elif answer_status == "answered":
        codes.append("false_answer")
        stage = "answering"
        intervention = "abstention"
        notes.append("The answer responded to an unanswerable case.")
    if forbidden_count:
        codes.append("forbidden_claim")
        stage = "answering"
        intervention = "prompt"
        notes.append("The answer contains explicitly forbidden statements.")

    return FailureDiagnosis(
        failure_codes=tuple(dict.fromkeys(codes)),
        affected_stage=stage,  # type: ignore[arg-type]
        intervention=intervention,  # type: ignore[arg-type]
        notes=" ".join(notes) if notes else None,
    )


def aggregate_metrics(results: tuple[CaseEvaluation, ...]) -> tuple[MetricValue, ...]:
    values: dict[str, list[float]] = {}
    for result in results:
        for metric in result.metrics:
            if metric.passed is not None:
                values.setdefault(metric.name, []).append(metric.value)
    return tuple(
        MetricValue(
            name=name,
            value=sum(items) / len(items),
            details={"applicable_cases": len(items)},
        )
        for name, items in sorted(values.items())
    )


def build_verdict(
    case: EvaluationCase,
    result: CaseEvaluation,
    *,
    suite_version: str,
    now: datetime,
    verdict_id: str,
) -> EvaluationVerdict:
    if result.answer_id is None:
        raise ValueError("cannot build a verdict without an answer ID.")
    metrics = {metric.name: metric for metric in result.metrics}
    checks = {
        "retrieval_relevance": _check(
            metrics,
            ("retrieval_hit_at_k", "retrieval_recall_at_k"),
        ),
        "citation_validity": _check(
            metrics,
            ("citation_validity", "citation_coverage"),
        ),
        "faithfulness": _check(
            metrics,
            ("required_key_point_coverage", "forbidden_statement_violations"),
        ),
        "refusal_correctness": _check(metrics, ("refusal_correctness",)),
    }
    return EvaluationVerdict(
        verdict_id=verdict_id,
        answer_id=result.answer_id,
        pipeline_id=result.pipeline_id,
        case_id=result.case_id,
        suite_version=suite_version,
        rubric_version=case.rubric_version,
        configuration_fingerprint=result.configuration_fingerprint,
        checks=checks,
        status=expected_verdict_status(checks),
        evaluated_at=now,
    )


def normalize_text(value: str) -> str:
    return " ".join(_NON_WORD.sub(" ", value.lower()).split())


def _check(metrics: dict[str, MetricValue], names: tuple[str, ...]) -> str:
    selected = [metrics[name] for name in names if name in metrics]
    applicable = [metric for metric in selected if metric.passed is not None]
    if not applicable:
        return "not_applicable"
    return "passed" if all(metric.passed for metric in applicable) else "failed"


def _list_of_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
