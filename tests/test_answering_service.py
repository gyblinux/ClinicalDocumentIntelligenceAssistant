from __future__ import annotations

import json
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

import pytest

from clinical_doc_assist.answering.models import (
    AgentResult,
    AnswerConfig,
    AnsweringInputError,
    AnsweringOutputError,
    EvidenceItem,
    MetadataLookup,
    ModelUsage,
)
from clinical_doc_assist.answering.service import AnswerService, load_retrieval_input
from tests.fixtures.answering.fakes import usage

FIXTURES = Path(__file__).parent / "fixtures" / "answering"


class FakeAgent:
    def __init__(self, result: AgentResult) -> None:
        self.result = result
        self.calls: list[tuple[str, tuple[EvidenceItem, ...]]] = []

    def run(
        self,
        question: str,
        evidence: tuple[EvidenceItem, ...],
    ) -> AgentResult:
        self.calls.append((question, evidence))
        return self.result


class FakeAgentFactory:
    def __init__(self, agent: FakeAgent | None = None) -> None:
        self.agent = agent
        self.allowed_nct_ids: list[frozenset[str]] = []

    def __call__(self, allowed_nct_ids: frozenset[str]) -> FakeAgent:
        self.allowed_nct_ids.append(allowed_nct_ids)
        if self.agent is None:
            raise AssertionError("agent should not be created for this run.")
        return self.agent


def fixed_now() -> datetime:
    return datetime(2026, 10, 21, 12, 0, 8, tzinfo=UTC)


def make_service(
    tmp_path: Path,
    *,
    content: str | None,
    tool_calls: tuple[MetadataLookup, ...] = (),
    error: str | None = None,
) -> tuple[AnswerService, FakeAgentFactory]:
    agent = FakeAgent(
        AgentResult(
            content=content,
            usage=usage(),
            tool_calls=tool_calls,
            error=error,
        )
    )
    factory = FakeAgentFactory(agent)
    service = AnswerService(
        config=AnswerConfig(provider="deepseek", model="deepseek-flash"),
        agent_factory=factory,
        output_dir=tmp_path / "answers",
        now=fixed_now,
        monotonic=count(10.0, 0.25).__next__,
        id_factory=lambda: "0123456789abcdef",
    )
    return service, factory


def supported_content(chunk_id: str = "chunk-1") -> str:
    return json.dumps(
        {
            "status": "answered",
            "claims": [
                {
                    "text": "The study evaluates semaglutide outcomes.",
                    "citation_ids": [chunk_id],
                }
            ],
        }
    )


def test_load_retrieval_input_inherits_question_and_evidence() -> None:
    source = load_retrieval_input(FIXTURES / "retrieval-supported.json")

    assert source.question == "What did NCT07424430 aim to evaluate?"
    assert source.retrieval_id == "retrieval-fixture-supported"
    assert len(source.evidence) == 2
    assert source.nct_ids == frozenset({"NCT07424430", "NCT00000002"})


def test_service_persists_supported_answer_without_retrieval_services(
    tmp_path: Path,
) -> None:
    service, factory = make_service(
        tmp_path,
        content=supported_content("chunk-7f7563be8042d8cdfa51a2fa"),
    )

    outcome = service.answer(FIXTURES / "retrieval-supported.json")

    assert outcome.run.status == "answered"
    assert outcome.run.usage.total_tokens == 120
    assert outcome.run.latency_ms == 250
    assert outcome.run.citations[0].source_url == (
        "https://clinicaltrials.gov/study/NCT07424430"
    )
    assert outcome.run.retrieval_id == "retrieval-fixture-supported"
    assert outcome.path == tmp_path / "answers" / "answer-0123456789abcdef.json"
    assert factory.agent is not None
    assert factory.agent.calls[0][0] == "What did NCT07424430 aim to evaluate?"
    assert factory.allowed_nct_ids == [
        frozenset({"NCT07424430", "NCT00000002"})
    ]
    assert json.loads(outcome.path.read_text(encoding="utf-8"))["status"] == "answered"


def test_answer_record_contains_complete_feature_006_handoff(tmp_path: Path) -> None:
    service, _ = make_service(
        tmp_path,
        content=supported_content("chunk-7f7563be8042d8cdfa51a2fa"),
    )

    outcome = service.answer(FIXTURES / "retrieval-supported.json")
    payload = outcome.run.to_dict()

    assert payload["schema_version"] == "1.0"
    assert payload["answer_id"] == "answer-0123456789abcdef"
    assert payload["retrieval_id"] == "retrieval-fixture-supported"
    assert payload["question"] == "What did NCT07424430 aim to evaluate?"
    assert payload["evidence"][0]["chunk_id"] == "chunk-7f7563be8042d8cdfa51a2fa"
    assert payload["model"]["prompt_version"] == "answering-v1"
    assert payload["claims"][0]["citation_ids"] == [
        "chunk-7f7563be8042d8cdfa51a2fa"
    ]
    assert payload["citations"][0]["source_url"] == (
        "https://clinicaltrials.gov/study/NCT07424430"
    )
    assert payload["usage"]["total_tokens"] == 120
    assert payload["latency_ms"] == 250
    assert payload["model_output"] is not None
    assert payload["disclaimer"]


def test_no_results_abstains_without_creating_agent(tmp_path: Path) -> None:
    factory = FakeAgentFactory()
    service = AnswerService(
        config=AnswerConfig(provider="deepseek", model="deepseek-flash"),
        agent_factory=factory,
        output_dir=tmp_path / "answers",
        now=fixed_now,
        monotonic=iter([1.0, 1.01]).__next__,
        id_factory=lambda: "0123456789abcdef",
    )

    outcome = service.answer(FIXTURES / "retrieval-no-results.json")

    assert outcome.run.status == "insufficient_evidence"
    assert outcome.run.claims == ()
    assert outcome.run.reason == "The retrieval run contained no evidence."
    assert outcome.run.usage == ModelUsage()
    assert outcome.run.model_output is None
    assert factory.allowed_nct_ids == []
    assert outcome.exit_code == 0


def test_model_declared_insufficient_evidence_is_persisted(tmp_path: Path) -> None:
    service, _ = make_service(
        tmp_path,
        content='{"status":"insufficient_evidence","reason":"No outcome data."}',
    )

    outcome = service.answer(FIXTURES / "retrieval-supported.json")

    assert outcome.run.status == "insufficient_evidence"
    assert outcome.run.reason == "No outcome data."
    assert outcome.run.claims == ()


def test_agent_error_creates_failed_record(tmp_path: Path) -> None:
    service, _ = make_service(
        tmp_path,
        content=None,
        error="provider unavailable",
    )

    outcome = service.answer(FIXTURES / "retrieval-supported.json")

    assert outcome.run.status == "failed"
    assert outcome.run.errors == ("provider unavailable",)
    assert outcome.exit_code == 1


def test_malformed_model_response_creates_failed_record(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path, content="not-json")

    outcome = service.answer(FIXTURES / "retrieval-supported.json")

    assert outcome.run.status == "failed"
    assert "valid JSON" in outcome.run.errors[0]
    assert outcome.run.claims == ()
    assert outcome.run.model_output == "not-json"


def test_unknown_citation_creates_failed_record_without_partial_claims(
    tmp_path: Path,
) -> None:
    service, _ = make_service(tmp_path, content=supported_content("chunk-unknown"))

    outcome = service.answer(FIXTURES / "retrieval-supported.json")

    assert outcome.run.status == "failed"
    assert outcome.run.claims == ()
    assert "does not match" in outcome.run.errors[0]


def test_metadata_lookup_is_persisted_and_cited(tmp_path: Path) -> None:
    lookup = MetadataLookup(
        lookup_id="lookup-1",
        nct_id="NCT07424430",
        requested_at=fixed_now(),
        status="completed",
        data={"overall_status": "RECRUITING"},
    )
    content = json.dumps(
        {
            "status": "answered",
            "claims": [
                {
                    "text": "The trial is recruiting.",
                    "citation_ids": ["trial-metadata:NCT07424430"],
                }
            ],
        }
    )
    service, _ = make_service(
        tmp_path,
        content=content,
        tool_calls=(lookup,),
    )

    outcome = service.answer(FIXTURES / "retrieval-supported.json")

    assert outcome.run.citations[0].source_type == "trial_metadata"
    assert outcome.run.tool_calls[0].lookup_id == "lookup-1"


def test_existing_explicit_output_fails_before_model_call(tmp_path: Path) -> None:
    service, factory = make_service(tmp_path, content=supported_content())
    output = tmp_path / "existing.json"
    output.write_text("keep", encoding="utf-8")

    with pytest.raises(AnsweringInputError, match="already exists"):
        service.answer(FIXTURES / "retrieval-supported.json", output=output)

    assert factory.agent is not None
    assert factory.agent.calls == []


def test_existing_default_output_fails_before_second_model_call(
    tmp_path: Path,
) -> None:
    service, factory = make_service(tmp_path, content=supported_content())
    fixture = FIXTURES / "retrieval-supported.json"
    service.answer(fixture)

    with pytest.raises(AnsweringOutputError, match="already exists"):
        service.answer(fixture)

    assert factory.agent is not None
    assert len(factory.agent.calls) == 1


def test_malformed_retrieval_json_is_an_input_error(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")

    with pytest.raises(AnsweringInputError, match="not valid JSON"):
        load_retrieval_input(malformed)


def test_failed_retrieval_status_is_rejected(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "retrieval-supported.json").read_text())
    payload["status"] = "failed"
    failed = tmp_path / "failed.json"
    failed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AnsweringInputError, match="status is failed"):
        load_retrieval_input(failed)


def test_completed_retrieval_with_no_results_is_rejected(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "retrieval-supported.json").read_text())
    payload["results"] = []
    empty = tmp_path / "empty-completed.json"
    empty.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AnsweringInputError, match="completed retrieval"):
        load_retrieval_input(empty)


def test_retrieval_with_more_than_ten_results_is_rejected(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "retrieval-supported.json").read_text())
    template = payload["results"][0]
    payload["results"] = [
        {
            **template,
            "rank": rank,
            "chunk_id": f"chunk-{rank}",
        }
        for rank in range(1, 12)
    ]
    oversized = tmp_path / "oversized.json"
    oversized.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AnsweringInputError, match="cannot exceed 10"):
        load_retrieval_input(oversized)
