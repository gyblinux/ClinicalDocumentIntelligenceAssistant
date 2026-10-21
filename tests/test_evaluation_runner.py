from __future__ import annotations

import json
from itertools import count
from pathlib import Path
from types import SimpleNamespace

import pytest

from clinical_doc_assist.evaluation.cases import load_evaluation_set
from clinical_doc_assist.evaluation.models import EvaluationInputError
from clinical_doc_assist.evaluation.runner import (
    EvaluationService,
    compute_configuration_fingerprint,
    load_pipeline_bundle,
)
from tests.fixtures.evaluation.fakes import (
    FakeOrchestrator,
    write_evaluation_report,
    write_pipeline_bundle,
)

FIXTURES = Path(__file__).parent / "fixtures" / "evaluation"
PROJECT_ROOT = Path(__file__).parents[1]


def _write_pipeline_map(
    tmp_path: Path,
    evaluation_set,
) -> Path:
    mapping = {}
    for case in evaluation_set.cases:
        mapping[case.case_id] = str(write_pipeline_bundle(tmp_path / case.case_id, case))
    path = tmp_path / "pipeline-map.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    return path


def _service(
    tmp_path: Path,
    *,
    orchestrator=None,
    start: int = 1,
) -> EvaluationService:
    values = count(start)
    return EvaluationService(
        orchestrator=orchestrator,
        output_dir=tmp_path / "evaluations",
        id_factory=lambda: f"{next(values):016d}",
    )


def test_saved_mode_evaluates_all_twenty_cases(tmp_path: Path) -> None:
    cases = load_evaluation_set(FIXTURES / "cases-valid.json")
    mapping = _write_pipeline_map(tmp_path, cases)
    service = _service(tmp_path)

    outcome = service.run(
        FIXTURES / "cases-valid.json",
        pipeline_map=mapping,
    )

    assert outcome.run.mode == "saved"
    assert len(outcome.run.cases) == 20
    assert outcome.run.set_version == cases.set_version
    assert outcome.run.errors == ()
    assert outcome.path.is_file()
    assert outcome.verdicts_path.is_file()
    verdict_artifact = json.loads(outcome.verdicts_path.read_text(encoding="utf-8"))
    assert verdict_artifact["schema_version"] == "1.0"
    assert verdict_artifact["suite_version"] == cases.set_version
    assert verdict_artifact["rubric_versions"] == ["rag-rubric-v1"]
    assert len(verdict_artifact["verdicts"]) == 20


def test_saved_mode_is_reproducible_for_core_results(tmp_path: Path) -> None:
    cases = load_evaluation_set(FIXTURES / "cases-valid.json")
    mapping = _write_pipeline_map(tmp_path, cases)
    first = _service(tmp_path).run(
        FIXTURES / "cases-valid.json",
        pipeline_map=mapping,
    )
    second = _service(tmp_path, start=100).run(
        FIXTURES / "cases-valid.json",
        pipeline_map=mapping,
    )

    first_payload = first.run.to_dict()
    second_payload = second.run.to_dict()
    for payload in (first_payload, second_payload):
        payload.pop("evaluation_id")
        payload.pop("created_at")
        for case in payload["cases"]:
            case.pop("configuration_fingerprint")
    assert first_payload == second_payload


def test_generated_mode_calls_orchestration_once_per_case(tmp_path: Path) -> None:
    cases = load_evaluation_set(FIXTURES / "cases-valid.json")
    outcomes = []
    for case in cases.cases:
        path = write_pipeline_bundle(tmp_path / "generated" / case.case_id, case)
        outcomes.append(SimpleNamespace(path=path))
    orchestrator = FakeOrchestrator(outcomes)
    service = _service(tmp_path, orchestrator=orchestrator)

    outcome = service.run(FIXTURES / "cases-valid.json")

    assert outcome.run.mode == "generated"
    assert len(orchestrator.requests) == 20
    assert {request.collection for request in orchestrator.requests} == {"clinical_evidence_v1"}
    assert {request.limit for request in orchestrator.requests} == {5}
    assert [request.question for request in orchestrator.requests] == [
        case.question for case in cases.cases
    ]


def test_missing_pipeline_map_case_fails_before_evaluation(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "pipeline-map.json").read_text())
    payload.pop("case-020")
    path = tmp_path / "incomplete-map.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="missing=.*case-020"):
        _service(tmp_path).run(
            FIXTURES / "cases-valid.json",
            pipeline_map=path,
        )


def test_configuration_fingerprint_is_canonical() -> None:
    left = {"limit": 5, "collection": "clinical_evidence_v1"}
    right = {"collection": "clinical_evidence_v1", "limit": 5}
    changed = {"collection": "clinical_evidence_v1", "limit": 10}

    assert compute_configuration_fingerprint(left) == compute_configuration_fingerprint(right)
    assert compute_configuration_fingerprint(left) != compute_configuration_fingerprint(changed)


def test_pipeline_loader_rejects_non_object_retrieval_results(
    tmp_path: Path,
) -> None:
    cases = load_evaluation_set(FIXTURES / "cases-valid.json")
    pipeline_path = write_pipeline_bundle(tmp_path, cases.cases[0])
    bundle = load_pipeline_bundle(pipeline_path)
    retrieval_path = Path(str(bundle.pipeline["retrieval"]["path"]))
    retrieval = json.loads(retrieval_path.read_text(encoding="utf-8"))
    retrieval["results"].append("not-an-object")
    retrieval_path.write_text(json.dumps(retrieval), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="results.*objects"):
        load_pipeline_bundle(pipeline_path)


def test_pipeline_loader_rejects_unknown_answer_status(tmp_path: Path) -> None:
    cases = load_evaluation_set(FIXTURES / "cases-valid.json")
    pipeline_path = write_pipeline_bundle(tmp_path, cases.cases[0])
    bundle = load_pipeline_bundle(pipeline_path)
    answer_path = Path(str(bundle.pipeline["answer"]["path"]))
    answer = json.loads(answer_path.read_text(encoding="utf-8"))
    answer["status"] = "unknown"
    answer_path.write_text(json.dumps(answer), encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="answer status"):
        load_pipeline_bundle(pipeline_path)


def test_write_evaluation_report_helper_is_valid(tmp_path: Path) -> None:
    path = write_evaluation_report(tmp_path / "report.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"


def test_versioned_glp1_pilot_set_runs_with_linked_fixtures(
    tmp_path: Path,
) -> None:
    cases_path = PROJECT_ROOT / "evaluation" / "cases" / "glp1-eval-v1.json"
    cases = load_evaluation_set(cases_path)
    mapping = _write_pipeline_map(tmp_path, cases)

    outcome = _service(tmp_path).run(cases_path, pipeline_map=mapping)

    assert len(outcome.run.cases) == 20
    assert outcome.run.errors == ()
    assert outcome.run.rubric_versions == ("rag-rubric-v1",)
