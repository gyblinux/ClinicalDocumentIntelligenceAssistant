"""Starter tools for the clinical documentation agent."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

ToolHandler = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class Tool:
    """A model-facing function and its application-side implementation."""

    name: str
    description: str
    parameters: Mapping[str, Any]
    handler: ToolHandler

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert the tool to the Chat Completions tool schema."""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": dict(self.parameters),
            },
        }


def calculate_bmi(weight_kg: float, height_m: float) -> dict[str, Any]:
    """Calculate BMI from metric measurements."""

    if weight_kg <= 0:
        raise ValueError("weight_kg must be greater than zero.")
    if height_m <= 0:
        raise ValueError("height_m must be greater than zero.")

    bmi = weight_kg / (height_m**2)
    return {
        "bmi": round(bmi, 1),
        "note": "BMI is a screening measure and is not a diagnosis.",
    }


CLINICAL_TEMPLATES: dict[str, str] = {
    "soap": (
        "Subjective:\n- \n\n"
        "Objective:\n- \n\n"
        "Assessment:\n- \n\n"
        "Plan:\n- "
    ),
    "progress_note": (
        "Interval history:\n- \n\n"
        "Current status:\n- \n\n"
        "Assessment:\n- \n\n"
        "Plan:\n- "
    ),
    "discharge_summary": (
        "Admission and presenting concern:\n- \n\n"
        "Relevant findings:\n- \n\n"
        "Hospital course:\n- \n\n"
        "Discharge plan and follow-up:\n- "
    ),
}


def get_clinical_template(template_name: str) -> dict[str, Any]:
    """Return a local, non-PHI documentation template."""

    normalized_name = template_name.strip().lower()
    try:
        template = CLINICAL_TEMPLATES[normalized_name]
    except KeyError as exc:
        supported = ", ".join(sorted(CLINICAL_TEMPLATES))
        raise ValueError(
            f"Unknown template '{template_name}'. Supported templates: {supported}."
        ) from exc

    return {"template_name": normalized_name, "template": template}


def build_default_tools() -> dict[str, Tool]:
    """Build the starter tool registry.

    Replace or extend this registry with application-specific functions. Keep
    each function small and enforce authorization in your own infrastructure.
    """

    tools = (
        Tool(
            name="calculate_bmi",
            description=(
                "Calculate BMI from weight in kilograms and height in meters. "
                "Use only when both measurements are supplied. The result is a "
                "screening measure, not a diagnosis."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "weight_kg": {
                        "type": "number",
                        "description": "Patient weight in kilograms.",
                    },
                    "height_m": {
                        "type": "number",
                        "description": "Patient height in meters.",
                    },
                },
                "required": ["weight_kg", "height_m"],
                "additionalProperties": False,
            },
            handler=calculate_bmi,
        ),
        Tool(
            name="get_clinical_template",
            description=(
                "Return the heading structure for a local clinical note template. "
                "This tool contains no patient data."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "enum": sorted(CLINICAL_TEMPLATES),
                        "description": "The document template to retrieve.",
                    }
                },
                "required": ["template_name"],
                "additionalProperties": False,
            },
            handler=get_clinical_template,
        ),
    )
    return {tool.name: tool for tool in tools}


def execute_tool(tool: Tool, arguments: str) -> str:
    """Validate and execute a model-requested function call."""

    try:
        parsed_arguments = json.loads(arguments or "{}")
    except json.JSONDecodeError as exc:
        return json.dumps({"ok": False, "error": f"Invalid JSON arguments: {exc.msg}"})

    if not isinstance(parsed_arguments, dict):
        return json.dumps({"ok": False, "error": "Tool arguments must be a JSON object."})

    try:
        result = tool.handler(**parsed_arguments)
    except (TypeError, ValueError) as exc:
        return json.dumps({"ok": False, "error": str(exc)})

    return json.dumps({"ok": True, "result": result}, ensure_ascii=False)

