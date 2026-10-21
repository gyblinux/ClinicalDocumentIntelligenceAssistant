"""Load and validate fixed evaluation cases and pipeline maps."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from clinical_doc_assist.evaluation.artifact_io import (
    load_json_object,
    required_text,
)
from clinical_doc_assist.evaluation.models import (
    EVALUATION_SCHEMA_VERSION,
    Answerability,
    EvaluationCase,
    EvaluationInputError,
    EvaluationSet,
)


def load_evaluation_set(path: Path) -> EvaluationSet:
    """Load one versioned 20-40 case evaluation set."""

    payload = load_json_object(path, "evaluation set")
    schema_version = payload.get("schema_version")
    if schema_version != EVALUATION_SCHEMA_VERSION:
        raise EvaluationInputError(
            f"evaluation schema_version must be {EVALUATION_SCHEMA_VERSION}."
        )
    set_version = payload.get("set_version")
    if not isinstance(set_version, str) or not set_version.strip():
        raise EvaluationInputError("set_version must be a non-empty string.")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise EvaluationInputError("evaluation cases must be a list.")

    try:
        return EvaluationSet(
            set_version=set_version.strip(),
            cases=tuple(_case(item) for item in raw_cases),
        )
    except ValueError as exc:
        raise EvaluationInputError(str(exc)) from exc


def load_pipeline_map(path: Path, evaluation_set: EvaluationSet) -> dict[str, Path]:
    """Load one saved pipeline path for every evaluation case."""

    payload = load_json_object(path, "pipeline map")
    expected_ids = {case.case_id for case in evaluation_set.cases}
    actual_ids = set(payload)
    missing = sorted(expected_ids - actual_ids)
    unknown = sorted(actual_ids - expected_ids)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if unknown:
            details.append(f"unknown={unknown}")
        raise EvaluationInputError("pipeline map mismatch: " + ", ".join(details))

    result: dict[str, Path] = {}
    for case_id, value in payload.items():
        if not isinstance(value, str) or not value.strip():
            raise EvaluationInputError(f"pipeline path for {case_id} must be a non-empty string.")
        result[case_id] = Path(value)
    return result


def _case(value: object) -> EvaluationCase:
    if not isinstance(value, dict):
        raise EvaluationInputError("each case must be an object.")
    case_id = required_text(value, "case_id")
    question = required_text(value, "question")
    rubric_version = required_text(value, "rubric_version")
    answerability = required_text(value, "answerability")
    if answerability not in {"answerable", "unanswerable"}:
        raise EvaluationInputError(f"unknown answerability for {case_id}: {answerability!r}")
    expected = _string_list(value, "expected_evidence_ids")
    required = _string_list(value, "required_key_points")
    forbidden = _string_list(value, "forbidden_statements")
    for field_name, items in (
        ("expected_evidence_ids", expected),
        ("required_key_points", required),
        ("forbidden_statements", forbidden),
    ):
        if len(items) != len(set(items)):
            raise EvaluationInputError(f"{case_id} contains duplicate {field_name} values.")
    return EvaluationCase(
        case_id=case_id,
        question=question,
        answerability=cast(Answerability, answerability),
        expected_evidence_ids=expected,
        required_key_points=required,
        forbidden_statements=forbidden,
        rubric_version=rubric_version,
    )


def _string_list(payload: dict[str, Any], field_name: str) -> tuple[str, ...]:
    value = payload.get(field_name, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise EvaluationInputError(f"{field_name} must be a string list.")
    return tuple(item.strip() for item in value)
