"""Shared JSON loading and atomic persistence for evaluation artifacts."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from clinical_doc_assist.evaluation.models import (
    EvaluationInputError,
    EvaluationOutputError,
)


def load_json(path: Path, label: str) -> Any:
    """Load one JSON value with consistent path-aware diagnostics."""

    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise EvaluationInputError(f"Cannot read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationInputError(f"{label} is not valid JSON: {path}") from exc


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object."""

    payload = load_json(path, label)
    if not isinstance(payload, dict):
        raise EvaluationInputError(f"{label} must be a JSON object.")
    return payload


def required_text(payload: dict[str, Any], field_name: str) -> str:
    """Return one required non-empty string field."""

    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise EvaluationInputError(f"{field_name} must be a non-empty string.")
    return value.strip()


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write one JSON artifact without overwriting an existing path."""

    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    write_text_atomic(path, text)


def write_text_atomic(path: Path, text: str) -> None:
    """Write one local artifact using an atomic replacement."""

    if path.exists():
        raise EvaluationOutputError(f"artifact already exists: {path}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        os.close(file_descriptor)
        temporary_path = Path(temporary_name)
        try:
            temporary_path.write_text(text, encoding="utf-8")
            if path.exists():
                raise EvaluationOutputError(f"artifact already exists: {path}")
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
    except EvaluationOutputError:
        raise
    except OSError as exc:
        raise EvaluationOutputError(f"Cannot write artifact {path}: {exc}") from exc
