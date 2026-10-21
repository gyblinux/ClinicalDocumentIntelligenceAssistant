from __future__ import annotations

import json
from datetime import date

import pytest

from clinical_doc_assist.research.cli import main
from clinical_doc_assist.research.models import (
    AgentError,
    DiscoveryRequest,
    DiscoveryRun,
    RunStatus,
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
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(_: DiscoveryRequest) -> DiscoveryRun:
        raise AgentError("source unavailable")

    exit_code = main(
        [
            "diabetes",
            "--updated-after",
            "2023-01-01",
            "--updated-before",
            "2026-01-01",
        ],
        run_discovery=fail,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "source unavailable" in captured.err


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
