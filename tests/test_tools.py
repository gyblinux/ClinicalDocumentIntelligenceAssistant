from __future__ import annotations

import json

from clinical_doc_assist.tools import build_default_tools, execute_tool


def test_bmi_tool_returns_rounding_and_safety_note() -> None:
    result = json.loads(
        execute_tool(
            build_default_tools()["calculate_bmi"],
            '{"weight_kg":70,"height_m":1.75}',
        )
    )

    assert result["ok"] is True
    assert result["result"]["bmi"] == 22.9
    assert "not a diagnosis" in result["result"]["note"]


def test_invalid_arguments_are_returned_as_structured_errors() -> None:
    result = json.loads(execute_tool(build_default_tools()["calculate_bmi"], "not-json"))

    assert result["ok"] is False
    assert "Invalid JSON" in result["error"]
