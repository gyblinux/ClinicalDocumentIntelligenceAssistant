"""Deterministic fakes and records for orchestration tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from clinical_doc_assist.answering.models import (
    AnswerCitation,
    AnswerClaim,
    AnswerConfig,
    AnswerOutcome,
    AnswerRun,
    EvidenceItem,
    ModelUsage,
)
from clinical_doc_assist.retrieval.models import (
    RetrievalQuery,
    RetrievalResult,
    RetrievalRun,
)

QUESTION = "What did NCT07424430 aim to evaluate?"
RETRIEVAL_ID = "retrieval-fixture-1"
ANSWER_ID = "answer-fixture-1"


class FakeRetrievalService:
    def __init__(self, *responses: RetrievalRun | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, int]] = []

    def search_evidence(
        self,
        text: str,
        *,
        collection: str,
        limit: int = 5,
    ) -> RetrievalRun:
        self.calls.append((text, collection, limit))
        if not self._responses:
            raise AssertionError("fake retrieval has no queued response.")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeAnsweringService:
    def __init__(self, *responses: AnswerOutcome | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[Path] = []

    def answer(
        self,
        retrieval_run: Path,
        *,
        output: Path | None = None,
    ) -> AnswerOutcome:
        del output
        self.calls.append(retrieval_run)
        if not self._responses:
            raise AssertionError("fake answering has no queued response.")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def evidence() -> EvidenceItem:
    return EvidenceItem(
        rank=1,
        score=0.91,
        chunk_id="chunk-7f7563be8042d8cdfa51a2fa",
        document_id="doc-NCT07424430",
        nct_id="NCT07424430",
        section="summary",
        text="The study aims to evaluate semaglutide outcomes.",
        source_url="https://clinicaltrials.gov/study/NCT07424430",
        content_hash="a" * 64,
    )


def retrieval_run(
    *,
    question: str = QUESTION,
    retrieval_id: str = RETRIEVAL_ID,
    status: str = "completed",
) -> RetrievalRun:
    evidence_items = () if status == "no_results" else (evidence(),)
    results = tuple(
        RetrievalResult(
            rank=item.rank,
            score=item.score,
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            nct_id=item.nct_id,
            section=item.section,
            text=item.text,
            source_url=item.source_url,
            content_hash=item.content_hash,
        )
        for item in evidence_items
    )
    return RetrievalRun(
        retrieval_id=retrieval_id,
        created_at=datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
        query=RetrievalQuery.from_values(question, "clinical_evidence_v1", 5),
        tei_model="BAAI/bge-small-en-v1.5",
        collection="clinical_evidence_v1",
        status=status,  # type: ignore[arg-type]
        results=results,
    )


def answer_outcome(
    path: Path,
    *,
    question: str = QUESTION,
    retrieval_id: str = RETRIEVAL_ID,
    status: str = "answered",
    include_evidence: bool = True,
) -> AnswerOutcome:
    evidence_items = (evidence(),) if include_evidence else ()
    claims: tuple[AnswerClaim, ...] = ()
    citations: tuple[AnswerCitation, ...] = ()
    reason: str | None = None
    errors: tuple[str, ...] = ()
    model_output: str | None = None

    if status == "answered":
        claims = (
            AnswerClaim(
                claim_id="claim-1",
                text="The study evaluates semaglutide outcomes.",
                citation_ids=(evidence().chunk_id,),
            ),
        )
        citations = (
            AnswerCitation(
                citation_id=evidence().chunk_id,
                source_type="retrieval_evidence",
                nct_id=evidence().nct_id,
                section=evidence().section,
                source_url=evidence().source_url,
                content_hash=evidence().content_hash,
            ),
        )
        model_output = '{"status":"answered"}'
    elif status == "insufficient_evidence":
        reason = "The evidence is insufficient."
        model_output = '{"status":"insufficient_evidence"}'
    elif status == "failed":
        errors = ("model response invalid",)
        model_output = "invalid"
    else:
        raise ValueError(f"unsupported fake answer status: {status}")

    run = AnswerRun(
        answer_id=ANSWER_ID,
        created_at=datetime(2026, 10, 21, 12, 0, 2, tzinfo=UTC),
        status=status,  # type: ignore[arg-type]
        question=question,
        retrieval_id=retrieval_id,
        retrieval_created_at=datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
        evidence=evidence_items,
        model=AnswerConfig(provider="deepseek", model="deepseek-flash"),
        claims=claims,
        reason=reason,
        model_output=model_output,
        citations=citations,
        usage=ModelUsage(input_tokens=100, output_tokens=20, total_tokens=120),
        latency_ms=900,
        errors=errors,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run.to_dict()), encoding="utf-8")
    return AnswerOutcome(run=run, path=path)
