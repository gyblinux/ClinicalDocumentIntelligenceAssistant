"""A small, bounded agent loop for Chat Completions tool calling."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from clinical_doc_assist.config import Settings
from clinical_doc_assist.tools import Tool, build_default_tools, execute_tool

DEFAULT_SYSTEM_PROMPT = """\
You are a clinical documentation assistant. Draft clear, concise, structured
notes for review by a qualified clinician.

Rules:
- Use only facts provided by the user or returned by tools.
- Never invent patient history, measurements, diagnoses, medications, or follow-up.
- Clearly mark missing information and ask for it when it is needed.
- Do not present a draft as a final medical decision or as clinically verified.
- Use tools when a calculation or template is needed.
- Begin generated clinical documents with "DRAFT - CLINICIAN REVIEW REQUIRED".
- Keep protected health information out of tool arguments unless a real,
  authorized, audited integration explicitly requires it.
"""


class AgentError(RuntimeError):
    """Base error for agent execution."""


class MaxStepsExceeded(AgentError):
    """Raised when the model does not finish within the configured tool budget."""


@dataclass(frozen=True, slots=True)
class AgentReply:
    """A completed assistant turn and the tool names it used."""

    text: str
    tools_used: tuple[str, ...] = ()


class ClinicalDocumentationAgent:
    """Maintain conversation state and execute requested tools."""

    def __init__(
        self,
        *,
        client: OpenAI,
        model: str,
        tools: dict[str, Tool] | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_steps: int = 8,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1.")

        self._client = client
        self._model = model
        self._tools = tools if tools is not None else build_default_tools()
        self._max_steps = max_steps
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        tools: dict[str, Tool] | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> ClinicalDocumentationAgent:
        """Create an agent using the OpenAI SDK against DeepSeek."""

        client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
        )
        return cls(
            client=client,
            model=settings.model,
            tools=tools,
            system_prompt=system_prompt,
            max_steps=settings.max_steps,
        )

    @property
    def messages(self) -> tuple[dict[str, Any], ...]:
        """Return a read-only view of the current conversation."""

        return tuple(self._messages)

    def reset(self) -> None:
        """Clear all conversation turns while preserving the system prompt."""

        self._messages = self._messages[:1]

    def run(self, user_message: str) -> AgentReply:
        """Run one user turn until the assistant produces a final response."""

        prompt = user_message.strip()
        if not prompt:
            raise ValueError("user_message cannot be empty.")

        self._messages.append({"role": "user", "content": prompt})
        used_tools: list[str] = []
        tool_schemas = [tool.to_openai_tool() for tool in self._tools.values()]

        for _ in range(self._max_steps):
            response = self._client.chat.completions.create(
                model=self._model,
                messages=self._messages,
                tools=tool_schemas or None,
                tool_choice="auto" if tool_schemas else "none",
            )
            message = response.choices[0].message
            tool_calls = message.tool_calls or []
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": message.content or "",
            }
            if tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in tool_calls
                ]
            self._messages.append(assistant_message)

            if not tool_calls:
                text = message.content or ""
                return AgentReply(text=text.strip(), tools_used=tuple(used_tools))

            for tool_call in tool_calls:
                tool = self._tools.get(tool_call.function.name)
                used_tools.append(tool_call.function.name)
                if tool is None:
                    output = json.dumps(
                        {"ok": False, "error": f"Unknown tool: {tool_call.function.name}"}
                    )
                else:
                    output = execute_tool(tool, tool_call.function.arguments)

                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": output,
                    }
                )

        raise MaxStepsExceeded(
            f"The model did not produce a final answer within {self._max_steps} steps."
        )
