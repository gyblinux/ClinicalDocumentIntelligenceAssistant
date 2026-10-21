"""Bounded single-turn answer agent and DeepSeek chat adapter."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Protocol

from openai import OpenAI, OpenAIError

from clinical_doc_assist.answering.models import (
    MAX_MODEL_TURNS,
    MAX_OUTPUT_TOKENS,
    MAX_TOOL_CALLS,
    AgentResult,
    AnsweringModelError,
    AnsweringToolError,
    EvidenceItem,
    ModelToolCall,
    ModelTurn,
    ModelUsage,
)
from clinical_doc_assist.answering.prompts import (
    ANSWERING_SYSTEM_PROMPT,
    build_answer_user_prompt,
)
from clinical_doc_assist.answering.tools import METADATA_TOOL_NAME, TOOL_SCHEMA, TrialMetadataTool


class ChatModel(Protocol):
    def complete(
        self,
        *,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
    ) -> ModelTurn: ...


class DeepSeekModelClient:
    """Adapt the OpenAI-compatible DeepSeek chat API to a testable protocol."""

    def __init__(
        self,
        *,
        client: OpenAI,
        model: str,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> None:
        if not model.strip():
            raise ValueError("model cannot be empty.")
        if max_output_tokens != MAX_OUTPUT_TOKENS:
            raise ValueError(f"max_output_tokens must be {MAX_OUTPUT_TOKENS}.")
        self._client = client
        self._model = model.strip()
        self._max_output_tokens = max_output_tokens

    def complete(
        self,
        *,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
    ) -> ModelTurn:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=list(messages),
                tools=list(tools),
                tool_choice="auto",
                max_tokens=self._max_output_tokens,
            )
        except OpenAIError as exc:
            raise AnsweringModelError(f"model request failed: {exc}") from exc

        try:
            message = response.choices[0].message
        except (AttributeError, IndexError) as exc:
            raise AnsweringModelError(
                "model response did not contain an assistant message."
            ) from exc

        tool_calls = tuple(
            ModelToolCall(
                call_id=call.id,
                name=call.function.name,
                arguments=call.function.arguments,
            )
            for call in (message.tool_calls or [])
        )
        usage = _usage(response)
        return ModelTurn(
            content=message.content,
            tool_calls=tool_calls,
            usage=usage,
        )

    def close(self) -> None:
        self._client.close()


class AnswerAgent:
    """Run at most two model turns with one metadata tool."""

    def __init__(
        self,
        *,
        model: ChatModel,
        metadata_tool: TrialMetadataTool,
        max_model_turns: int = MAX_MODEL_TURNS,
    ) -> None:
        if max_model_turns != MAX_MODEL_TURNS:
            raise ValueError(f"max_model_turns must be {MAX_MODEL_TURNS}.")
        self._model = model
        self._metadata_tool = metadata_tool
        self._max_model_turns = max_model_turns

    def run(self, question: str, evidence: tuple[EvidenceItem, ...]) -> AgentResult:
        """Produce model content while enforcing the bounded tool policy."""

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": ANSWERING_SYSTEM_PROMPT},
            {"role": "user", "content": build_answer_user_prompt(question, evidence)},
        ]
        usage = ModelUsage()
        attempted_tool_calls = 0

        for turn_index in range(self._max_model_turns):
            try:
                turn = self._model.complete(
                    messages=messages,
                    tools=(TOOL_SCHEMA,),
                )
            except AnsweringModelError as exc:
                return AgentResult(
                    content=None,
                    usage=usage,
                    tool_calls=self._metadata_tool.lookups,
                    error=str(exc),
                )

            usage = usage.add(turn.usage)
            if not turn.tool_calls:
                return AgentResult(
                    content=turn.content,
                    usage=usage,
                    tool_calls=self._metadata_tool.lookups,
                )
            if turn_index == self._max_model_turns - 1:
                return self._failure(
                    usage,
                    "model requested a metadata tool after its final allowed turn.",
                )
            if attempted_tool_calls + len(turn.tool_calls) > MAX_TOOL_CALLS:
                return self._failure(
                    usage,
                    f"model exceeded the {MAX_TOOL_CALLS}-lookup limit.",
                )

            messages.append(_assistant_tool_message(turn))
            for tool_call in turn.tool_calls:
                if tool_call.name != METADATA_TOOL_NAME:
                    return self._failure(
                        usage,
                        f"model requested unknown tool: {tool_call.name}.",
                    )
                nct_id = _nct_id_argument(tool_call.arguments)
                if nct_id is None:
                    return self._failure(
                        usage,
                        "fetch_trial_metadata requires one string nct_id argument.",
                    )
                try:
                    lookup = self._metadata_tool.execute(nct_id)
                except AnsweringToolError as exc:
                    return self._failure(usage, str(exc))

                attempted_tool_calls += 1
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.call_id,
                        "content": json.dumps(lookup.to_dict(), ensure_ascii=False),
                    }
                )

        return self._failure(usage, f"model exceeded its {self._max_model_turns}-turn limit.")

    def _failure(self, usage: ModelUsage, message: str) -> AgentResult:
        return AgentResult(
            content=None,
            usage=usage,
            tool_calls=self._metadata_tool.lookups,
            error=message,
        )


def _assistant_tool_message(turn: ModelTurn) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": turn.content or "",
        "tool_calls": [
            {
                "id": call.call_id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": call.arguments,
                },
            }
            for call in turn.tool_calls
        ],
    }


def _nct_id_argument(arguments: str) -> str | None:
    try:
        payload = json.loads(arguments)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("nct_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _usage(response: object) -> ModelUsage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return ModelUsage()
    return ModelUsage(
        input_tokens=_token_value(getattr(usage, "prompt_tokens", None)),
        output_tokens=_token_value(getattr(usage, "completion_tokens", None)),
        total_tokens=_token_value(getattr(usage, "total_tokens", None)),
    )


def _token_value(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
