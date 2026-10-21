from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from clinical_doc_assist.evaluation.models import (
    EvaluationCase,
    EvaluationInputError,
    PresentationRequest,
    PresentationTooLongError,
)
from clinical_doc_assist.evaluation.presentation import (
    PresentationService,
    persist_presentation_review,
)
from clinical_doc_assist.evaluation.runner import load_pipeline_bundle
from tests.fixtures.evaluation.fakes import write_pipeline_bundle

FIXTURES = Path(__file__).parent / "fixtures" / "evaluation"
PIPELINE = FIXTURES / "artifacts" / "pipeline.json"


def fixed_now() -> datetime:
    return datetime(2026, 10, 21, 13, 0, tzinfo=UTC)


def service(tmp_path: Path) -> PresentationService:
    return PresentationService(
        output_dir=tmp_path / "presentations",
        now=fixed_now,
        id_factory=lambda: "fixture",
    )


def test_plain_text_contains_all_claims_and_deduplicated_sources(
    tmp_path: Path,
) -> None:
    outcome = service(tmp_path).present(PresentationRequest(pipeline_path=PIPELINE))

    assert outcome.text.startswith("ANSWER\n")
    assert "SUPPORTING DETAIL" in outcome.text
    assert "The study evaluates semaglutide's real-world effectiveness" in outcome.text
    assert "The study population includes adults" in outcome.text
    assert outcome.text.count("[1]") >= 3
    assert outcome.text.count("https://clinicaltrials.gov/study/NCT07424430") == 1
    assert "Confidence percentage: Not provided" in outcome.text
    assert "not clinical advice" in outcome.text
    assert outcome.text_path.is_file()
    assert outcome.metadata_path.is_file()


def test_presentation_does_not_use_raw_model_output(tmp_path: Path) -> None:
    outcome = service(tmp_path).present(PresentationRequest(pipeline_path=PIPELINE))
    answer = json.loads((FIXTURES / "artifacts" / "answer.json").read_text())

    assert answer["model_output"] not in outcome.text


def test_matching_verdict_is_rendered_without_trust_percentage(
    tmp_path: Path,
) -> None:
    outcome = service(tmp_path).present(
        PresentationRequest(
            pipeline_path=PIPELINE,
            case_id="case-001",
            evaluation_path=FIXTURES / "artifacts" / "verdicts-match.json",
        )
    )

    assert "Evaluation: Passed" in outcome.text
    assert "Faithfulness: passed" in outcome.text
    assert "Confidence percentage: Not provided" in outcome.text
    assert "%" not in outcome.text


def test_mismatched_or_missing_case_verdict_is_unevaluated(
    tmp_path: Path,
) -> None:
    mismatched = service(tmp_path).present(
        PresentationRequest(
            pipeline_path=PIPELINE,
            case_id="case-different",
            evaluation_path=FIXTURES / "artifacts" / "verdicts-match.json",
        )
    )
    missing_case = service(tmp_path / "missing").present(
        PresentationRequest(
            pipeline_path=PIPELINE,
            evaluation_path=FIXTURES / "artifacts" / "verdicts-match.json",
        )
    )

    assert "Not independently evaluated" in mismatched.text
    assert "Not independently evaluated" in missing_case.text


def test_mismatched_verdict_suite_is_unevaluated(tmp_path: Path) -> None:
    payload = json.loads(
        (FIXTURES / "artifacts" / "verdicts-match.json").read_text(encoding="utf-8")
    )
    payload["suite_version"] = "another-suite-v1"
    verdicts_path = tmp_path / "verdicts.json"
    verdicts_path.write_text(json.dumps(payload), encoding="utf-8")

    outcome = service(tmp_path).present(
        PresentationRequest(
            pipeline_path=PIPELINE,
            case_id="case-001",
            evaluation_path=verdicts_path,
        )
    )

    assert "Not independently evaluated" in outcome.text


def test_mismatched_verdict_rubric_is_unevaluated(tmp_path: Path) -> None:
    payload = json.loads(
        (FIXTURES / "artifacts" / "verdicts-match.json").read_text(encoding="utf-8")
    )
    payload["rubric_versions"] = ["another-rubric-v1"]
    verdicts_path = tmp_path / "verdicts.json"
    verdicts_path.write_text(json.dumps(payload), encoding="utf-8")

    outcome = service(tmp_path).present(
        PresentationRequest(
            pipeline_path=PIPELINE,
            case_id="case-001",
            evaluation_path=verdicts_path,
        )
    )

    assert "Not independently evaluated" in outcome.text


def test_abstention_view_has_no_answer_claims(tmp_path: Path) -> None:
    case = EvaluationCase(
        case_id="case-abstain",
        question="Unanswerable?",
        answerability="unanswerable",
        expected_evidence_ids=(),
        required_key_points=(),
        forbidden_statements=(),
        rubric_version="rag-rubric-v1",
    )
    pipeline = write_pipeline_bundle(tmp_path, case)

    outcome = service(tmp_path).present(PresentationRequest(pipeline_path=pipeline))

    assert "Insufficient evidence:" in outcome.text
    assert "SUPPORTING DETAIL" not in outcome.text
    assert outcome.rendered.claims == ()


def test_oversized_complete_view_fails_without_truncation(tmp_path: Path) -> None:
    case = EvaluationCase(
        case_id="case-long",
        question="Long?",
        answerability="answerable",
        expected_evidence_ids=("chunk-long",),
        required_key_points=("long",),
        forbidden_statements=(),
        rubric_version="rag-rubric-v1",
    )
    pipeline = write_pipeline_bundle(tmp_path, case)
    bundle = load_pipeline_bundle(pipeline)
    assert bundle.answer is not None
    answer_path = Path(str(bundle.pipeline["answer"]["path"]))
    answer = json.loads(answer_path.read_text())
    long_text = " ".join(["word"] * 170)
    answer["claims"] = [
        {
            "claim_id": f"claim-{index}",
            "text": long_text,
            "citation_ids": ["chunk-long"],
        }
        for index in range(6)
    ]
    answer_path.write_text(json.dumps(answer), encoding="utf-8")

    with pytest.raises(PresentationTooLongError):
        service(tmp_path).present(PresentationRequest(pipeline_path=pipeline))


def test_persists_valid_human_review(tmp_path: Path) -> None:
    review, path = persist_presentation_review(
        FIXTURES / "artifacts" / "presentation-review.json",
        output_dir=tmp_path / "reviews",
        now=fixed_now,
        id_factory=lambda: "fixture",
    )

    assert review.aggregate_score == 9
    assert review.passed
    assert path.is_file()


def test_human_review_requires_exactly_five_cases(tmp_path: Path) -> None:
    payload = json.loads(
        (FIXTURES / "artifacts" / "presentation-review.json").read_text(encoding="utf-8")
    )
    payload["case_ids"] = payload["case_ids"][:4]
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="five"):
        persist_presentation_review(
            review_path,
            output_dir=tmp_path / "reviews",
            now=fixed_now,
            id_factory=lambda: "invalid",
        )


def test_human_review_requires_unique_cases(tmp_path: Path) -> None:
    payload = json.loads(
        (FIXTURES / "artifacts" / "presentation-review.json").read_text(encoding="utf-8")
    )
    payload["case_ids"][-1] = payload["case_ids"][0]
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="unique"):
        persist_presentation_review(
            review_path,
            output_dir=tmp_path / "reviews",
            now=fixed_now,
            id_factory=lambda: "invalid",
        )


def test_human_review_requires_supported_rubric(tmp_path: Path) -> None:
    payload = json.loads(
        (FIXTURES / "artifacts" / "presentation-review.json").read_text(encoding="utf-8")
    )
    payload["rubric_version"] = "different-rubric-v1"
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="rubric_version"):
        persist_presentation_review(
            review_path,
            output_dir=tmp_path / "reviews",
            now=fixed_now,
            id_factory=lambda: "invalid",
        )


def test_presentation_rejects_json_output_path_collision(tmp_path: Path) -> None:
    output = tmp_path / "answer.json"

    with pytest.raises(EvaluationInputError, match="\\.txt"):
        service(tmp_path).present(
            PresentationRequest(
                pipeline_path=PIPELINE,
                output_path=output,
            )
        )
