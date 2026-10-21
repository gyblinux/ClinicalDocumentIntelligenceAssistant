"""Strict parsing and validation for evidence-grounded model citations."""

from __future__ import annotations

import json
from dataclasses import dataclass

from clinical_doc_assist.answering.models import (
    MAX_CLAIMS,
    METADATA_CITATION_PATTERN,
    AnswerCitation,
    AnswerClaim,
    AnsweringResponseError,
    CitationValidationError,
    EvidenceItem,
    MetadataLookup,
    ModelClaim,
    ModelResponse,
)


@dataclass(frozen=True, slots=True)
class ResolvedCitations:
    claims: tuple[AnswerClaim, ...]
    citations: tuple[AnswerCitation, ...]


def parse_model_response(content: str | None) -> ModelResponse:
    """Parse the model's final JSON response without accepting loose prose."""

    if not isinstance(content, str) or not content.strip():
        raise AnsweringResponseError("model response content is empty.")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AnsweringResponseError("model response is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise AnsweringResponseError("model response must be a JSON object.")

    status = payload.get("status")
    if status == "answered":
        raw_claims = payload.get("claims")
        if not isinstance(raw_claims, list) or not raw_claims:
            raise AnsweringResponseError(
                "answered response must contain a non-empty claims list."
            )
        if len(raw_claims) > MAX_CLAIMS:
            raise AnsweringResponseError(
                f"answered response cannot exceed {MAX_CLAIMS} claims."
            )
        claims = tuple(_model_claim(item) for item in raw_claims)
        try:
            return ModelResponse(status="answered", claims=claims)
        except ValueError as exc:
            raise AnsweringResponseError(str(exc)) from exc

    if status == "insufficient_evidence":
        raw_claims = payload.get("claims")
        if raw_claims not in (None, []):
            raise AnsweringResponseError(
                "insufficient_evidence response cannot contain claims."
            )
        reason = payload.get("reason")
        try:
            return ModelResponse(
                status="insufficient_evidence",
                reason=reason if isinstance(reason, str) else None,
            )
        except ValueError as exc:
            raise AnsweringResponseError(str(exc)) from exc

    raise AnsweringResponseError(f"model response has unknown status: {status!r}.")


def resolve_citations(
    response: ModelResponse,
    evidence: tuple[EvidenceItem, ...],
    lookups: tuple[MetadataLookup, ...],
) -> ResolvedCitations:
    """Resolve model citation IDs to canonical retrieval or metadata provenance."""

    if response.status == "insufficient_evidence":
        return ResolvedCitations(claims=(), citations=())

    evidence_by_id = {item.chunk_id: item for item in evidence}
    evidence_nct_ids = {item.nct_id for item in evidence}
    metadata_by_id = {
        lookup.citation_id: lookup
        for lookup in lookups
        if lookup.status == "completed" and lookup.nct_id in evidence_nct_ids
    }

    answer_claims: list[AnswerClaim] = []
    citations_by_id: dict[str, AnswerCitation] = {}
    for index, model_claim in enumerate(response.claims, start=1):
        resolved_ids: list[str] = []
        for citation_id in model_claim.citation_ids:
            citation = _resolve_citation(
                citation_id,
                evidence_by_id=evidence_by_id,
                metadata_by_id=metadata_by_id,
            )
            resolved_ids.append(citation.citation_id)
            citations_by_id.setdefault(citation.citation_id, citation)

        answer_claims.append(
            AnswerClaim(
                claim_id=f"claim-{index}",
                text=model_claim.text,
                citation_ids=tuple(resolved_ids),
            )
        )

    return ResolvedCitations(
        claims=tuple(answer_claims),
        citations=tuple(citations_by_id.values()),
    )


def _model_claim(value: object) -> ModelClaim:
    if not isinstance(value, dict):
        raise AnsweringResponseError("each model claim must be an object.")
    text = value.get("text")
    citation_ids = value.get("citation_ids")
    if not isinstance(text, str):
        raise AnsweringResponseError("model claim text must be a string.")
    if not isinstance(citation_ids, list) or not all(
        isinstance(item, str) for item in citation_ids
    ):
        raise AnsweringResponseError("model claim citation_ids must be a string list.")
    try:
        return ModelClaim(text=text, citation_ids=tuple(citation_ids))
    except ValueError as exc:
        raise AnsweringResponseError(str(exc)) from exc


def _resolve_citation(
    citation_id: str,
    *,
    evidence_by_id: dict[str, EvidenceItem],
    metadata_by_id: dict[str, MetadataLookup],
) -> AnswerCitation:
    evidence = evidence_by_id.get(citation_id)
    if evidence is not None:
        return AnswerCitation(
            citation_id=evidence.chunk_id,
            source_type="retrieval_evidence",
            nct_id=evidence.nct_id,
            section=evidence.section,
            source_url=evidence.source_url,
            content_hash=evidence.content_hash,
        )

    metadata_match = METADATA_CITATION_PATTERN.fullmatch(citation_id)
    if metadata_match is not None:
        lookup = metadata_by_id.get(citation_id)
        if lookup is None:
            raise CitationValidationError(
                f"citation {citation_id} has no successful metadata lookup."
            )
        return AnswerCitation(
            citation_id=citation_id,
            source_type="trial_metadata",
            nct_id=lookup.nct_id,
            section=None,
            source_url=f"https://clinicaltrials.gov/study/{lookup.nct_id}",
            content_hash=None,
            lookup_id=lookup.lookup_id,
        )

    raise CitationValidationError(
        f"citation {citation_id!r} does not match retrieved evidence or metadata."
    )
