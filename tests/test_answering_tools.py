from __future__ import annotations

from datetime import UTC, datetime

import pytest

from clinical_doc_assist.answering.models import AnsweringToolError
from clinical_doc_assist.answering.tools import (
    TrialMetadataTool,
    normalize_trial_metadata,
)
from clinical_doc_assist.research.models import SourceError
from tests.fixtures.answering.fakes import FakeTrialSource, trial_study


def fixed_now() -> datetime:
    return datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def test_normalize_trial_metadata_returns_compact_public_fields() -> None:
    result = normalize_trial_metadata(
        trial_study(),
        expected_nct_id="NCT07424430",
    )

    assert result["nct_id"] == "NCT07424430"
    assert result["overall_status"] == "RECRUITING"
    assert result["enrollment"] == {"count": 500, "type": "ACTUAL"}
    assert result["interventions"] == [{"name": "semaglutide", "type": "DRUG"}]


def test_tool_executes_only_allowlisted_identifier() -> None:
    source = FakeTrialSource({"NCT07424430": trial_study()})
    tool = TrialMetadataTool(
        source=source,
        allowed_nct_ids=frozenset({"NCT07424430"}),
        now=fixed_now,
        id_factory=lambda: "lookup-1",
    )

    lookup = tool.execute("NCT07424430")
    assert lookup.status == "completed"
    assert lookup.lookup_id == "lookup-1"
    assert source.calls == ["NCT07424430"]

    rejected = tool.execute("NCT00000002")
    assert rejected.status == "failed"
    assert source.calls == ["NCT07424430"]


def test_tool_prevents_duplicate_and_unbounded_lookups() -> None:
    source = FakeTrialSource(
        {
            "NCT07424430": trial_study(),
            "NCT07424431": trial_study("NCT07424431"),
            "NCT07424432": trial_study("NCT07424432"),
            "NCT07424433": trial_study("NCT07424433"),
        }
    )
    tool = TrialMetadataTool(
        source=source,
        allowed_nct_ids=frozenset(
            {"NCT07424430", "NCT07424431", "NCT07424432", "NCT07424433"}
        ),
        now=fixed_now,
        id_factory=iter(
            ["lookup-1", "lookup-2", "lookup-3", "lookup-4"]
        ).__next__,
    )

    assert tool.execute("NCT07424430").status == "completed"
    duplicate = tool.execute("NCT07424430")
    assert duplicate.status == "failed"
    assert "already requested" in (duplicate.error or "")
    assert tool.execute("NCT07424431").status == "completed"
    assert tool.execute("NCT07424432").status == "completed"

    with pytest.raises(AnsweringToolError, match="limit"):
        tool.execute("NCT07424433")
    assert source.calls == ["NCT07424430", "NCT07424431", "NCT07424432"]


def test_tool_records_source_failure() -> None:
    source = FakeTrialSource(
        {"NCT07424430": SourceError("temporary source failure")}
    )
    tool = TrialMetadataTool(
        source=source,
        allowed_nct_ids=frozenset({"NCT07424430"}),
        now=fixed_now,
        id_factory=lambda: "lookup-1",
    )

    lookup = tool.execute("NCT07424430")
    assert lookup.status == "failed"
    assert lookup.error == "temporary source failure"


def test_tool_rejects_syntactically_invalid_nct_id() -> None:
    tool = TrialMetadataTool(
        source=FakeTrialSource({}),
        allowed_nct_ids=frozenset({"NCT07424430"}),
        now=fixed_now,
    )

    with pytest.raises(AnsweringToolError, match="invalid NCT"):
        tool.execute("not-an-nct")
