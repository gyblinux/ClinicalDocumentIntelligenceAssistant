from __future__ import annotations

import json
from pathlib import Path

import pytest

from clinical_doc_assist.evaluation.comparison import compare_evaluations
from clinical_doc_assist.evaluation.models import EvaluationInputError
from tests.fixtures.evaluation.fakes import write_evaluation_report


def _reports(tmp_path: Path, *, candidate_limit: int = 10):
    baseline = write_evaluation_report(tmp_path / "baseline.json")
    candidate = write_evaluation_report(
        tmp_path / "candidate.json",
        evaluation_id="evaluation-candidate",
    )
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["configuration"]["limit"] = candidate_limit
    payload["aggregates"] = [
        {"name": "citation_validity", "value": 0.5, "passed": None, "details": None}
    ]
    payload["cases"][0]["latency_ms"] = 2500
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    return baseline, candidate


def test_compares_exactly_one_configuration_change(tmp_path: Path) -> None:
    baseline, candidate = _reports(tmp_path)

    outcome = compare_evaluations(
        baseline,
        candidate,
        output_dir=tmp_path / "output",
    )

    assert outcome.run.changed_variable == "limit"
    assert outcome.run.baseline_value == 5
    assert outcome.run.candidate_value == 10
    assert outcome.run.metric_deltas["citation_validity"] == -0.5
    assert outcome.run.latency_delta_ms == 1000
    assert outcome.path.is_file()


def test_rejects_multiple_configuration_changes(tmp_path: Path) -> None:
    baseline, candidate = _reports(tmp_path)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["configuration"]["collection"] = "different"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="exactly one"):
        compare_evaluations(baseline, candidate, output_dir=tmp_path / "output")


def test_rejects_mismatched_case_set_version(tmp_path: Path) -> None:
    baseline, candidate = _reports(tmp_path)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["set_version"] = "different"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="set_version"):
        compare_evaluations(baseline, candidate, output_dir=tmp_path / "output")


def test_rejects_different_case_ids(tmp_path: Path) -> None:
    baseline, candidate = _reports(tmp_path)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["cases"][0]["case_id"] = "case-different"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="case sets"):
        compare_evaluations(baseline, candidate, output_dir=tmp_path / "output")


def test_rejects_non_object_case_records(tmp_path: Path) -> None:
    baseline, candidate = _reports(tmp_path)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["cases"].append("not-an-object")
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="cases.*objects"):
        compare_evaluations(baseline, candidate, output_dir=tmp_path / "output")


def test_rejects_invalid_case_latency(tmp_path: Path) -> None:
    baseline, candidate = _reports(tmp_path)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["cases"][0]["latency_ms"] = -1
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="latency_ms"):
        compare_evaluations(baseline, candidate, output_dir=tmp_path / "output")


def test_rejects_invalid_aggregate_value(tmp_path: Path) -> None:
    baseline, candidate = _reports(tmp_path)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["aggregates"][0]["value"] = "not-a-number"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="aggregate value"):
        compare_evaluations(baseline, candidate, output_dir=tmp_path / "output")
