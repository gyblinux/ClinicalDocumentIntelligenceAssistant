from __future__ import annotations

from datetime import UTC, datetime

import pytest

from clinical_doc_assist.answering.models import (
    MAX_CLAIMS,
    MAX_EVIDENCE_ITEMS,
    MAX_MODEL_TURNS,
    MAX_OUTPUT_TOKENS,
    MAX_TOOL_CALLS,
    AnswerConfig,
    EvidenceItem,
    ModelClaim,
    ModelResponse,
    RetrievalInput,
)


def evidence(rank: int = 1, nct_id: str = "NCT07424430") -> EvidenceItem:
    return EvidenceItem(
        rank=rank,
        score=0.9,
        chunk_id=f"chunk-{rank}",
        document_id="doc-NCT07424430",
        nct_id=nct_id,
        section="summary",
        text="The trial evaluates semaglutide outcomes.",
        source_url=f"https://clinicaltrials.gov/study/{nct_id}",
        content_hash="a" * 64,
    )


def test_evidence_rejects_invalid_rank_and_nct_id() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        EvidenceItem(
            rank="1",  # type: ignore[arg-type]
            score=0.9,
            chunk_id="chunk-1",
            document_id="doc-1",
            nct_id="NCT07424430",
            section="summary",
            text="Text",
            source_url="https://clinicaltrials.gov/study/NCT07424430",
            content_hash="a" * 64,
        )

    with pytest.raises(ValueError, match="invalid NCT"):
        evidence(nct_id="NCT123")


def test_completed_retrieval_requires_one_to_ten_items() -> None:
    with pytest.raises(ValueError, match=f"1-{MAX_EVIDENCE_ITEMS}"):
        RetrievalInput(
            retrieval_id="retrieval-1",
            created_at=datetime.now(UTC),
            question="Question",
            collection="clinical_evidence_v1",
            query_limit=5,
            evidence=(),
            status="completed",
        )


def test_no_results_retrieval_must_be_empty() -> None:
    with pytest.raises(ValueError, match="cannot contain"):
        RetrievalInput(
            retrieval_id="retrieval-1",
            created_at=datetime.now(UTC),
            question="Question",
            collection="clinical_evidence_v1",
            query_limit=5,
            evidence=(evidence(),),
            status="no_results",
        )


def test_retrieval_rejects_duplicate_ranks_and_chunk_ids() -> None:
    with pytest.raises(ValueError, match="ranks must be unique"):
        RetrievalInput(
            retrieval_id="retrieval-1",
            created_at=datetime.now(UTC),
            question="Question",
            collection="clinical_evidence_v1",
            query_limit=5,
            evidence=(evidence(1), evidence(1)),
            status="completed",
        )


def test_answer_config_enforces_fixed_limits() -> None:
    config = AnswerConfig(provider="deepseek", model="deepseek-flash")
    assert config.max_model_turns == MAX_MODEL_TURNS
    assert config.max_tool_calls == MAX_TOOL_CALLS
    assert config.max_evidence_items == MAX_EVIDENCE_ITEMS
    assert config.max_output_tokens == MAX_OUTPUT_TOKENS
    assert config.max_claims == MAX_CLAIMS

    with pytest.raises(ValueError, match="fixed"):
        AnswerConfig(provider="deepseek", model="deepseek-flash", max_tool_calls=4)

    with pytest.raises(ValueError, match="fixed"):
        AnswerConfig(provider="deepseek", model="deepseek-flash", max_claims=11)


def test_model_response_status_shapes_are_enforced() -> None:
    claim = ModelClaim(text="Supported claim.", citation_ids=("chunk-1",))
    assert ModelResponse(status="answered", claims=(claim,)).claims == (claim,)

    with pytest.raises(ValueError, match="requires at least one claim"):
        ModelResponse(status="answered")
    with pytest.raises(ValueError, match="cannot contain claims"):
        ModelResponse(
            status="insufficient_evidence",
            claims=(claim,),
            reason="Not enough evidence.",
        )
