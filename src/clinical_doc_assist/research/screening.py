"""Deterministic candidate screening for the research agent."""

from __future__ import annotations

import re
from collections.abc import Sequence

from clinical_doc_assist.research.models import (
    DiscoveryRequest,
    ModelDecision,
    ReasonCode,
    ResearchCandidate,
    ScreeningDecision,
    ScreeningResult,
)

NCT_ID_PATTERN = re.compile(r"^NCT\d{8}$")
APPROVED_STUDY_PREFIX = "https://clinicaltrials.gov/study/"


def screen_candidates(
    candidates: Sequence[ResearchCandidate],
    request: DiscoveryRequest,
    model_decisions: Sequence[ModelDecision],
) -> ScreeningResult:
    """Apply deterministic checks and merge advisory model decisions."""

    decisions = {decision.nct_id: decision for decision in model_decisions}
    seen_identifiers: dict[str, str] = {}
    accepted: list[ScreeningDecision] = []
    rejected: list[ScreeningDecision] = []
    needs_review: list[ScreeningDecision] = []

    for candidate in candidates:
        reasons: list[ReasonCode] = []
        duplicate_of = _duplicate_of(candidate, seen_identifiers)

        if not _valid_identifier(candidate.nct_id):
            reasons.append("missing_identifier")
        if not candidate.title.strip():
            reasons.append("ambiguous_metadata")
        if candidate.source_type != "trial_registry" or not candidate.source_url.startswith(
            APPROVED_STUDY_PREFIX
        ):
            reasons.append("unapproved_source")

        if candidate.updated_date is None:
            reasons.append("invalid_date")
        elif not request.updated_after <= candidate.updated_date <= request.updated_before:
            reasons.append("outside_date_window")

        if duplicate_of is not None:
            reasons.append("duplicate")

        if reasons:
            rejected.append(
                ScreeningDecision(
                    candidate=candidate,
                    status="rejected",
                    reason_codes=tuple(dict.fromkeys(reasons)),
                    duplicate_of=duplicate_of,
                )
            )
            continue

        model_decision = decisions.get(candidate.nct_id or "")
        if model_decision is None:
            needs_review.append(
                ScreeningDecision(
                    candidate=candidate,
                    status="needs_review",
                    reason_codes=("missing_reflection",),
                )
            )
        elif model_decision.status == "accepted":
            accepted.append(
                ScreeningDecision(
                    candidate=candidate,
                    status="accepted",
                    reason_codes=(
                        "approved_source",
                        "within_date_window",
                        "unique_identifier",
                        "relevant_topic",
                    ),
                )
            )
        elif model_decision.status == "rejected":
            rejected.append(
                ScreeningDecision(
                    candidate=candidate,
                    status="rejected",
                    reason_codes=model_decision.reason_codes or ("off_topic",),
                )
            )
        else:
            needs_review.append(
                ScreeningDecision(
                    candidate=candidate,
                    status="needs_review",
                    reason_codes=model_decision.reason_codes or ("ambiguous_metadata",),
                )
            )

    return ScreeningResult(
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        needs_review=tuple(needs_review),
    )


def _valid_identifier(value: str | None) -> bool:
    return bool(value and NCT_ID_PATTERN.fullmatch(value))


def _duplicate_of(
    candidate: ResearchCandidate,
    seen_identifiers: dict[str, str],
) -> str | None:
    if not _valid_identifier(candidate.nct_id):
        return None

    assert candidate.nct_id is not None
    original = seen_identifiers.get(candidate.nct_id)
    if original is None:
        seen_identifiers[candidate.nct_id] = candidate.nct_id
    return original
