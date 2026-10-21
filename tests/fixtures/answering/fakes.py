"""Reusable fakes for answering-stage tests."""

from __future__ import annotations

from typing import Any

from clinical_doc_assist.answering.agent import ChatModel
from clinical_doc_assist.answering.models import ModelTurn, ModelUsage
from clinical_doc_assist.answering.tools import TrialMetadataSource
from clinical_doc_assist.research.models import SourceError


class FakeChatModel(ChatModel):
    def __init__(self, *turns: ModelTurn | Exception) -> None:
        self._turns = list(turns)
        self.calls: list[list[dict[str, Any]]] = []

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        del tools
        self.calls.append([dict(message) for message in messages])
        if not self._turns:
            raise AssertionError("fake model has no queued response.")
        turn = self._turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn


class FakeTrialSource(TrialMetadataSource):
    def __init__(self, studies: dict[str, dict[str, Any] | Exception]) -> None:
        self._studies = studies
        self.calls: list[str] = []

    def fetch_study(self, nct_id: str) -> dict[str, Any]:
        self.calls.append(nct_id)
        response = self._studies.get(nct_id)
        if response is None:
            raise SourceError(f"missing fake study: {nct_id}")
        if isinstance(response, Exception):
            raise response
        return response


def usage(
    *,
    input_tokens: int | None = 100,
    output_tokens: int | None = 20,
) -> ModelUsage:
    total = (
        input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else None
    )
    return ModelUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total,
    )


def trial_study(nct_id: str = "NCT07424430") -> dict[str, Any]:
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": nct_id,
                "briefTitle": "Semaglutide outcomes study",
            },
            "statusModule": {
                "overallStatus": "RECRUITING",
                "startDateStruct": {"date": "2026-01-01"},
                "primaryCompletionDateStruct": {"date": "2028-01-01"},
                "completionDateStruct": {"date": "2029-01-01"},
            },
            "designModule": {
                "studyType": "OBSERVATIONAL",
                "phases": ["NA"],
                "enrollmentInfo": {"count": 500, "enrollmentType": "ACTUAL"},
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Example Sponsor"}
            },
            "armsInterventionsModule": {
                "interventions": [{"name": "semaglutide", "type": "DRUG"}]
            },
        }
    }
