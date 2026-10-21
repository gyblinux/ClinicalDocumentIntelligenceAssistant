from __future__ import annotations

from datetime import date

import pytest

from clinical_doc_assist.research.models import (
    DiscoveryRequest,
    DiscoveryRun,
    ResearchCandidate,
    ScreeningDecision,
    ToolResult,
)


def _candidate() -> ResearchCandidate:
    return ResearchCandidate(
        nct_id="NCT12345678",
        title="Example trial",
        source_url="https://clinicaltrials.gov/study/NCT12345678",
        source_type="trial_registry",
        updated_date=date(2026, 1, 15),
        first_posted_date=date(2025, 1, 1),
        status="COMPLETED",
        study_type="INTERVENTIONAL",
        sponsor="Example Sponsor",
        evidence_snippet="Example evidence.",
    )


def test_request_normalizes_topic_and_serializes_dates() -> None:
    request = DiscoveryRequest(
        topic="  GLP-1 outcomes  ",
        updated_after=date(2023, 1, 1),
        updated_before=date(2026, 10, 21),
    )

    assert request.topic == "GLP-1 outcomes"
    assert request.to_dict() == {
        "topic": "GLP-1 outcomes",
        "updated_after": "2023-01-01",
        "updated_before": "2026-10-21",
        "limit": 5,
    }


@pytest.mark.parametrize(
    ("topic", "after", "before", "limit", "message"),
    [
        ("", date(2023, 1, 1), date(2026, 1, 1), 5, "topic"),
        ("x" * 501, date(2023, 1, 1), date(2026, 1, 1), 5, "500"),
        ("topic", date(2026, 1, 2), date(2026, 1, 1), 5, "before"),
        ("topic", date(2023, 1, 1), date(2026, 1, 1), 0, "limit"),
        ("topic", date(2023, 1, 1), date(2026, 1, 1), 21, "limit"),
    ],
)
def test_request_rejects_invalid_values(
    topic: str,
    after: date,
    before: date,
    limit: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        DiscoveryRequest(topic, after, before, limit)


def test_run_serializes_candidate_and_screening_decisions() -> None:
    request = DiscoveryRequest("trial", date(2023, 1, 1), date(2026, 1, 1), 1)
    candidate = _candidate()
    decision = ScreeningDecision(
        candidate=candidate,
        status="accepted",
        reason_codes=("approved_source", "relevant_topic"),
    )
    run = DiscoveryRun(
        status="completed",
        request=request,
        current_time="2026-10-21T07:30:00Z",
        searches=(),
        accepted=(decision,),
        rejected=(),
        needs_review=(),
        errors=(),
    )

    payload = run.to_dict()

    assert payload["status"] == "completed"
    assert payload["request"]["topic"] == "trial"
    assert payload["accepted"][0]["candidate"]["nct_id"] == "NCT12345678"
    assert payload["accepted"][0]["candidate"]["updated_date"] == "2026-01-15"


def test_tool_result_serializes_success_and_failure() -> None:
    assert ToolResult.success({"count": 1}).to_dict() == {
        "ok": True,
        "result": {"count": 1},
    }
    assert ToolResult.failure("missing clock").to_dict() == {
        "ok": False,
        "error": "missing clock",
    }
