"""Compare compatible baseline and candidate evaluation runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from clinical_doc_assist.evaluation.artifact_io import (
    load_json_object,
    required_text,
    write_json_atomic,
)
from clinical_doc_assist.evaluation.models import (
    EVALUATION_SCHEMA_VERSION,
    ComparisonOutcome,
    ComparisonRun,
    EvaluationInputError,
)


def compare_evaluations(
    baseline_path: Path,
    candidate_path: Path,
    *,
    output: Path | None = None,
    output_dir: Path = Path("artifacts/evaluations"),
) -> ComparisonOutcome:
    """Compare reports only when exactly one configuration variable differs."""

    baseline = load_json_object(baseline_path, "baseline evaluation report")
    candidate = load_json_object(candidate_path, "candidate evaluation report")
    _validate_compatible(baseline, candidate)

    baseline_config = _required_mapping(baseline, "configuration")
    candidate_config = _required_mapping(candidate, "configuration")
    keys = set(baseline_config) | set(candidate_config)
    changed = [key for key in sorted(keys) if baseline_config.get(key) != candidate_config.get(key)]
    if len(changed) != 1:
        raise EvaluationInputError(
            f"comparison requires exactly one changed configuration variable; got {changed}."
        )

    baseline_metrics = _metric_map(baseline)
    candidate_metrics = _metric_map(candidate)
    all_metrics = sorted(set(baseline_metrics) | set(candidate_metrics))
    deltas = {
        name: _round(candidate_metrics.get(name, 0.0) - baseline_metrics.get(name, 0.0))
        for name in all_metrics
    }
    changed_variable = changed[0]
    run = ComparisonRun(
        baseline_id=required_text(baseline, "evaluation_id"),
        candidate_id=required_text(candidate, "evaluation_id"),
        changed_variable=changed_variable,
        baseline_value=baseline_config.get(changed_variable),
        candidate_value=candidate_config.get(changed_variable),
        metric_deltas=deltas,
        latency_delta_ms=_total_latency(candidate) - _total_latency(baseline),
        cost_delta=_cost_delta(baseline, candidate),
        status="valid",
    )
    path = output or output_dir / f"comparison-{uuid4().hex[:16]}.json"
    if path.exists():
        raise EvaluationInputError(f"comparison output already exists: {path}")
    write_json_atomic(path, run.to_dict())
    return ComparisonOutcome(run, path)


def _validate_compatible(baseline: dict[str, Any], candidate: dict[str, Any]) -> None:
    if (
        baseline.get("schema_version") != EVALUATION_SCHEMA_VERSION
        or candidate.get("schema_version") != EVALUATION_SCHEMA_VERSION
    ):
        raise EvaluationInputError(
            f"evaluation reports require schema_version {EVALUATION_SCHEMA_VERSION}."
        )
    if required_text(baseline, "set_version") != required_text(candidate, "set_version"):
        raise EvaluationInputError("mismatched set_version.")
    if _rubric_versions(baseline) != _rubric_versions(candidate):
        raise EvaluationInputError("mismatched rubric versions.")
    baseline_cases = _case_ids(baseline)
    candidate_cases = _case_ids(candidate)
    if baseline_cases != candidate_cases:
        raise EvaluationInputError("comparison case sets do not match.")


def _metric_map(payload: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in _object_list(payload.get("aggregates"), "aggregates"):
        name = item.get("name")
        value = item.get("value")
        if not isinstance(name, str) or not name.strip():
            raise EvaluationInputError("aggregate name must be a non-empty string.")
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise EvaluationInputError("aggregate value must be numeric.")
        if name in result:
            raise EvaluationInputError(f"duplicate aggregate: {name}.")
        result[name] = float(value)
    return result


def _total_latency(payload: dict[str, Any]) -> int:
    total = 0
    for item in _object_list(payload.get("cases"), "cases"):
        value = item.get("latency_ms")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise EvaluationInputError("each case latency_ms must be a non-negative integer.")
        total += value
    return total


def _cost_delta(baseline: dict[str, Any], candidate: dict[str, Any]) -> float | None:
    baseline_cost = _total_estimated_cost(baseline)
    candidate_cost = _total_estimated_cost(candidate)
    if baseline_cost is None or candidate_cost is None:
        return None
    return _round(candidate_cost - baseline_cost)


def _total_estimated_cost(payload: dict[str, Any]) -> float | None:
    values: list[float] = []
    for item in _object_list(payload.get("cases"), "cases"):
        usage = _required_mapping(item, "usage")
        value = usage.get("estimated_cost")
        if value is None:
            return None
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise EvaluationInputError("estimated_cost must be numeric or null.")
        values.append(float(value))
    return sum(values) if values else None


def _required_mapping(
    payload: dict[str, Any],
    field_name: str,
) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise EvaluationInputError(f"{field_name} must be an object.")
    return value


def _object_list(value: object, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise EvaluationInputError(f"{field_name} must be a list of objects.")
    return value


def _rubric_versions(payload: dict[str, Any]) -> tuple[str, ...]:
    value = payload.get("rubric_versions")
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise EvaluationInputError("rubric_versions must contain non-empty strings.")
    return tuple(sorted(item.strip() for item in value))


def _case_ids(payload: dict[str, Any]) -> set[str]:
    cases = _object_list(payload.get("cases"), "cases")
    case_ids = [required_text(item, "case_id") for item in cases]
    unique_case_ids = set(case_ids)
    if len(unique_case_ids) != len(case_ids):
        raise EvaluationInputError("evaluation case IDs must be unique.")
    return unique_case_ids


def _round(value: float) -> float:
    return round(value, 6)
