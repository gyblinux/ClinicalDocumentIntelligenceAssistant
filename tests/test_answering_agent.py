from __future__ import annotations

import json
from datetime import UTC, datetime

from clinical_doc_assist.answering.agent import AnswerAgent
from clinical_doc_assist.answering.models import (
    AnsweringModelError,
    EvidenceItem,
    ModelToolCall,
    ModelTurn,
)
from clinical_doc_assist.answering.tools import METADATA_TOOL_NAME, TrialMetadataTool
from tests.fixtures.answering.fakes import FakeChatModel, FakeTrialSource, trial_study, usage


def evidence() -> tuple[EvidenceItem, ...]:
    return (
        EvidenceItem(
            rank=1,
            score=0.9,
            chunk_id="chunk-1",
            document_id="doc-NCT07424430",
            nct_id="NCT07424430",
            section="summary",
            text="The study evaluates semaglutide outcomes.",
            source_url="https://clinicaltrials.gov/study/NCT07424430",
            content_hash="a" * 64,
        ),
    )


def fixed_now() -> datetime:
    return datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def make_agent(
    model: FakeChatModel,
    *,
    source: FakeTrialSource | None = None,
) -> AnswerAgent:
    return AnswerAgent(
        model=model,
        metadata_tool=TrialMetadataTool(
            source=source or FakeTrialSource({}),
            allowed_nct_ids=frozenset({"NCT07424430"}),
            now=fixed_now,
            id_factory=lambda: "lookup-1",
        ),
    )


def test_agent_returns_supported_content_and_usage() -> None:
    content = json.dumps(
        {
            "status": "answered",
            "claims": [{"text": "Supported.", "citation_ids": ["chunk-1"]}],
        }
    )
    model = FakeChatModel(ModelTurn(content=content, usage=usage()))

    result = make_agent(model).run("What is being evaluated?", evidence())

    assert result.error is None
    assert result.content == content
    assert result.usage.total_tokens == 120
    assert "chunk-1" in model.calls[0][1]["content"]
    assert "no more than 10" in model.calls[0][0]["content"]


def test_agent_returns_model_error_without_raising() -> None:
    model = FakeChatModel(AnsweringModelError("provider unavailable"))

    result = make_agent(model).run("Question", evidence())

    assert result.content is None
    assert result.error == "provider unavailable"


def test_agent_executes_metadata_tool_then_returns_final_content() -> None:
    source = FakeTrialSource({"NCT07424430": trial_study()})
    model = FakeChatModel(
        ModelTurn(
            content=None,
            tool_calls=(
                ModelToolCall(
                    call_id="call-1",
                    name=METADATA_TOOL_NAME,
                    arguments='{"nct_id":"NCT07424430"}',
                ),
            ),
            usage=usage(),
        ),
        ModelTurn(
            content=(
                '{"status":"answered","claims":[{"text":"Recruiting.",'
                '"citation_ids":["trial-metadata:NCT07424430"]}]}'
            ),
            usage=usage(),
        ),
    )

    result = make_agent(model, source=source).run("What is the status?", evidence())

    assert result.error is None
    assert result.tool_calls[0].status == "completed"
    assert source.calls == ["NCT07424430"]
    assert model.calls[1][-1]["role"] == "tool"
    assert result.usage.total_tokens == 240


def test_agent_rejects_unknown_tool() -> None:
    model = FakeChatModel(
        ModelTurn(
            content=None,
            tool_calls=(
                ModelToolCall(
                    call_id="call-1",
                    name="search_the_web",
                    arguments="{}",
                ),
            ),
        )
    )

    result = make_agent(model).run("Question", evidence())

    assert result.error is not None
    assert "unknown tool" in result.error


def test_agent_rejects_malformed_tool_arguments() -> None:
    model = FakeChatModel(
        ModelTurn(
            content=None,
            tool_calls=(
                ModelToolCall(
                    call_id="call-1",
                    name=METADATA_TOOL_NAME,
                    arguments="not-json",
                ),
            ),
        )
    )

    result = make_agent(model).run("Question", evidence())

    assert result.error is not None
    assert "nct_id" in result.error


def test_agent_rejects_tool_call_after_final_turn() -> None:
    source = FakeTrialSource({"NCT07424430": trial_study()})
    tool_call = ModelToolCall(
        call_id="call-1",
        name=METADATA_TOOL_NAME,
        arguments='{"nct_id":"NCT07424430"}',
    )
    model = FakeChatModel(
        ModelTurn(content=None, tool_calls=(tool_call,)),
        ModelTurn(content=None, tool_calls=(tool_call,)),
    )

    result = make_agent(model, source=source).run("Question", evidence())

    assert result.error is not None
    assert "final allowed turn" in result.error
    assert source.calls == ["NCT07424430"]


def test_agent_rejects_more_than_three_requested_lookups() -> None:
    source = FakeTrialSource({})
    calls = tuple(
        ModelToolCall(
            call_id=f"call-{index}",
            name=METADATA_TOOL_NAME,
            arguments='{"nct_id":"NCT07424430"}',
        )
        for index in range(4)
    )
    model = FakeChatModel(ModelTurn(content=None, tool_calls=calls))

    result = make_agent(model, source=source).run("Question", evidence())

    assert result.error is not None
    assert "lookup limit" in result.error
    assert source.calls == []
