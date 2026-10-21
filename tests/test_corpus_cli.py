from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from clinical_doc_assist.corpus.cli import main
from clinical_doc_assist.corpus.models import (
    BuildManifest,
    BuildSettings,
    CorpusBuildResult,
    CorpusInputError,
    CorpusOutputError,
    DiscoveryAggregate,
)


def _result(status: str, output: Path) -> CorpusBuildResult:
    manifest = BuildManifest(
        "corpus-test",
        status,
        datetime(2026, 10, 21, 9, 0),
        DiscoveryAggregate((), ()),
        BuildSettings(),
        0,
        0,
        (),
        (),
    )
    return CorpusBuildResult(manifest, output)


def test_cli_runs_with_repeatable_discovery_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: list[tuple[list[Path], Path, BuildSettings]] = []
    output = tmp_path / "corpus"

    def run(
        discovery_paths: list[Path],
        output_path: Path,
        settings: BuildSettings,
    ) -> CorpusBuildResult:
        captured.append((discovery_paths, output_path, settings))
        return _result("completed", output_path)

    exit_code = main(
        [
            "build",
            "--discovery-run",
            "one.json",
            "--discovery-run",
            "two.json",
            "--output",
            str(output),
        ],
        run_build=run,
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert [path.name for path in captured[0][0]] == ["one.json", "two.json"]
    assert summary["status"] == "completed"


@pytest.mark.parametrize(
    ("status", "exit_code"),
    [("completed", 0), ("partial", 0), ("no_documents", 3), ("failed", 1)],
)
def test_cli_maps_build_status_to_exit_code(
    status: str,
    exit_code: int,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "build",
            "--discovery-run",
            "one.json",
            "--output",
            str(tmp_path / status),
        ],
        run_build=lambda _, output, __: _result(status, output),
    )

    assert code == exit_code
    assert json.loads(capsys.readouterr().out)["status"] == status


def test_cli_reports_invalid_settings_and_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "build",
            "--discovery-run",
            "one.json",
            "--output",
            str(tmp_path / "bad-settings"),
            "--max-chars",
            "10",
            "--overlap-chars",
            "10",
        ],
        run_build=lambda *_: _result("completed", tmp_path),
    )
    assert code == 2
    assert "overlap_chars" in capsys.readouterr().err

    def fail(*_: object) -> CorpusBuildResult:
        raise CorpusInputError("invalid discovery")

    code = main(
        [
            "build",
            "--discovery-run",
            "one.json",
            "--output",
            str(tmp_path / "bad-input"),
        ],
        run_build=fail,
    )
    assert code == 2
    assert "invalid discovery" in capsys.readouterr().err


def test_cli_reports_output_errors_concisely(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*_: object) -> CorpusBuildResult:
        raise CorpusOutputError("output denied")

    code = main(
        [
            "build",
            "--discovery-run",
            "one.json",
            "--output",
            str(tmp_path / "corpus"),
        ],
        run_build=fail,
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.strip() == "Corpus error: output denied"
