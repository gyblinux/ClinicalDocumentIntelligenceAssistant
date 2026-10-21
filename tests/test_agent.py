from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from clinical_doc_assist.agent import ClinicalDocumentationAgent
from clinical_doc_assist.tools import build_default_tools


def _completion(
    *,
    content: str | None = None,
    tool_calls: list[Any] | None = None,
) -> SimpleNamespace:
    message_data: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message_data["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in tool_calls
        ]

    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        model_dump=lambda **_: message_data,
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@dataclass
class FakeCompletions:
    responses: list[SimpleNamespace]
    requests: list[dict[str, Any]]

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.completions = FakeCompletions(responses=responses, requests=[])
        self.chat = SimpleNamespace(completions=self.completions)


def test_agent_executes_tool_and_returns_final_answer() -> None:
    tool_call = SimpleNamespace(
        id="call_bmi",
        function=SimpleNamespace(
            name="calculate_bmi",
            arguments=json.dumps({"weight_kg": 70, "height_m": 1.75}),
        ),
    )
    client = FakeClient(
        [
            _completion(tool_calls=[tool_call]),
            _completion(content="DRAFT - CLINICIAN REVIEW REQUIRED\n\nBMI: 22.9"),
        ]
    )
    agent = ClinicalDocumentationAgent(
        client=client,  # type: ignore[arg-type]
        model="deepseek-chat",
        tools=build_default_tools(),
        max_steps=3,
    )

    reply = agent.run("Calculate BMI for 70 kg and 1.75 m.")

    assert reply.tools_used == ("calculate_bmi",)
    assert "22.9" in reply.text
    assert client.completions.requests[0]["model"] == "deepseek-chat"
    tool_result = json.loads(agent.messages[-2]["content"])
    assert tool_result == {
        "ok": True,
        "result": {
            "bmi": 22.9,
            "note": "BMI is a screening measure and is not a diagnosis.",
        },
    }


def test_agent_returns_actionable_error_for_unknown_tool() -> None:
    tool_call = SimpleNamespace(
        id="call_unknown",
        function=SimpleNamespace(name="delete_patient", arguments="{}"),
    )
    client = FakeClient(
        [
            _completion(tool_calls=[tool_call]),
            _completion(content="I cannot perform that action."),
        ]
    )
    agent = ClinicalDocumentationAgent(
        client=client,  # type: ignore[arg-type]
        model="deepseek-chat",
    )

    reply = agent.run("Delete the patient.")

    assert reply.tools_used == ("delete_patient",)
    tool_result = json.loads(agent.messages[-2]["content"])
    assert tool_result == {"ok": False, "error": "Unknown tool: delete_patient"}


def test_agent_reset_preserves_only_system_prompt() -> None:
    client = FakeClient([_completion(content="Hello.")])
    agent = ClinicalDocumentationAgent(
        client=client,  # type: ignore[arg-type]
        model="deepseek-chat",
    )

    agent.run("Hello")
    agent.reset()

    assert len(agent.messages) == 1
    assert agent.messages[0]["role"] == "system"

