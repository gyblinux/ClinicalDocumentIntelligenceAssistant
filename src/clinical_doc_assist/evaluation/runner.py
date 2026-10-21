"""Load linked pipeline artifacts and orchestrate one evaluation run."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from clinical_doc_assist.evaluation.artifact_io import (
    load_json_object,
    required_text,
    write_json_atomic,
)
from clinical_doc_assist.evaluation.cases import (
    load_evaluation_set,
    load_pipeline_map,
)
from clinical_doc_assist.evaluation.metrics import (
    aggregate_metrics,
    evaluate_case,
)
from clinical_doc_assist.evaluation.models import (
    DEFAULT_COLLECTION,
    DEFAULT_RETRIEVAL_LIMIT,
    CaseEvaluation,
    EvaluationCase,
    EvaluationError,
    EvaluationInputError,
    EvaluationOutcome,
    EvaluationRun,
    EvaluationVerdict,
    EvaluationVerdictArtifact,
    FailureDiagnosis,
    PipelineBundle,
)
from clinical_doc_assist.orchestration.models import PipelineOutcome, QuestionRequest


class OrchestrationCommands(Protocol):
    def ask(self, request: QuestionRequest) -> PipelineOutcome: ...


class EvaluationService:
    """Evaluate saved or freshly generated feature 006 pipelines."""

    def __init__(
        self,
        *,
        orchestrator: OrchestrationCommands | None = None,
        output_dir: Path = Path("artifacts/evaluations"),
        now: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._output_dir = output_dir
        self._now = now or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: uuid4().hex[:16])

    def run(
        self,
        cases_path: Path,
        *,
        pipeline_map: Path | None = None,
        collection: str = DEFAULT_COLLECTION,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
    ) -> EvaluationOutcome:
        evaluation_set = load_evaluation_set(cases_path)
        mode = "saved" if pipeline_map is not None else "generated"
        mapped_paths = (
            load_pipeline_map(pipeline_map, evaluation_set) if pipeline_map is not None else None
        )
        if mapped_paths is None and self._orchestrator is None:
            raise EvaluationInputError("generated mode requires an orchestration service.")

        evaluation_id = f"evaluation-{self._id_factory()}"
        results: list[CaseEvaluation] = []
        errors: list[str] = []
        configuration: dict[str, Any] | None = None
        common_configuration_fingerprint: str | None = None
        verdicts: list[EvaluationVerdict] = []

        for case in evaluation_set.cases:
            try:
                pipeline_path = (
                    mapped_paths[case.case_id]
                    if mapped_paths is not None
                    else self._generate(case, collection=collection, limit=limit)
                )
                bundle = load_pipeline_bundle(pipeline_path)
                validate_bundle_for_case(bundle, case)
                fingerprint = compute_configuration_fingerprint(bundle.configuration)
                if configuration is None:
                    configuration = bundle.configuration
                    common_configuration_fingerprint = fingerprint
                elif fingerprint != common_configuration_fingerprint:
                    raise EvaluationInputError("evaluation cases use different configurations.")
                result, verdict = evaluate_case(
                    case,
                    bundle,
                    suite_version=evaluation_set.set_version,
                    configuration_fingerprint=fingerprint,
                    now=self._now(),
                    verdict_id=f"verdict-{self._id_factory()}",
                )
            except (EvaluationError, OSError) as exc:
                message = f"{case.case_id}: {exc}"
                errors.append(message)
                result = _failed_case_result(case, message)
                verdict = None
            results.append(result)
            if verdict is not None:
                verdicts.append(verdict)

        if configuration is None:
            configuration = {
                "collection": collection,
                "limit": limit,
                "embedding_model": None,
                "embedding_dimension": None,
                "answer_model": None,
                "prompt_version": None,
            }
            common_configuration_fingerprint = compute_configuration_fingerprint(configuration)

        run = EvaluationRun(
            evaluation_id=evaluation_id,
            created_at=self._now(),
            set_version=evaluation_set.set_version,
            mode=mode,
            rubric_versions=evaluation_set.rubric_versions,
            configuration=configuration,
            configuration_fingerprint=common_configuration_fingerprint or "",
            cases=tuple(results),
            aggregates=aggregate_metrics(tuple(results)),
            errors=tuple(errors),
        )
        output_path = self._output_dir / f"{evaluation_id}.json"
        verdicts_path = self._output_dir / f"{evaluation_id}-verdicts.json"
        verdict_artifact = EvaluationVerdictArtifact(
            suite_version=evaluation_set.set_version,
            rubric_versions=evaluation_set.rubric_versions,
            verdicts=tuple(verdicts),
        )
        write_json_atomic(output_path, run.to_dict())
        write_json_atomic(verdicts_path, verdict_artifact.to_dict())
        return EvaluationOutcome(run, output_path, verdicts_path)

    def _generate(
        self,
        case: EvaluationCase,
        *,
        collection: str,
        limit: int,
    ) -> Path:
        if self._orchestrator is None:
            raise EvaluationInputError("orchestration service is unavailable.")
        outcome = self._orchestrator.ask(
            QuestionRequest(
                question=case.question,
                collection=collection,
                limit=limit,
            )
        )
        return outcome.path


def load_pipeline_bundle(path: Path) -> PipelineBundle:
    """Load a feature 006 pipeline and its linked stage artifacts."""

    pipeline = load_json_object(path, "pipeline artifact")
    if pipeline.get("schema_version") != "1.0":
        raise EvaluationInputError("pipeline schema_version must be 1.0.")
    required_text(pipeline, "pipeline_id")
    _required_choice(
        pipeline,
        "status",
        {"answered", "insufficient_evidence", "failed"},
        label="pipeline status",
    )
    request = _mapping(pipeline.get("request"))
    required_text(request, "question")
    if not isinstance(pipeline.get("configuration"), dict):
        raise EvaluationInputError("pipeline configuration must be an object.")
    retrieval_ref = pipeline.get("retrieval")
    if not isinstance(retrieval_ref, dict):
        raise EvaluationInputError("pipeline has no retrieval artifact reference.")
    required_text(retrieval_ref, "artifact_id")
    retrieval_path = _artifact_path(retrieval_ref)
    retrieval = load_json_object(retrieval_path, "retrieval artifact")
    if retrieval.get("schema_version") != "1.0":
        raise EvaluationInputError("retrieval schema_version must be 1.0.")
    required_text(retrieval, "retrieval_id")
    _required_choice(
        retrieval,
        "status",
        {"completed", "no_results", "failed"},
        label="retrieval status",
    )
    _required_object_list(retrieval.get("results"), "retrieval results")
    retrieval_query = _mapping(retrieval.get("query"))
    if required_text(retrieval_query, "text") != required_text(request, "question"):
        raise EvaluationInputError("retrieval question does not match pipeline.")
    answer: dict[str, Any] | None = None
    answer_ref = pipeline.get("answer")
    if answer_ref is not None:
        if not isinstance(answer_ref, dict):
            raise EvaluationInputError("pipeline answer reference is invalid.")
        required_text(answer_ref, "artifact_id")
        answer = load_json_object(_artifact_path(answer_ref), "answer artifact")
        if answer.get("schema_version") != "1.0":
            raise EvaluationInputError("answer schema_version must be 1.0.")
        required_text(answer, "answer_id")
        required_text(answer, "question")
        required_text(answer, "retrieval_id")
        _required_choice(
            answer,
            "status",
            {"answered", "insufficient_evidence", "failed"},
            label="answer status",
        )
        for field_name in ("evidence", "claims", "citations"):
            _required_object_list(answer.get(field_name), f"answer {field_name}")
    return PipelineBundle(
        path=path,
        pipeline=pipeline,
        retrieval=retrieval,
        answer=answer,
    )


def validate_bundle_for_case(bundle: PipelineBundle, case: EvaluationCase) -> None:
    """Verify the pipeline and answer artifacts belong to the evaluation case."""

    if bundle.question != case.question:
        raise EvaluationInputError("pipeline question does not match evaluation case.")
    if bundle.retrieval.get("retrieval_id") != bundle.retrieval_id:
        raise EvaluationInputError("pipeline retrieval ID does not match artifact.")
    if bundle.answer is not None:
        if bundle.answer.get("answer_id") != bundle.answer_id:
            raise EvaluationInputError("pipeline answer ID does not match artifact.")
        if bundle.answer.get("retrieval_id") != bundle.retrieval_id:
            raise EvaluationInputError("answer retrieval ID does not match pipeline.")
        if bundle.answer.get("question") != case.question:
            raise EvaluationInputError("answer question does not match evaluation case.")


def compute_configuration_fingerprint(configuration: dict[str, Any]) -> str:
    canonical = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _artifact_path(reference: dict[str, Any]) -> Path:
    value = reference.get("path")
    if not isinstance(value, str) or not value.strip():
        raise EvaluationInputError("artifact reference path must be a string.")
    path = Path(value)
    if not path.is_file():
        raise EvaluationInputError(f"artifact not found: {path}")
    return path


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _required_object_list(value: object, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise EvaluationInputError(f"{field_name} must be a list of objects.")
    return value


def _required_choice(
    payload: dict[str, Any],
    field_name: str,
    allowed: set[str],
    *,
    label: str,
) -> str:
    value = required_text(payload, field_name)
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise EvaluationInputError(f"{label} must be one of: {choices}.")
    return value


def _failed_case_result(case: EvaluationCase, error: str) -> CaseEvaluation:
    return CaseEvaluation(
        case_id=case.case_id,
        rubric_version=case.rubric_version,
        pipeline_id="pipeline-unavailable",
        retrieval_id=None,
        answer_id=None,
        configuration_fingerprint="unavailable",
        metrics=(),
        diagnosis=FailureDiagnosis(
            failure_codes=("stage_failure",),
            affected_stage="evaluation",
            intervention="case_or_rubric",
            notes=error,
        ),
        latency_ms=0,
        usage={},
    )
