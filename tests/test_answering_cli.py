from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from clinical_doc_assist.answering.cli import main
from clinical_doc_assist.answering.models import (
    AgentResult,
    AnswerConfig,
    AnsweringInputError,
    EvidenceItem,
)
from clinical_doc_assist.answering.service import AnswerService
from tests.fixtures.answering.fakes import usage

FIXTURES = Path(__file__).parent / "fixtures" / "answering"


class FakeAgent:
    def __init__(self, content: str) -> None:
        self.content = content

    def run(
        self,
        question: str,
        evidence: tuple[EvidenceItem, ...],
    ) -> AgentResult:
        del question, evidence
        return AgentResult(content=self.content, usage=usage())


class ServiceFactory:
    def __init__(self, content: str) -> None:
        self.content = content

    def __call__(self, allowed_nct_ids: frozenset[str]) -> FakeAgent:
        del allowed_nct_ids
        return FakeAgent(self.content)


def fixed_now() -> datetime:
    return datetime(2026, 10, 21, 12, 0, 8, tzinfo=UTC)


def make_service(tmp_path: Path, content: str) -> AnswerService:
    return AnswerService(
        config=AnswerConfig(provider="deepseek", model="deepseek-flash"),
        agent_factory=ServiceFactory(content),
        output_dir=tmp_path / "answers",
        now=fixed_now,
        monotonic=iter([1.0, 1.2]).__next__,
        id_factory=lambda: "0123456789abcdef",
    )


def test_cli_prints_and_persists_answered_json(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "answer.json"
    service = make_service(
        tmp_path,
        json.dumps(
            {
                "status": "answered",
                "claims": [
                    {
                        "text": "Supported.",
                        "citation_ids": ["chunk-7f7563be8042d8cdfa51a2fa"],
                    }
                ],
            }
        ),
    )

    exit_code = main(
        ["--retrieval-run", str(FIXTURES / "retrieval-supported.json"), "--output", str(output)],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == json.loads(output.read_text(encoding="utf-8"))
    assert json.loads(captured.out)["status"] == "answered"


def test_cli_returns_zero_for_no_results_abstention(
    tmp_path: Path,
    capsys,
) -> None:
    service = AnswerService(
        config=AnswerConfig(provider="deepseek", model="deepseek-flash"),
        agent_factory=lambda allowed: (_ for _ in ()).throw(
            AssertionError(f"agent should not be created: {allowed}")
        ),
        output_dir=tmp_path / "answers",
        now=fixed_now,
        monotonic=iter([1.0, 1.01]).__next__,
        id_factory=lambda: "0123456789abcdef",
    )

    exit_code = main(
        ["--retrieval-run", str(FIXTURES / "retrieval-no-results.json")],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["status"] == "insufficient_evidence"


def test_cli_uses_default_answer_path(tmp_path: Path, capsys) -> None:
    service = make_service(
        tmp_path,
        json.dumps(
            {
                "status": "answered",
                "claims": [
                    {
                        "text": "Supported.",
                        "citation_ids": ["chunk-7f7563be8042d8cdfa51a2fa"],
                    }
                ],
            }
        ),
    )

    exit_code = main(
        ["--retrieval-run", str(FIXTURES / "retrieval-supported.json")],
        service=service,
    )

    expected = tmp_path / "answers" / "answer-0123456789abcdef.json"
    captured = capsys.readouterr()
    assert exit_code == 0
    assert expected.is_file()
    assert json.loads(captured.out) == json.loads(expected.read_text(encoding="utf-8"))


def test_cli_standard_output_is_ascii_safe(tmp_path: Path, capsys) -> None:
    service = make_service(
        tmp_path,
        json.dumps(
            {
                "status": "answered",
                "claims": [
                    {
                        "text": "HbA1c fell to \u2264 7%.",
                        "citation_ids": ["chunk-7f7563be8042d8cdfa51a2fa"],
                    }
                ],
            }
        ),
    )

    exit_code = main(
        ["--retrieval-run", str(FIXTURES / "retrieval-supported.json")],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.isascii()
    assert json.loads(captured.out)["claims"][0]["text"] == "HbA1c fell to \u2264 7%."


def test_cli_prints_failed_record_and_returns_one(
    tmp_path: Path,
    capsys,
) -> None:
    service = make_service(
        tmp_path,
        json.dumps(
            {
                "status": "answered",
                "claims": [{"text": "Unsupported.", "citation_ids": ["chunk-unknown"]}],
            }
        ),
    )

    exit_code = main(
        ["--retrieval-run", str(FIXTURES / "retrieval-supported.json")],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert json.loads(captured.out)["status"] == "failed"


def test_cli_reports_invalid_input_to_stderr(tmp_path: Path, capsys) -> None:
    class InvalidService:
        def answer(self, retrieval_run: Path, *, output: Path | None = None):
            del retrieval_run, output
            raise AnsweringInputError("invalid retrieval artifact")

    exit_code = main(
        ["--retrieval-run", str(FIXTURES / "retrieval-supported.json")],
        service=InvalidService(),
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "invalid retrieval artifact" in captured.err


def test_cli_refuses_existing_explicit_output(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "existing.json"
    output.write_text("keep", encoding="utf-8")
    service = make_service(tmp_path, "unused")

    exit_code = main(
        ["--retrieval-run", str(FIXTURES / "retrieval-supported.json"), "--output", str(output)],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "already exists" in captured.err
    assert output.read_text(encoding="utf-8") == "keep"
