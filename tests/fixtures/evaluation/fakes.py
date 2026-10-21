"""Deterministic evaluation artifacts for tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clinical_doc_assist.evaluation.models import EvaluationCase
from clinical_doc_assist.orchestration.models import PipelineOutcome


def write_pipeline_bundle(
    root: Path,
    case: EvaluationCase,
    *,
    answer_status: str | None = None,
    include_expected: bool = True,
    claim_text: str | None = None,
    citations: bool = True,
) -> Path:
    """Write one internally linked pipeline/retrieval/answer fixture."""

    slug = case.case_id.replace("/", "-")
    artifact_dir = root / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    retrieval_id = f"retrieval-{slug}"
    answer_id = f"answer-{slug}"
    pipeline_id = f"pipeline-{slug}"
    status = answer_status or (
        "answered" if case.answerability == "answerable" else "insufficient_evidence"
    )
    chunk_id = (
        case.expected_evidence_ids[0]
        if include_expected and case.expected_evidence_ids
        else f"chunk-other-{slug}"
    )
    result = {
        "rank": 1,
        "score": 0.9,
        "chunk_id": chunk_id,
        "document_id": f"doc-{slug}",
        "nct_id": "NCT07424430",
        "section": "summary",
        "text": "Public study evidence.",
        "source_url": "https://clinicaltrials.gov/study/NCT07424430",
        "content_hash": "a" * 64,
    }
    results = [result]
    retrieval = {
        "schema_version": "1.0",
        "retrieval_id": retrieval_id,
        "created_at": "2026-10-21T12:00:00Z",
        "query": {
            "text": case.question,
            "collection": "clinical_evidence_v1",
            "limit": 5,
        },
        "tei_model": "BAAI/bge-small-en-v1.5",
        "collection": "clinical_evidence_v1",
        "results": results,
        "status": "completed",
        "errors": [],
    }

    claims: list[dict[str, Any]] = []
    answer_citations: list[dict[str, Any]] = []
    evidence = results
    if status == "answered":
        text = claim_text or (
            "The evidence reports "
            + "; ".join(case.required_key_points)
            + "."
            if case.required_key_points
            else "The evidence reports the answer."
        )
        citation_ids = [chunk_id] if citations else []
        claims = [
            {
                "claim_id": "claim-1",
                "text": text,
                "citation_ids": citation_ids,
            }
        ]
        if citations:
            answer_citations = [
                {
                    "citation_id": chunk_id,
                    "source_type": "retrieval_evidence",
                    "nct_id": "NCT07424430",
                    "section": "summary",
                    "source_url": "https://clinicaltrials.gov/study/NCT07424430",
                    "content_hash": "a" * 64,
                    "lookup_id": None,
                }
            ]
    elif status == "insufficient_evidence":
        evidence = []
        results = []
        retrieval["results"] = []
        retrieval["status"] = "no_results"

    answer = {
        "schema_version": "1.0",
        "answer_id": answer_id,
        "created_at": "2026-10-21T12:00:03Z",
        "status": status,
        "question": case.question,
        "retrieval_id": retrieval_id,
        "retrieval_created_at": "2026-10-21T12:00:00Z",
        "evidence": evidence,
        "model": {
            "provider": "test",
            "model": "fixture-model",
            "prompt_version": "answering-v1",
            "max_model_turns": 2,
            "max_tool_calls": 3,
            "max_evidence_items": 10,
            "max_output_tokens": 1600,
            "max_claims": 10,
        },
        "claims": claims,
        "reason": "Evidence is insufficient." if status == "insufficient_evidence" else None,
        "model_output": json.dumps({"status": status}),
        "citations": answer_citations,
        "tool_calls": [],
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "estimated_cost": None,
        },
        "latency_ms": 1000,
        "errors": ["fixture failure"] if status == "failed" else [],
        "disclaimer": "Research summary only.",
    }
    configuration = {
        "collection": "clinical_evidence_v1",
        "limit": 5,
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "embedding_dimension": 384,
        "answer_model": "fixture-model",
        "prompt_version": "answering-v1",
    }
    pipeline = {
        "schema_version": "1.0",
        "pipeline_id": pipeline_id,
        "created_at": "2026-10-21T12:00:04Z",
        "status": status,
        "request": {
            "question": case.question,
            "collection": "clinical_evidence_v1",
            "limit": 5,
        },
        "configuration": configuration,
        "retrieval": {
            "artifact_id": retrieval_id,
            "path": "",
            "status": "no_results" if not results else "completed",
        },
        "answer": {
            "artifact_id": answer_id,
            "path": "",
            "status": status,
        },
        "answer_summary": {
            "answer_id": answer_id,
            "status": status,
            "claims": claims,
            "reason": answer["reason"],
            "citation_ids": [item["citation_id"] for item in answer_citations],
        },
        "timing": {"retrieval_ms": 500, "answer_ms": 1000, "total_ms": 1500},
        "errors": list(answer["errors"]),
    }

    retrieval_path = artifact_dir / f"{retrieval_id}.json"
    answer_path = artifact_dir / f"{answer_id}.json"
    pipeline_path = artifact_dir / f"{pipeline_id}.json"
    pipeline["retrieval"]["path"] = retrieval_path.resolve().as_posix()
    pipeline["answer"]["path"] = answer_path.resolve().as_posix()
    retrieval_path.write_text(json.dumps(retrieval), encoding="utf-8")
    answer_path.write_text(json.dumps(answer), encoding="utf-8")
    pipeline_path.write_text(json.dumps(pipeline), encoding="utf-8")
    return pipeline_path


class FakeOrchestrator:
    def __init__(self, outcomes: list[PipelineOutcome]) -> None:
        self._outcomes = list(outcomes)
        self.requests = []

    def ask(self, request) -> PipelineOutcome:
        self.requests.append(request)
        if not self._outcomes:
            raise AssertionError("fake orchestrator has no queued outcome.")
        return self._outcomes.pop(0)


def write_evaluation_report(path: Path, **overrides: Any) -> Path:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "evaluation_id": "evaluation-fixture",
        "created_at": "2026-10-21T13:00:00Z",
        "set_version": "evaluation-fixture-v1",
        "mode": "saved",
        "rubric_versions": ["rag-rubric-v1"],
        "configuration": {
            "collection": "clinical_evidence_v1",
            "limit": 5,
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "embedding_dimension": 384,
            "answer_model": "fixture-model",
            "prompt_version": "answering-v1",
        },
        "configuration_fingerprint": "sha256:fixture",
        "cases": [
            {
                "case_id": "case-001",
                "rubric_version": "rag-rubric-v1",
                "pipeline_id": "pipeline-case-001",
                "retrieval_id": "retrieval-case-001",
                "answer_id": "answer-case-001",
                "configuration_fingerprint": "sha256:fixture",
                "metrics": [],
                "diagnosis": {
                    "failure_codes": [],
                    "affected_stage": "none",
                    "intervention": "none",
                    "notes": None,
                },
                "latency_ms": 1500,
                "usage": {"estimated_cost": 0.0},
            }
        ],
        "aggregates": [
            {"name": "citation_validity", "value": 1.0, "passed": None, "details": None}
        ],
        "errors": [],
    }
    payload.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def now() -> datetime:
    return datetime(2026, 10, 21, 13, 0, tzinfo=UTC)
