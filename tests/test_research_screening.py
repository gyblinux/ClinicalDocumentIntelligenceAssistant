from __future__ import annotations

from datetime import date

from clinical_doc_assist.research.models import (
    DiscoveryRequest,
    ModelDecision,
    ResearchCandidate,
)
from clinical_doc_assist.research.screening import screen_candidates

REQUEST = DiscoveryRequest(
    "diabetes",
    updated_after=date(2023, 1, 1),
    updated_before=date(2026, 10, 21),
    limit=10,
)


def _candidate(
    nct_id: str | None = "NCT12345678",
    *,
    updated: date | None = date(2025, 1, 1),
    title: str = "Diabetes trial",
    source_url: str | None = None,
    source_type: str = "trial_registry",
) -> ResearchCandidate:
    return ResearchCandidate(
        nct_id=nct_id,
        title=title,
        source_url=source_url or f"https://clinicaltrials.gov/study/{nct_id or 'missing'}",
        source_type=source_type,
        updated_date=updated,
        first_posted_date=date(2024, 1, 1),
        status="COMPLETED",
        study_type="INTERVENTIONAL",
        sponsor="Sponsor",
        evidence_snippet="Evidence",
    )


def test_accepts_valid_relevant_candidate() -> None:
    candidate = _candidate()
    decision = ModelDecision("NCT12345678", "accepted", ("relevant_topic",))

    result = screen_candidates([candidate], REQUEST, [decision])

    assert result.accepted[0].status == "accepted"
    assert result.accepted[0].reason_codes == (
        "approved_source",
        "within_date_window",
        "unique_identifier",
        "relevant_topic",
    )


def test_reflection_can_reject_off_topic_candidate() -> None:
    decision = ModelDecision("NCT12345678", "rejected", ("off_topic",))

    result = screen_candidates([_candidate()], REQUEST, [decision])

    assert result.rejected[0].reason_codes == ("off_topic",)


def test_missing_reflection_needs_review() -> None:
    result = screen_candidates([_candidate()], REQUEST, [])

    assert result.needs_review[0].reason_codes == ("missing_reflection",)


def test_deterministic_checks_reject_bad_metadata_and_dates() -> None:
    candidates = [
        _candidate(None),
        _candidate("NCT87654321", updated=None),
        _candidate("NCT11111111", updated=date(2021, 1, 1)),
        _candidate(
            "NCT22222222",
            source_url="https://example.test/NCT22222222",
        ),
        _candidate("NCT33333333", title=""),
    ]
    decisions = [
        ModelDecision("NCT87654321", "accepted", ()),
        ModelDecision("NCT11111111", "accepted", ()),
        ModelDecision("NCT22222222", "accepted", ()),
        ModelDecision("NCT33333333", "accepted", ()),
    ]

    result = screen_candidates(candidates, REQUEST, decisions)
    reasons = {item.candidate.nct_id: item.reason_codes for item in result.rejected}

    assert reasons[None] == ("missing_identifier",)
    assert reasons["NCT87654321"] == ("invalid_date",)
    assert reasons["NCT11111111"] == ("outside_date_window",)
    assert reasons["NCT22222222"] == ("unapproved_source",)
    assert reasons["NCT33333333"] == ("ambiguous_metadata",)


def test_duplicate_is_rejected_and_points_to_original() -> None:
    first = _candidate()
    duplicate = _candidate(title="Duplicate record")
    decision = ModelDecision("NCT12345678", "accepted", ("relevant_topic",))

    result = screen_candidates([first, duplicate], REQUEST, [decision])

    assert len(result.accepted) == 1
    assert result.rejected[0].reason_codes == ("duplicate",)
    assert result.rejected[0].duplicate_of == "NCT12345678"
