from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from openai import OpenAIError

from clinical_doc_assist.research.agent import ResearchAgent
from clinical_doc_assist.research.models import (
    AgentError,
    ClockUnavailableError,
    DiscoveryRequest,
    ResearchCandidate,
    ScreeningStatus,
)


def _completion(
    *,
    content: str | None = None,
    tool_calls: list[Any] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))]
    )


def _tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _decision_content(
    nct_id: str = "NCT12345678",
    status: ScreeningStatus = "accepted",
) -> str:
    return json.dumps(
        {
            "decisions": [
                {
                    "nct_id": nct_id,
                    "status": status,
                    "reason_codes": ["relevant_topic"],
                }
            ]
        }
    )


@dataclass
class FakeCompletions:
    responses: list[SimpleNamespace]
    requests: list[dict[str, Any]]

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(copy.deepcopy(kwargs))
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.completions = FakeCompletions(responses=responses, requests=[])
        self.chat = SimpleNamespace(completions=self.completions)


class FailingCompletions:
    def create(self, **_: Any) -> SimpleNamespace:
        raise OpenAIError("provider down")


class FailingClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FailingCompletions())


class FakeSource:
    def __init__(self, candidates: list[ResearchCandidate]) -> None:
        self.candidates = candidates
        self.calls: list[tuple[DiscoveryRequest, str]] = []

    def search(
        self,
        request: DiscoveryRequest,
        *,
        query: str,
    ) -> list[ResearchCandidate]:
        self.calls.append((request, query))
        return list(self.candidates)


def _candidate(nct_id: str = "NCT12345678") -> ResearchCandidate:
    return ResearchCandidate(
        nct_id=nct_id,
        title="Example trial",
        source_url=f"https://clinicaltrials.gov/study/{nct_id}",
        source_type="trial_registry",
        updated_date=date(2025, 1, 1),
        first_posted_date=date(2024, 1, 1),
        status="COMPLETED",
        study_type="INTERVENTIONAL",
        sponsor="Sponsor",
        evidence_snippet="Evidence",
    )


def _request() -> DiscoveryRequest:
    return DiscoveryRequest(
        "diabetes",
        date(2023, 1, 1),
        date(2026, 10, 21),
        5,
    )


def _agent(client: FakeClient, source: FakeSource, *, max_steps: int = 6) -> ResearchAgent:
    return ResearchAgent(
        client=client,  # type: ignore[arg-type]
        model="test-model",
        source=source,
        now=lambda: datetime(2026, 10, 21, 7, 30, tzinfo=UTC),
        max_steps=max_steps,
    )


def test_agent_records_time_searches_and_returns_screening() -> None:
    client = FakeClient(
        [
            _completion(tool_calls=[_tool_call("clock", "get_current_datetime", {})]),
            _completion(
                tool_calls=[
                    _tool_call(
                        "search",
                        "search_clinical_trials",
                        {"query": "diabetes"},
                    )
                ]
            ),
            _completion(content=_decision_content()),
        ]
    )
    source = FakeSource([_candidate()])

    run = _agent(client, source).run(_request())

    assert run.status == "completed"
    assert run.current_time == "2026-10-21T07:30:00Z"
    assert run.accepted[0].candidate.nct_id == "NCT12345678"
    assert run.searches[0].result_count == 1
    assert len(source.calls) == 1


def test_search_is_blocked_until_clock_succeeds() -> None:
    client = FakeClient(
        [
            _completion(
                tool_calls=[
                    _tool_call(
                        "early-search",
                        "search_clinical_trials",
                        {"query": "diabetes"},
                    )
                ]
            ),
            _completion(tool_calls=[_tool_call("clock", "get_current_datetime", {})]),
            _completion(
                tool_calls=[
                    _tool_call(
                        "search",
                        "search_clinical_trials",
                        {"query": "diabetes"},
                    )
                ]
            ),
            _completion(content=_decision_content()),
        ]
    )
    source = FakeSource([_candidate()])

    _agent(client, source).run(_request())

    assert len(source.calls) == 1
    second_messages = client.completions.requests[1]["messages"]
    tool_payload = json.loads(second_messages[-1]["content"])
    assert tool_payload == {"ok": False, "error": "clock_required"}


def test_clock_failure_stops_without_search() -> None:
    client = FakeClient(
        [
            _completion(tool_calls=[_tool_call("clock", "get_current_datetime", {})]),
            _completion(content='{"decisions": []}'),
        ]
    )
    source = FakeSource([])
    agent = ResearchAgent(
        client=client,  # type: ignore[arg-type]
        model="test-model",
        source=source,
        now=lambda: (_ for _ in ()).throw(RuntimeError("clock unavailable")),
    )

    with pytest.raises(ClockUnavailableError, match="clock unavailable"):
        agent.run(_request())

    assert source.calls == []


def test_agent_rejects_malformed_final_json_and_exceeded_steps() -> None:
    malformed_client = FakeClient(
        [
            _completion(tool_calls=[_tool_call("clock", "get_current_datetime", {})]),
            _completion(content="not-json"),
        ]
    )
    with pytest.raises(AgentError, match="JSON"):
        _agent(malformed_client, FakeSource([])).run(_request())

    looping_client = FakeClient(
        [_completion(tool_calls=[_tool_call("clock-1", "get_current_datetime", {})])]
    )
    with pytest.raises(AgentError, match="step"):
        _agent(looping_client, FakeSource([]), max_steps=1).run(_request())


def test_agent_limits_unique_tool_results_to_requested_total() -> None:
    client = FakeClient(
        [
            _completion(tool_calls=[_tool_call("clock", "get_current_datetime", {})]),
            _completion(
                tool_calls=[
                    _tool_call(
                        "search",
                        "search_clinical_trials",
                        {"query": "diabetes"},
                    )
                ]
            ),
            _completion(content=_decision_content()),
        ]
    )
    source = FakeSource([_candidate(), _candidate("NCT87654321")])
    request = DiscoveryRequest(
        "diabetes",
        date(2023, 1, 1),
        date(2026, 10, 21),
        1,
    )

    run = _agent(client, source).run(request)

    screened = run.accepted + run.rejected + run.needs_review
    assert len(screened) == 1


def test_model_reason_codes_are_normalized_to_fixed_taxonomy() -> None:
    client = FakeClient(
        [
            _completion(tool_calls=[_tool_call("clock", "get_current_datetime", {})]),
            _completion(
                tool_calls=[
                    _tool_call(
                        "search",
                        "search_clinical_trials",
                        {"query": "diabetes"},
                    )
                ]
            ),
            _completion(
                content=json.dumps(
                    {
                        "decisions": [
                            {
                                "nct_id": "NCT12345678",
                                "status": "rejected",
                                "reason_codes": ["unexpected-model-reason"],
                            }
                        ]
                    }
                )
            ),
        ]
    )

    run = _agent(client, FakeSource([_candidate()])).run(_request())

    assert run.rejected[0].reason_codes == ("off_topic",)


def test_model_api_errors_are_wrapped_as_agent_errors() -> None:
    agent = ResearchAgent(
        client=FailingClient(),  # type: ignore[arg-type]
        model="test-model",
        source=FakeSource([]),
    )

    with pytest.raises(AgentError, match="provider down"):
        agent.run(_request())
