from __future__ import annotations

from datetime import UTC, datetime

import pytest

from clinical_doc_assist.evaluation.metrics import (
    aggregate_metrics,
    build_verdict,
    citation_metrics,
    diagnose_case,
    forbidden_count_metric,
    key_point_metric,
    normalize_text,
    refusal_metric,
    retrieval_metrics,
)
from clinical_doc_assist.evaluation.models import (
    CaseEvaluation,
    EvaluationCase,
    EvaluationVerdict,
    FailureDiagnosis,
    MetricValue,
)


def case(
    *,
    answerability: str = "answerable",
    forbidden: tuple[str, ...] = (),
) -> EvaluationCase:
    return EvaluationCase(
        case_id="case-1",
        question="Question?",
        answerability=answerability,  # type: ignore[arg-type]
        expected_evidence_ids=("chunk-a", "chunk-b") if answerability == "answerable" else (),
        required_key_points=("required fact",) if answerability == "answerable" else (),
        forbidden_statements=forbidden,
        rubric_version="rag-rubric-v1",
    )


def test_retrieval_hit_recall_and_mrr() -> None:
    hit, recall, mrr, details = retrieval_metrics(
        case(),
        [
            {"chunk_id": "chunk-x"},
            {"chunk_id": "chunk-a"},
            {"chunk_id": "chunk-b"},
        ],
    )

    assert hit == 1.0
    assert recall == 1.0
    assert mrr == 0.5
    assert details == {"expected": 2, "found": 2, "first_rank": 2}


def test_retrieval_miss_returns_zero_scores() -> None:
    hit, recall, mrr, details = retrieval_metrics(
        case(),
        [{"chunk_id": "chunk-x"}],
    )

    assert (hit, recall, mrr) == (0.0, 0.0, 0.0)
    assert details["found"] == 0


def test_citation_validity_and_coverage() -> None:
    claims = [
        {"text": "One.", "citation_ids": ["chunk-a"]},
        {"text": "Two.", "citation_ids": ["chunk-b"]},
    ]
    citations = [
        {
            "citation_id": "chunk-a",
            "source_type": "retrieval_evidence",
        },
        {
            "citation_id": "chunk-b",
            "source_type": "retrieval_evidence",
        },
    ]
    evidence = [{"chunk_id": "chunk-a"}, {"chunk_id": "chunk-b"}]
    retrieval = evidence

    validity, coverage = citation_metrics(
        claims,
        citations,
        evidence,
        retrieval,
        tool_calls=[],
        expected_answer=True,
    )

    assert validity == 1.0
    assert coverage == 1.0


def test_citation_invalid_when_claim_points_outside_evidence() -> None:
    claims = [{"text": "One.", "citation_ids": ["chunk-x"]}]
    citations = [{"citation_id": "chunk-x", "source_type": "retrieval_evidence"}]

    validity, coverage = citation_metrics(
        claims,
        citations,
        [{"chunk_id": "chunk-a"}],
        [{"chunk_id": "chunk-a"}],
        tool_calls=[],
        expected_answer=True,
    )

    assert validity == 0.0
    assert coverage == 1.0


def test_metadata_citation_requires_successful_lookup() -> None:
    claims = [
        {
            "text": "Metadata fact.",
            "citation_ids": ["trial-metadata:NCT07424430"],
        }
    ]
    citations = [
        {
            "citation_id": "trial-metadata:NCT07424430",
            "source_type": "trial_metadata",
        }
    ]
    evidence = [{"chunk_id": "chunk-a", "nct_id": "NCT07424430"}]

    missing_lookup = citation_metrics(
        claims,
        citations,
        evidence,
        evidence,
        tool_calls=[],
        expected_answer=True,
    )
    completed_lookup = citation_metrics(
        claims,
        citations,
        evidence,
        evidence,
        tool_calls=[{"nct_id": "NCT07424430", "status": "completed"}],
        expected_answer=True,
    )

    assert missing_lookup == (0.0, 1.0)
    assert completed_lookup == (1.0, 1.0)


def test_key_point_and_forbidden_statement_detection() -> None:
    normalized = normalize_text("The required fact is present, but final results are not.")
    assert key_point_metric(case(), normalized) == 1.0
    assert forbidden_count_metric(case(forbidden=("final results",)), normalized) == 1


def test_refusal_correctness_for_answerable_and_unanswerable_cases() -> None:
    assert refusal_metric(case(), "answered")
    assert not refusal_metric(case(), "insufficient_evidence")
    assert refusal_metric(case(answerability="unanswerable"), "insufficient_evidence")
    assert not refusal_metric(case(answerability="unanswerable"), "answered")


def test_diagnosis_attributes_retrieval_failure() -> None:
    diagnosis = diagnose_case(
        case(),
        pipeline_status="failed",
        answer_status="failed",
        retrieval_hit=0.0,
        retrieval_recall=0.0,
        citation_validity=1.0,
        citation_coverage=0.0,
        key_point_coverage=0.0,
        forbidden_count=0,
        refusal_correct=False,
    )

    assert "stage_failure" in diagnosis.failure_codes
    assert "retrieval_miss" in diagnosis.failure_codes
    assert diagnosis.affected_stage == "retrieval"
    assert diagnosis.intervention == "retrieval"


def test_aggregate_metrics_average_applicable_values() -> None:
    first = CaseEvaluation(
        case_id="a",
        rubric_version="r",
        pipeline_id="p1",
        retrieval_id="r1",
        answer_id="a1",
        configuration_fingerprint="f",
        metrics=(
            MetricValue("citation_validity", 1.0, True),
            MetricValue("not_applicable", 0.0, None),
        ),
        diagnosis=FailureDiagnosis(),
        latency_ms=1,
        usage={},
    )
    second = CaseEvaluation(
        case_id="b",
        rubric_version="r",
        pipeline_id="p2",
        retrieval_id="r2",
        answer_id="a2",
        configuration_fingerprint="f",
        metrics=(
            MetricValue("citation_validity", 0.0, False),
            MetricValue("not_applicable", 1.0, None),
        ),
        diagnosis=FailureDiagnosis(),
        latency_ms=1,
        usage={},
    )

    aggregates = aggregate_metrics((first, second))

    assert len(aggregates) == 1
    assert aggregates[0].name == "citation_validity"
    assert aggregates[0].value == 0.5


def test_verdict_has_exact_artifact_keys() -> None:
    result = CaseEvaluation(
        case_id="case-1",
        rubric_version="rag-rubric-v1",
        pipeline_id="pipeline-1",
        retrieval_id="retrieval-1",
        answer_id="answer-1",
        configuration_fingerprint="sha256:fixture",
        metrics=(
            MetricValue("retrieval_hit_at_k", 1.0, True),
            MetricValue("retrieval_recall_at_k", 1.0, True),
            MetricValue("citation_validity", 1.0, True),
            MetricValue("citation_coverage", 1.0, True),
            MetricValue("required_key_point_coverage", 1.0, True),
            MetricValue("forbidden_statement_violations", 0.0, True),
            MetricValue("refusal_correctness", 1.0, True),
        ),
        diagnosis=FailureDiagnosis(),
        latency_ms=1,
        usage={},
    )

    verdict = build_verdict(
        case(),
        result,
        suite_version="suite-v1",
        now=datetime(2026, 10, 21, tzinfo=UTC),
        verdict_id="verdict-1",
    )

    assert verdict is not None
    assert verdict.status == "passed"
    assert verdict.pipeline_id == "pipeline-1"
    assert "trust_percentage" not in verdict.to_dict()


def test_verdict_requires_all_named_checks() -> None:
    with pytest.raises(ValueError, match="checks"):
        EvaluationVerdict(
            verdict_id="verdict-1",
            answer_id="answer-1",
            pipeline_id="pipeline-1",
            case_id="case-1",
            suite_version="suite-v1",
            rubric_version="rag-rubric-v1",
            configuration_fingerprint="sha256:fixture",
            checks={},
            status="passed",
            evaluated_at=datetime(2026, 10, 21, tzinfo=UTC),
        )


def test_verdict_status_must_match_checks() -> None:
    with pytest.raises(ValueError, match="status"):
        EvaluationVerdict(
            verdict_id="verdict-1",
            answer_id="answer-1",
            pipeline_id="pipeline-1",
            case_id="case-1",
            suite_version="suite-v1",
            rubric_version="rag-rubric-v1",
            configuration_fingerprint="sha256:fixture",
            checks={
                "retrieval_relevance": "passed",
                "citation_validity": "failed",
                "faithfulness": "passed",
                "refusal_correctness": "passed",
            },
            status="passed",
            evaluated_at=datetime(2026, 10, 21, tzinfo=UTC),
        )
