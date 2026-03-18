"""LangChain-agent orchestration helpers and deterministic fallback logic."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Sequence, cast

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from pydantic import ValidationError

from app.schemas.api.recommendations import (
    RecommendationQuery as ApiRecommendationQuery,
)
from app.schemas.orchestrator import (
    Intent,
    OrchestratorPolicyConfig,
    OrchestratorResponse,
    RecommendationToolRuntimePayload,
    TranscriptMessage,
)
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationResult,
    RecommendationToolResponse,
)
from app.services.orchestrator.extraction import (
    apply_message_state_updates,
    build_effective_recommendation_query_text,
    extract_query_filters,
    is_follow_up_refinement,
    resolve_effective_item_type,
)
from app.services.orchestrator.policies import (
    build_clarification_message,
    build_empty_message,
    build_empty_results_message,
    build_guardrail_plan,
    build_invalid_request_message,
    build_invalid_tool_payload_message,
    build_tool_failure_message,
    build_tool_timeout_message,
    missing_core_constraint_slots,
    next_missing_core_constraint_slot,
)

RecommendationExecutor = Callable[[RecommendationQuery], RecommendationToolResponse]
AgentExecutor = Callable[[list[dict[str, str]]], dict[str, Any]]
RecommendationItemType = Literal["destination", "hotel", "flight"]

_VALID_ITEM_TYPES = {"destination", "hotel", "flight"}
_STATE_CONTEXT_PREFIX = "TRAVELTOM_SESSION_STATE_JSON:"
_DIRECT_QUERY_PREFIX = "TRAVELTOM_DIRECT_RECOMMENDATION_QUERY_JSON:"
_RECOMMENDATION_CONTEXT_PREFIX = "TRAVELTOM_RECOMMENDATION_CONTEXT_JSON:"


def build_runtime_state_message(session_state: SessionState) -> str:
    """Serialize session state for agent-visible runtime context."""

    payload = session_state.model_dump(mode="json")
    return f"{_STATE_CONTEXT_PREFIX}\n{json.dumps(payload, sort_keys=True)}"


def extract_runtime_state(messages: Sequence[BaseMessage]) -> SessionState | None:
    """Extract session state from runtime context messages."""

    for message in messages:
        if getattr(message, "type", None) != "system":
            continue
        content = getattr(message, "content", "")
        if not isinstance(content, str) or not content.startswith(
            _STATE_CONTEXT_PREFIX
        ):
            continue
        raw_payload = content.removeprefix(_STATE_CONTEXT_PREFIX).strip()
        return SessionState.model_validate_json(raw_payload)
    return None


def build_runtime_recommendation_context_message(
    *,
    user_message: str,
    session_state: SessionState,
) -> str:
    """Serialize deterministic recommendation carry-forward context."""

    effective_item_type = resolve_effective_item_type(
        message=user_message,
        session_state=session_state,
    )
    weighted_interests = sorted(
        session_state.preferences.weighted_interests.items(),
        key=lambda item: (-item[1], item[0]),
    )
    payload = {
        "follow_up_refinement": is_follow_up_refinement(user_message),
        "effective_query": build_effective_recommendation_query_text(
            message=user_message,
            session_state=session_state,
        ),
        "effective_item_type": effective_item_type,
        "previous_item_type": session_state.conversation.last_recommendation_item_type,
        "previous_query": session_state.conversation.last_recommendation_query,
        "weighted_interests": [
            interest for interest, _weight in weighted_interests[:3]
        ],
    }
    return f"{_RECOMMENDATION_CONTEXT_PREFIX}\n{json.dumps(payload, sort_keys=True)}"


def extract_runtime_recommendation_context(
    messages: Sequence[BaseMessage],
) -> dict[str, Any]:
    """Extract recommendation carry-forward context from system messages."""

    for message in messages:
        if getattr(message, "type", None) != "system":
            continue
        content = getattr(message, "content", "")
        if not isinstance(content, str) or not content.startswith(
            _RECOMMENDATION_CONTEXT_PREFIX
        ):
            continue
        raw_payload = content.removeprefix(_RECOMMENDATION_CONTEXT_PREFIX).strip()
        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
    return {}


def build_direct_query_message(request: ApiRecommendationQuery) -> str:
    """Serialize a deterministic recommendation request for agent input."""

    payload = request.model_dump(mode="json")
    return f"{_DIRECT_QUERY_PREFIX}\n{json.dumps(payload, sort_keys=True)}"


def extract_direct_query(messages: Sequence[BaseMessage]) -> RecommendationQuery | None:
    """Extract a direct recommendation query from agent messages."""

    for message in reversed(messages):
        if getattr(message, "type", None) != "human":
            continue
        content = getattr(message, "content", "")
        if not isinstance(content, str) or not content.startswith(_DIRECT_QUERY_PREFIX):
            continue
        raw_payload = content.removeprefix(_DIRECT_QUERY_PREFIX).strip()
        return RecommendationQuery.model_validate_json(raw_payload)
    return None


def placeholder_recommendation_tool(
    query: RecommendationQuery,
) -> RecommendationToolResponse:
    """Temporary recommendation tool used until recommender integration is ready."""

    return RecommendationToolResponse(
        results=[],
        ranking_version=query.ranking_version,
    )


class OrchestratorService:
    """Coordinate chat-agent invocation and deterministic fallback behavior."""

    def __init__(
        self,
        policy_config: OrchestratorPolicyConfig | None = None,
    ) -> None:
        self._policy = policy_config or OrchestratorPolicyConfig()

    def build_chat_messages(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        recent_messages: Sequence[TranscriptMessage] | None = None,
    ) -> list[dict[str, str]]:
        """Build agent inputs from hidden runtime context plus recent transcript."""

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": build_runtime_state_message(session_state),
            },
            {
                "role": "system",
                "content": build_runtime_recommendation_context_message(
                    user_message=user_message,
                    session_state=session_state,
                ),
            },
        ]
        for transcript_message in recent_messages or []:
            messages.append(
                {
                    "role": transcript_message.role,
                    "content": transcript_message.content,
                }
            )
        messages.append({"role": "user", "content": user_message})
        return messages

    def handle_message(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        recent_messages: Sequence[TranscriptMessage] | None = None,
        agent_executor: AgentExecutor,
        recommendation_executor: RecommendationExecutor | None = None,
    ) -> OrchestratorResponse:
        """Run the chat agent and normalize the transcript into API output."""

        message = user_message.strip()
        history = list(recent_messages or [])
        if not message:
            return self._clarification_response(
                session_state=session_state,
                assistant_message=build_empty_message(session_state),
                intent="clarify",
                requested_slots=session_state.conversation.last_requested_slots,
            )

        prepared_state = apply_message_state_updates(
            message=message,
            session_state=session_state,
        )
        acknowledged_slots = self._captured_core_slots(
            previous_state=session_state,
            next_state=prepared_state,
        )

        try:
            agent_result = agent_executor(
                self.build_chat_messages(
                    user_message=message,
                    session_state=prepared_state,
                    recent_messages=history,
                )
            )
        except Exception:
            return self._fallback_from_agent_failure(
                user_message=message,
                session_state=prepared_state,
                previous_state=session_state,
                acknowledged_slots=acknowledged_slots,
                recommendation_executor=recommendation_executor,
            )

        return self._response_from_agent_result(
            user_message=message,
            session_state=prepared_state,
            previous_state=session_state,
            acknowledged_slots=acknowledged_slots,
            agent_result=agent_result,
        )

    def response_from_direct_agent_result(
        self,
        *,
        agent_result: dict[str, Any],
    ) -> RecommendationToolRuntimePayload:
        """Extract the tool payload from a deterministic recommendation agent."""

        tool_message = self._last_recommendation_tool_message(agent_result)
        if tool_message is None:
            return RecommendationToolRuntimePayload(
                status="failure",
                error_code="missing_tool_call",
                error_message="Agent did not execute recommendation_query",
            )

        artifact = getattr(tool_message, "artifact", None)
        if artifact is not None:
            return RecommendationToolRuntimePayload.model_validate(artifact)

        return RecommendationToolRuntimePayload(
            status="failure",
            error_code="missing_tool_payload",
            error_message="Recommendation tool did not return a runtime payload",
        )

    def build_recommendation_query(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        max_results: int | None = None,
    ) -> RecommendationQuery | None:
        """Build a normalized recommendation query from state and user text."""

        effective_query = build_effective_recommendation_query_text(
            message=user_message,
            session_state=session_state,
        )
        payload: dict[str, Any] = {
            "session_id": session_state.session_id,
            "query": effective_query,
            "constraints": self._build_constraints_payload(session_state),
            "filters": self._merge_query_filters(
                user_message=user_message,
                session_state=session_state,
            ),
            "max_results": max_results or self._policy.max_recommendation_results,
            "ranking_version": "heuristic-v1",
        }
        try:
            return RecommendationQuery.model_validate(payload)
        except ValidationError:
            return None

    def build_results_message(
        self,
        results: list[RecommendationResult],
    ) -> str:
        """Build deterministic grounded copy from recommendation results."""

        preview_limit = max(1, self._policy.max_recommendation_results)
        preview_items = "\n".join(
            f"{i}. {self._recommendation_display_name(item)}"
            for i, item in enumerate(results[:preview_limit], start=1)
        )
        return (
            f"I found {len(results)} grounded option(s) that fit what you asked for. "
            f"My top picks are:\n{preview_items}"
        )

    def _response_from_agent_result(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        previous_state: SessionState,
        acknowledged_slots: list[str],
        agent_result: dict[str, Any],
    ) -> OrchestratorResponse:
        messages = self._messages_from_agent_result(agent_result)
        final_ai_message = self._last_final_ai_message(messages)
        tool_message = self._last_recommendation_tool_message(agent_result)

        if tool_message is None:
            intent = self._conversation_intent(
                previous_state=previous_state,
                next_state=session_state,
                planned_intent="clarify",
            )
            fallback = build_clarification_message(
                session_state,
                acknowledged_slots=acknowledged_slots or None,
            )
            assistant_message = self._assistant_message_or_fallback(
                final_ai_message,
                fallback,
            )
            requested_slot = next_missing_core_constraint_slot(session_state)
            return self._clarification_response(
                session_state=session_state,
                assistant_message=assistant_message,
                intent=intent,
                requested_slots=[requested_slot] if requested_slot else [],
            )

        if getattr(tool_message, "status", "success") == "error":
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=build_invalid_request_message(session_state),
                intent=self._turn_intent(previous_state, user_message, session_state),
            )

        runtime_payload = RecommendationToolRuntimePayload.model_validate(
            getattr(tool_message, "artifact", None)
        )
        if runtime_payload.status == "timeout":
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=build_tool_timeout_message(),
                intent=self._turn_intent(previous_state, user_message, session_state),
            )
        if runtime_payload.status == "invalid_payload":
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=build_invalid_tool_payload_message(),
                intent=self._turn_intent(previous_state, user_message, session_state),
            )
        if runtime_payload.status != "success" or runtime_payload.response is None:
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=build_tool_failure_message(),
                intent=self._turn_intent(previous_state, user_message, session_state),
            )

        recommendation_response = runtime_payload.response
        tool_call = self._last_recommendation_tool_call(messages)
        next_state = session_state.model_copy(deep=True)
        next_state.last_message_at = datetime.now(timezone.utc)
        next_state.last_recommendation_version = recommendation_response.ranking_version
        next_state.conversation.last_requested_slots = []
        next_state.conversation.last_user_intent = self._turn_intent(
            previous_state,
            user_message,
            session_state,
        )
        effective_item_type: RecommendationItemType | None = (
            self._extract_tool_call_item_type(tool_call)
        )
        if effective_item_type is None:
            resolved_item_type = resolve_effective_item_type(
                message=user_message,
                session_state=session_state,
            )
            effective_item_type = self._normalize_item_type(resolved_item_type)
        next_state.conversation.last_recommendation_item_type = effective_item_type
        next_state.conversation.last_recommendation_query = (
            self._extract_tool_call_query(tool_call)
            or build_effective_recommendation_query_text(
                message=user_message,
                session_state=session_state,
            )
        )

        if not recommendation_response.results:
            next_state.status = "explore"
            fallback = build_empty_results_message(next_state)
            assistant_message = self._assistant_message_or_fallback(
                final_ai_message,
                fallback,
            )
            return OrchestratorResponse(
                session_id=next_state.session_id,
                assistant_message=assistant_message,
                recommendations=[],
                itinerary=next_state.itinerary.model_dump(),
                state=next_state.model_dump(mode="json"),
            )

        next_state.status = "refine"
        fallback = self.build_results_message(recommendation_response.results)
        assistant_message = self._assistant_message_or_fallback(
            final_ai_message,
            fallback,
        )
        return OrchestratorResponse(
            session_id=next_state.session_id,
            assistant_message=assistant_message,
            recommendations=recommendation_response.results,
            itinerary=next_state.itinerary.model_dump(),
            state=next_state.model_dump(mode="json"),
        )

    def _fallback_from_agent_failure(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        previous_state: SessionState,
        acknowledged_slots: list[str],
        recommendation_executor: RecommendationExecutor | None,
    ) -> OrchestratorResponse:
        fallback_plan = build_guardrail_plan(
            message=user_message,
            session_state=session_state,
            max_results=self._policy.max_recommendation_results,
        )
        if not fallback_plan.should_call_recommendation_tool:
            conversation_intent = self._conversation_intent(
                previous_state=previous_state,
                next_state=session_state,
                planned_intent=fallback_plan.intent,
            )
            requested_slot = next_missing_core_constraint_slot(session_state)
            return self._clarification_response(
                session_state=session_state,
                assistant_message=build_clarification_message(
                    session_state,
                    acknowledged_slots=acknowledged_slots or None,
                ),
                intent=conversation_intent,
                requested_slots=[requested_slot] if requested_slot else [],
            )

        if recommendation_executor is None:
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=build_tool_failure_message(),
                intent=self._turn_intent(previous_state, user_message, session_state),
            )

        query = self.build_recommendation_query(
            user_message=user_message,
            session_state=session_state,
            max_results=fallback_plan.query_controls.max_results,
        )
        if query is None:
            requested_slot = next_missing_core_constraint_slot(session_state)
            return self._clarification_response(
                session_state=session_state,
                assistant_message=build_invalid_request_message(session_state),
                intent=self._conversation_intent(
                    previous_state=previous_state,
                    next_state=session_state,
                    planned_intent="clarify",
                ),
                requested_slots=[requested_slot] if requested_slot else [],
            )

        try:
            recommendation_response = RecommendationToolResponse.model_validate(
                recommendation_executor(query)
            )
        except ValidationError:
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=build_invalid_tool_payload_message(),
                intent=self._turn_intent(previous_state, user_message, session_state),
            )
        except Exception:
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=build_tool_failure_message(),
                intent=self._turn_intent(previous_state, user_message, session_state),
            )

        next_state = session_state.model_copy(deep=True)
        next_state.last_message_at = datetime.now(timezone.utc)
        next_state.last_recommendation_version = recommendation_response.ranking_version
        next_state.conversation.last_requested_slots = []
        next_state.conversation.last_user_intent = self._turn_intent(
            previous_state,
            user_message,
            session_state,
        )
        next_state.conversation.last_recommendation_item_type = (
            query.filters.get("item_type")
            if isinstance(query.filters.get("item_type"), str)
            else None
        )
        next_state.conversation.last_recommendation_query = query.query

        if not recommendation_response.results:
            next_state.status = "explore"
            return OrchestratorResponse(
                session_id=next_state.session_id,
                assistant_message=build_empty_results_message(next_state),
                recommendations=[],
                itinerary=next_state.itinerary.model_dump(),
                state=next_state.model_dump(mode="json"),
            )

        next_state.status = "refine"
        return OrchestratorResponse(
            session_id=next_state.session_id,
            assistant_message=self.build_results_message(
                recommendation_response.results
            ),
            recommendations=recommendation_response.results,
            itinerary=next_state.itinerary.model_dump(),
            state=next_state.model_dump(mode="json"),
        )

    def _build_constraints_payload(self, session_state: SessionState) -> dict[str, Any]:
        constraints: dict[str, Any] = {}
        if session_state.constraints.origin:
            constraints["origin"] = session_state.constraints.origin
        if session_state.constraints.destination:
            constraints["destination"] = session_state.constraints.destination
        if session_state.constraints.dates:
            constraints["dates"] = session_state.constraints.dates.model_dump(
                mode="json"
            )
        if session_state.constraints.budget:
            constraints["budget"] = session_state.constraints.budget.model_dump(
                mode="json"
            )
        if session_state.constraints.party_size:
            constraints["party_size"] = (
                session_state.constraints.party_size.model_dump()
            )
        return constraints

    def _merge_query_filters(
        self,
        *,
        user_message: str,
        session_state: SessionState,
    ) -> dict[str, str]:
        item_type = extract_query_filters(user_message).get("item_type")
        normalized_item_type = self._normalize_item_type(item_type)
        if normalized_item_type is not None:
            return {"item_type": normalized_item_type}

        remembered_item_type = resolve_effective_item_type(
            message=user_message,
            session_state=session_state,
        )
        normalized_remembered_item_type = self._normalize_item_type(
            remembered_item_type
        )
        if normalized_remembered_item_type is not None:
            return {"item_type": normalized_remembered_item_type}
        return {}

    def _normalize_item_type(
        self,
        item_type: Any,
    ) -> RecommendationItemType | None:
        if not isinstance(item_type, str):
            return None
        normalized = item_type.strip().casefold()
        if normalized.endswith("s"):
            normalized = normalized[:-1]
        if normalized in _VALID_ITEM_TYPES:
            return cast(RecommendationItemType, normalized)
        return None

    def _recommendation_display_name(self, item: RecommendationResult) -> str:
        name = item.features.get("name")
        if isinstance(name, str):
            normalized = name.strip()
            if normalized:
                return normalized
        return item.item_id

    def _assistant_message_or_fallback(
        self,
        final_ai_message: AIMessage | None,
        fallback_message: str,
    ) -> str:
        if final_ai_message is None:
            return fallback_message
        content = final_ai_message.text.strip()
        return content or fallback_message

    def _messages_from_agent_result(
        self,
        agent_result: dict[str, Any],
    ) -> list[BaseMessage]:
        raw_messages = agent_result.get("messages")
        if not isinstance(raw_messages, list):
            return []
        return [message for message in raw_messages if isinstance(message, BaseMessage)]

    def _last_final_ai_message(
        self,
        messages: Sequence[BaseMessage],
    ) -> AIMessage | None:
        for message in reversed(messages):
            if not isinstance(message, AIMessage):
                continue
            if message.tool_calls:
                continue
            return message
        return None

    def _last_recommendation_tool_message(
        self,
        agent_result: dict[str, Any],
    ) -> ToolMessage | None:
        for message in reversed(self._messages_from_agent_result(agent_result)):
            if not isinstance(message, ToolMessage):
                continue
            if message.name == "recommendation_query":
                return message
        return None

    def _last_recommendation_tool_call(
        self,
        messages: Sequence[BaseMessage],
    ) -> dict[str, Any] | None:
        for message in reversed(messages):
            if not isinstance(message, AIMessage):
                continue
            for tool_call in reversed(message.tool_calls):
                if tool_call.get("name") == "recommendation_query":
                    return cast(dict[str, Any], tool_call)
        return None

    def _extract_tool_call_query(self, tool_call: dict[str, Any] | None) -> str | None:
        if tool_call is None:
            return None
        args = tool_call.get("args")
        if not isinstance(args, dict):
            return None
        query = args.get("query")
        if not isinstance(query, str):
            return None
        normalized = query.strip()
        return normalized or None

    def _extract_tool_call_item_type(
        self,
        tool_call: dict[str, Any] | None,
    ) -> RecommendationItemType | None:
        if tool_call is None:
            return None
        args = tool_call.get("args")
        if not isinstance(args, dict):
            return None
        filters = args.get("filters")
        if not isinstance(filters, dict):
            return None
        item_type = filters.get("item_type")
        return self._normalize_item_type(item_type)

    def _captured_core_slots(
        self,
        *,
        previous_state: SessionState,
        next_state: SessionState,
    ) -> list[str]:
        captured: list[str] = []
        if (
            not previous_state.constraints.destination
            and next_state.constraints.destination
        ):
            captured.append("destination")
        if not previous_state.constraints.dates and next_state.constraints.dates:
            captured.append("dates")
        if not previous_state.constraints.budget and next_state.constraints.budget:
            captured.append("budget")
        return captured

    def _conversation_intent(
        self,
        *,
        previous_state: SessionState,
        next_state: SessionState,
        planned_intent: Intent,
    ) -> Intent:
        if planned_intent != "clarify":
            return planned_intent

        prior_intent = previous_state.conversation.last_user_intent
        if prior_intent in {"recommend", "refine"} and missing_core_constraint_slots(
            next_state
        ):
            return prior_intent
        return planned_intent

    def _turn_intent(
        self,
        previous_state: SessionState,
        user_message: str,
        session_state: SessionState,
    ) -> Intent:
        if extract_query_filters(user_message):
            return "refine" if previous_state.status == "refine" else "recommend"
        if is_follow_up_refinement(user_message):
            return "refine"
        fallback_plan = build_guardrail_plan(
            message=user_message,
            session_state=session_state,
            max_results=self._policy.max_recommendation_results,
        )
        return self._conversation_intent(
            previous_state=previous_state,
            next_state=session_state,
            planned_intent=fallback_plan.intent,
        )

    def _clarification_response(
        self,
        *,
        session_state: SessionState,
        assistant_message: str,
        intent: Intent,
        requested_slots: list[str],
    ) -> OrchestratorResponse:
        next_state = session_state.model_copy(deep=True)
        next_state.status = "explore"
        next_state.last_message_at = datetime.now(timezone.utc)
        next_state.conversation.last_requested_slots = requested_slots
        next_state.conversation.last_user_intent = intent
        return OrchestratorResponse(
            session_id=next_state.session_id,
            assistant_message=assistant_message,
            recommendations=[],
            itinerary=next_state.itinerary.model_dump(),
            state=next_state.model_dump(mode="json"),
        )

    def _safe_error_response(
        self,
        *,
        session_state: SessionState,
        assistant_message: str,
        intent: Intent,
    ) -> OrchestratorResponse:
        next_state = session_state.model_copy(deep=True)
        next_state.last_message_at = datetime.now(timezone.utc)
        next_state.conversation.last_user_intent = intent
        return OrchestratorResponse(
            session_id=next_state.session_id,
            assistant_message=assistant_message,
            recommendations=[],
            itinerary=next_state.itinerary.model_dump(),
            state=next_state.model_dump(mode="json"),
        )
