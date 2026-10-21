from __future__ import annotations

import json
from pathlib import Path

import pytest

from clinical_doc_assist.evaluation.cases import (
    load_evaluation_set,
    load_pipeline_map,
)
from clinical_doc_assist.evaluation.models import EvaluationInputError

FIXTURES = Path(__file__).parent / "fixtures" / "evaluation"
PROJECT_ROOT = Path(__file__).parents[1]


def test_loads_valid_twenty_case_set() -> None:
    evaluation_set = load_evaluation_set(FIXTURES / "cases-valid.json")

    assert evaluation_set.set_version == "evaluation-fixture-v1"
    assert len(evaluation_set.cases) == 20
    assert len({case.case_id for case in evaluation_set.cases}) == 20


def test_loads_windows_utf8_bom_file(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "cases-valid.json").read_text(encoding="utf-8"))
    path = tmp_path / "cases-with-bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8"))

    evaluation_set = load_evaluation_set(path)

    assert len(evaluation_set.cases) == 20


def test_loads_versioned_glp1_pilot_set() -> None:
    evaluation_set = load_evaluation_set(
        PROJECT_ROOT / "evaluation" / "cases" / "glp1-eval-v1.json"
    )

    assert evaluation_set.set_version == "glp1-eval-v1"
    assert len(evaluation_set.cases) == 20
    assert {case.answerability for case in evaluation_set.cases} == {
        "answerable",
        "unanswerable",
    }


def test_rejects_too_few_cases() -> None:
    with pytest.raises(EvaluationInputError, match="20-40"):
        load_evaluation_set(FIXTURES / "cases-too-few.json")


def test_rejects_too_many_cases(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "cases-valid.json").read_text())
    template = payload["cases"][0]
    payload["cases"] = [{**template, "case_id": f"case-{index}"} for index in range(41)]
    path = tmp_path / "too-many.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="20-40"):
        load_evaluation_set(path)


def test_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "cases-valid.json").read_text())
    payload["cases"] = [payload["cases"][0]] * 20
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="unique"):
        load_evaluation_set(path)


def test_rejects_unanswerable_case_with_expected_evidence(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "cases-valid.json").read_text())
    payload["cases"][0]["answerability"] = "unanswerable"
    path = tmp_path / "invalid-unanswerable.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="cannot define expected evidence"):
        load_evaluation_set(path)


def test_pipeline_map_requires_exact_case_coverage() -> None:
    evaluation_set = load_evaluation_set(FIXTURES / "cases-valid.json")
    complete = load_pipeline_map(FIXTURES / "pipeline-map.json", evaluation_set)
    assert set(complete) == {case.case_id for case in evaluation_set.cases}

    payload = json.loads((FIXTURES / "pipeline-map.json").read_text())
    payload.pop("case-020")
    payload["case-unknown"] = "tests/fixtures/evaluation/artifacts/pipeline.json"
    path = FIXTURES / "temporary-map.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        with pytest.raises(EvaluationInputError, match="missing=.*case-020"):
            load_pipeline_map(path, evaluation_set)
    finally:
        path.unlink(missing_ok=True)
