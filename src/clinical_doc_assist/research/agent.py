"""Bounded tool-calling agent for public research discovery."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

from openai import OpenAI, OpenAIError

from clinical_doc_assist.research.clinical_trials import ClinicalTrialsSource
from clinical_doc_assist.research.models import (
    VALID_SCREENING_STATUSES,
    AgentError,
    ClockUnavailableError,
    DiscoveryRequest,
    DiscoveryRun,
    ModelDecision,
    ReasonCode,
    ResearchCandidate,
    ScreeningStatus,
    SearchRecord,
    SourceError,
    ToolResult,
)
from clinical_doc_assist.research.prompts import (
    RESEARCH_SYSTEM_PROMPT,
    build_research_user_prompt,
)
from clinical_doc_assist.research.screening import screen_candidates

CLOCK_TOOL = "get_current_datetime"
SEARCH_TOOL = "search_clinical_trials"

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": CLOCK_TOOL,
            "description": "Return the current date and time in ISO 8601 UTC.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": SEARCH_TOOL,
            "description": (
                "Search ClinicalTrials.gov within the user's fixed update window. "
                "This tool is unavailable until get_current_datetime succeeds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A focused clinical research topic query.",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]


class ResearchAgent:
    """Use one model loop and two tools to discover and screen candidates."""

    def __init__(
        self,
        *,
        client: OpenAI,
        model: str,
        source: ClinicalTrialsSource,
        now: Callable[[], datetime] | None = None,
        max_steps: int = 8,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1.")

        self._client = client
        self._model = model
        self._source = source
        self._now = now or (lambda: datetime.now(UTC))
        self._max_steps = max_steps

    def run(self, request: DiscoveryRequest) -> DiscoveryRun:
        """Run one bounded discovery session."""

        current_time: str | None = None
        clock_error: str | None = None
        candidates: list[ResearchCandidate] = []
        searches: list[SearchRecord] = []
        errors: list[str] = []
        successful_searches = 0
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": build_research_user_prompt(request)},
        ]

        for _ in range(self._max_steps):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                )
            except OpenAIError as exc:
                raise AgentError(f"model request failed: {exc}") from exc
            try:
                message = response.choices[0].message
            except (IndexError, AttributeError) as exc:
                raise AgentError("model response did not contain an assistant message.") from exc
            tool_calls = message.tool_calls or []
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": message.content or "",
            }

            if tool_calls:
                assistant_message["tool_calls"] = [
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
                messages.append(assistant_message)

                for call in tool_calls:
                    result = self._execute_tool(
                        name=call.function.name,
                        arguments=call.function.arguments,
                        request=request,
                        current_time=current_time,
                        candidates=candidates,
                        searches=searches,
                        errors=errors,
                    )
                    if call.function.name == CLOCK_TOOL:
                        if result.ok:
                            clock_value = _clock_value(result)
                            if current_time is None:
                                current_time = clock_value
                            clock_error = None
                        else:
                            clock_error = result.error or "current time unavailable"
                    elif call.function.name == SEARCH_TOOL and result.ok:
                        successful_searches += 1

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(result.to_dict(), ensure_ascii=False),
                        }
                    )
                continue

            decisions = _parse_decisions(message.content)
            if clock_error is not None:
                raise ClockUnavailableError(clock_error)
            if current_time is None:
                raise AgentError("The agent finished without recording current time.")
            if successful_searches == 0:
                detail = "; ".join(errors) if errors else "no search was attempted"
                raise AgentError(f"The agent finished without a successful search: {detail}")

            screening = screen_candidates(candidates, request, decisions)
            return DiscoveryRun(
                status="completed" if candidates else "no_results",
                request=request,
                current_time=current_time,
                searches=tuple(searches),
                accepted=screening.accepted,
                rejected=screening.rejected,
                needs_review=screening.needs_review,
                errors=tuple(errors),
            )

        raise AgentError(f"The agent exceeded its {self._max_steps}-step limit.")

    def _execute_tool(
        self,
        *,
        name: str,
        arguments: str,
        request: DiscoveryRequest,
        current_time: str | None,
        candidates: list[ResearchCandidate],
        searches: list[SearchRecord],
        errors: list[str],
    ) -> ToolResult:
        if name == CLOCK_TOOL:
            try:
                value = self._now()
                if value.tzinfo is None:
                    value = value.replace(tzinfo=UTC)
                iso_value = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
            except Exception as exc:
                message = f"current time unavailable: {exc}"
                errors.append(message)
                return ToolResult.failure(message)
            return ToolResult.success({"current_time": iso_value})

        if name != SEARCH_TOOL:
            return ToolResult.failure(f"unknown tool: {name}")
        if current_time is None:
            return ToolResult.failure("clock_required")

        query = _query(arguments)
        if not query:
            return ToolResult.failure("search query cannot be empty")
        remaining = request.limit - len(candidates)
        if remaining <= 0:
            return ToolResult.success({"count": 0, "candidates": []})
        try:
            found = self._source.search(request, query=query)
        except SourceError as exc:
            message = str(exc)
            errors.append(message)
            return ToolResult.failure(message)

        found = found[:remaining]
        candidates.extend(found)
        searches.append(
            SearchRecord(
                query=query,
                updated_after=request.updated_after,
                updated_before=request.updated_before,
                result_count=len(found),
            )
        )
        return ToolResult.success(
            {
                "count": len(found),
                "candidates": [candidate.to_dict() for candidate in found],
            }
        )


def _query(arguments: str) -> str:
    try:
        value = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return ""
    if not isinstance(value, dict):
        return ""
    query = value.get("query")
    return query.strip() if isinstance(query, str) else ""


def _parse_decisions(content: str | None) -> tuple[ModelDecision, ...]:
    try:
        payload = json.loads(content or "")
    except json.JSONDecodeError as exc:
        raise AgentError("The agent did not return valid decision JSON.") from exc

    raw_decisions = payload.get("decisions") if isinstance(payload, dict) else None
    if not isinstance(raw_decisions, list):
        raise AgentError("The agent response must contain a decisions list.")

    decisions: list[ModelDecision] = []
    for item in raw_decisions:
        if not isinstance(item, dict):
            continue
        nct_id = item.get("nct_id")
        status = item.get("status")
        if not isinstance(nct_id, str) or not isinstance(status, str):
            continue
        if status not in VALID_SCREENING_STATUSES:
            continue
        screening_status = cast(ScreeningStatus, status)
        reason_codes = _model_reason_codes(screening_status)
        decisions.append(ModelDecision(nct_id, screening_status, reason_codes))
    return tuple(decisions)


def _model_reason_codes(status: ScreeningStatus) -> tuple[ReasonCode, ...]:
    if status == "accepted":
        return ("relevant_topic",)
    if status == "rejected":
        return ("off_topic",)
    return ("ambiguous_metadata",)


def _clock_value(result: ToolResult) -> str:
    value = (result.data or {}).get("current_time")
    if not isinstance(value, str):
        raise AgentError("current time tool returned invalid output.")
    return value
