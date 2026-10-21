from __future__ import annotations

import json
from itertools import count
from pathlib import Path

from clinical_doc_assist.evaluation.cli import main, main_eval, main_present
from clinical_doc_assist.evaluation.presentation import PresentationService
from clinical_doc_assist.evaluation.runner import EvaluationService

FIXTURES = Path(__file__).parent / "fixtures" / "evaluation"


def test_eval_run_cli_saved_mode(tmp_path: Path, capsys) -> None:
    values = count(1)
    service = EvaluationService(
        output_dir=tmp_path / "evaluations",
        id_factory=lambda: f"{next(values):016d}",
    )

    exit_code = main_eval(
        [
            "run",
            "--cases",
            str(FIXTURES / "cases-valid.json"),
            "--pipeline-map",
            str(FIXTURES / "pipeline-map.json"),
        ],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["mode"] == "saved"
    assert len(payload["cases"]) == 20


def test_compare_cli(tmp_path: Path, capsys) -> None:
    from tests.fixtures.evaluation.fakes import write_evaluation_report

    baseline = write_evaluation_report(tmp_path / "baseline.json")
    candidate = write_evaluation_report(tmp_path / "candidate.json")
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["configuration"]["limit"] = 10
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "comparison.json"

    exit_code = main_eval(
        [
            "compare",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["changed_variable"] == "limit"
    assert output.is_file()


def test_review_cli(tmp_path: Path, capsys) -> None:
    exit_code = main_eval(
        [
            "review",
            "--input",
            str(FIXTURES / "artifacts" / "presentation-review.json"),
            "--output-dir",
            str(tmp_path / "reviews"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["passed"] is True


def test_present_cli(tmp_path: Path, capsys) -> None:
    output = tmp_path / "answer.txt"
    service = PresentationService(
        now=lambda: __import__("datetime").datetime(
            2026, 10, 21, tzinfo=__import__("datetime").UTC
        ),
        id_factory=lambda: "fixture",
    )

    exit_code = main_present(
        [
            "--pipeline",
            str(FIXTURES / "artifacts" / "pipeline.json"),
            "--output",
            str(output),
        ],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.startswith("ANSWER\n")
    assert output.is_file()
    assert captured.out == output.read_text(encoding="utf-8")


def test_eval_cli_rejects_invalid_case_count(tmp_path: Path, capsys) -> None:
    values = count(1)
    service = EvaluationService(
        output_dir=tmp_path / "evaluations",
        id_factory=lambda: f"{next(values):016d}",
    )

    exit_code = main_eval(
        [
            "run",
            "--cases",
            str(FIXTURES / "cases-too-few.json"),
            "--pipeline-map",
            str(FIXTURES / "pipeline-map.json"),
        ],
        service=service,
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "20-40" in captured.err


def test_present_cli_rejects_missing_pipeline(tmp_path: Path, capsys) -> None:
    exit_code = main_present(
        ["--pipeline", str(tmp_path / "missing.json")],
        service=PresentationService(output_dir=tmp_path / "presentations"),
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "Cannot read" in captured.err


def test_module_main_dispatches_present(monkeypatch) -> None:
    received: list[list[str]] = []

    def fake_present(argv: list[str]) -> int:
        received.append(argv)
        return 0

    monkeypatch.setattr(
        "clinical_doc_assist.evaluation.cli.main_present",
        fake_present,
    )

    assert main(["present", "--pipeline", "pipeline.json"]) == 0
    assert received == [["--pipeline", "pipeline.json"]]
