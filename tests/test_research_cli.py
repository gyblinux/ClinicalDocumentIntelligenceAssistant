from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from clinical_doc_assist.research.cli import main
from clinical_doc_assist.research.models import (
    AgentError,
    DiscoveryRequest,
    DiscoveryRun,
    ResearchCandidate,
    RunStatus,
    ScreeningDecision,
)


def _run(status: RunStatus = "completed") -> DiscoveryRun:
    return DiscoveryRun(
        status=status,
        request=DiscoveryRequest("diabetes", date(2023, 1, 1), date(2026, 1, 1)),
        current_time="2026-10-21T07:30:00Z",
        searches=(),
        accepted=(),
        rejected=(),
        needs_review=(),
        errors=(),
    )


def test_cli_writes_only_json_for_success(capsys: pytest.CaptureFixture[str]) -> None:
    captured: list[DiscoveryRequest] = []

    def run_discovery(request: DiscoveryRequest) -> DiscoveryRun:
        captured.append(request)
        return _run()

    exit_code = main(
        [
            "diabetes",
            "--updated-after",
            "2023-01-01",
            "--updated-before",
            "2026-01-01",
            "--limit",
            "3",
        ],
        run_discovery=run_discovery,
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "completed"
    assert captured[0].limit == 3


def test_cli_writes_same_json_to_output_artifact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "nested" / "discovery.json"

    exit_code = main(
        [
            "diabetes",
            "--updated-after",
            "2023-01-01",
            "--updated-before",
            "2026-01-01",
            "--output",
            str(output_path),
        ],
        run_discovery=lambda _: _run(),
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact == json.loads(stdout)
    assert artifact["schema_version"] == "1.0"
    assert artifact["run_id"].startswith("run-")


def test_cli_stdout_is_ascii_safe_for_unicode_candidates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "unicode.json"
    candidate = ResearchCandidate(
        nct_id="NCT12345678",
        title="Trial \u00ae",
        source_url="https://clinicaltrials.gov/study/NCT12345678",
        source_type="trial_registry",
        updated_date=date(2025, 1, 1),
        first_posted_date=date(2024, 1, 1),
        status="COMPLETED",
        study_type="INTERVENTIONAL",
        sponsor="Sponsor",
        evidence_snippet="Evidence",
    )
    decision = ScreeningDecision(
        candidate=candidate,
        status="accepted",
        reason_codes=("relevant_topic",),
    )
    run = DiscoveryRun(
        status="completed",
        request=DiscoveryRequest("trial", date(2023, 1, 1), date(2026, 1, 1)),
        current_time="2026-10-21T07:30:00Z",
        searches=(),
        accepted=(decision,),
        rejected=(),
        needs_review=(),
    )

    exit_code = main(
        [
            "trial",
            "--updated-after",
            "2023-01-01",
            "--updated-before",
            "2026-01-01",
            "--output",
            str(output_path),
        ],
        run_discovery=lambda _: run,
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    stdout.encode("ascii")
    assert "Trial \u00ae" in output_path.read_text(encoding="utf-8")
    assert json.loads(stdout) == json.loads(output_path.read_text(encoding="utf-8"))


def test_cli_returns_zero_for_no_results(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [
            "diabetes",
            "--updated-after",
            "2023-01-01",
            "--updated-before",
            "2026-01-01",
        ],
        run_discovery=lambda _: _run("no_results"),
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "no_results"


def test_cli_reports_agent_failure_on_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "failed.json"

    def fail(_: DiscoveryRequest) -> DiscoveryRun:
        raise AgentError("source unavailable")

    exit_code = main(
        [
            "diabetes",
            "--updated-after",
            "2023-01-01",
            "--updated-before",
            "2026-01-01",
            "--output",
            str(output_path),
        ],
        run_discovery=fail,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "source unavailable" in captured.err
    assert not output_path.exists()


def test_cli_rejects_invalid_dates() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "diabetes",
                "--updated-after",
                "not-a-date",
                "--updated-before",
                "2026-01-01",
            ]
        )

    assert exc_info.value.code == 2
