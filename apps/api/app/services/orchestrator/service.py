"""Planner/composer orchestration helpers and deterministic fallback logic."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Sequence

from langchain_core.messages import BaseMessage, ToolMessage
from pydantic import ValidationError

from app.schemas.api.recommendations import (
    RecommendationQuery as ApiRecommendationQuery,
)
from app.schemas.orchestrator import (
    LLMComposedResponse,
    LLMOrchestrationPlan,
    OrchestratorPolicyConfig,
    OrchestratorResponse,
    RecommendationQueryControls,
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
    apply_structured_state_patch,
    extract_query_filters,
)
from app.services.orchestrator.policies import (
    build_clarification_message,
    build_empty_message,
    build_empty_results_message,
    build_guardrail_plan,
    build_invalid_request_message,
    build_invalid_tool_payload_message,
    build_planning_prompt_context,
    build_response_prompt_context,
    build_tool_failure_message,
    build_tool_timeout_message,
    missing_core_constraint_slots,
    next_missing_core_constraint_slot,
)

RecommendationExecutor = Callable[[RecommendationQuery], RecommendationToolResponse]
PlannerExecutor = Callable[[str], LLMOrchestrationPlan]
ComposerExecutor = Callable[[str], LLMComposedResponse]
ComposerOutcome = Literal["clarification", "results", "empty_results", "invalid_request"]

_VALID_ITEM_TYPES = {"destination", "hotel", "flight"}
_STATE_CONTEXT_PREFIX = "TRAVELTOM_SESSION_STATE_JSON:"
_DIRECT_QUERY_PREFIX = "TRAVELTOM_DIRECT_RECOMMENDATION_QUERY_JSON:"


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
    """Coordinate planning, recommendation execution, and grounded responses."""

    def __init__(
        self,
        policy_config: OrchestratorPolicyConfig | None = None,
    ) -> None:
        self._policy = policy_config or OrchestratorPolicyConfig()

    def handle_message(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        recent_messages: Sequence[TranscriptMessage] | None = None,
        planner_executor: PlannerExecutor | None = None,
        composer_executor: ComposerExecutor | None = None,
        recommendation_executor: RecommendationExecutor | None = None,
    ) -> OrchestratorResponse:
        """Run the planner/composer loop and normalize the result into API output."""

        message = user_message.strip()
        history = list(recent_messages or [])
        if not message:
            return self._clarification_response(
                session_state=session_state,
                assistant_message=build_empty_message(session_state),
                intent="clarify",
                requested_slots=session_state.conversation.last_requested_slots,
            )

        extracted_state = apply_message_state_updates(
            message=message,
            session_state=session_state,
        )
        acknowledged_slots = self._captured_core_slots(
            previous_state=session_state,
            next_state=extracted_state,
        )
        planned_state = extracted_state
        plan = self._plan_turn(
            user_message=message,
            session_state=extracted_state,
            recent_messages=history,
            planner_executor=planner_executor,
        )

        if plan.state_patch:
            planned_state = self._merge_state_patch(
                session_state=extracted_state,
                state_patch=plan.state_patch.model_dump(mode="python", exclude_none=True),
            )

        if plan.should_call_recommendation_tool and missing_core_constraint_slots(
            planned_state
        ):
            plan = build_guardrail_plan(
                message=message,
                session_state=planned_state,
                max_results=self._policy.max_recommendation_results,
            )

        if not plan.should_call_recommendation_tool:
            conversation_intent = self._conversation_intent(
                previous_state=session_state,
                next_state=planned_state,
                planned_intent=plan.intent,
            )
            if acknowledged_slots:
                fallback_message = build_clarification_message(
                    planned_state,
                    acknowledged_slots=acknowledged_slots,
                )
            else:
                fallback_message = (
                    plan.clarification_message
                    or build_clarification_message(planned_state)
                )
            assistant_message = self._compose_or_fallback(
                session_state=planned_state,
                recent_messages=history,
                user_message=message,
                recommendations=[],
                fallback_message=fallback_message,
                outcome="clarification",
                composer_executor=composer_executor,
            )
            requested_slot = next_missing_core_constraint_slot(planned_state)
            return self._clarification_response(
                session_state=planned_state,
                assistant_message=assistant_message,
                intent=conversation_intent,
                requested_slots=[requested_slot] if requested_slot else [],
            )

        if recommendation_executor is None:
            return self._safe_error_response(
                session_state=planned_state,
                assistant_message=build_tool_failure_message(),
                intent=plan.intent,
            )

        query = self.build_recommendation_query(
            user_message=message,
            session_state=planned_state,
            query_controls=plan.query_controls,
        )
        if query is None:
            conversation_intent = self._conversation_intent(
                previous_state=session_state,
                next_state=planned_state,
                planned_intent="clarify",
            )
            fallback_message = build_invalid_request_message(planned_state)
            assistant_message = self._compose_or_fallback(
                session_state=planned_state,
                recent_messages=history,
                user_message=message,
                recommendations=[],
                fallback_message=fallback_message,
                outcome="invalid_request",
                composer_executor=composer_executor,
            )
            requested_slot = next_missing_core_constraint_slot(planned_state)
            return self._clarification_response(
                session_state=planned_state,
                assistant_message=assistant_message,
                intent=conversation_intent,
                requested_slots=[requested_slot] if requested_slot else [],
            )

        try:
            recommendation_response = RecommendationToolResponse.model_validate(
                recommendation_executor(query)
            )
        except ValidationError:
            return self._safe_error_response(
                session_state=planned_state,
                assistant_message=build_invalid_tool_payload_message(),
                intent=plan.intent,
            )
        except Exception:
            return self._safe_error_response(
                session_state=planned_state,
                assistant_message=build_tool_failure_message(),
                intent=plan.intent,
            )

        next_state = planned_state.model_copy(deep=True)
        next_state.last_message_at = datetime.now(timezone.utc)
        next_state.last_recommendation_version = recommendation_response.ranking_version
        next_state.conversation.last_requested_slots = []
        next_state.conversation.last_user_intent = plan.intent

        if not recommendation_response.results:
            next_state.status = "explore"
            fallback_message = build_empty_results_message(next_state)
            assistant_message = self._compose_or_fallback(
                session_state=next_state,
                recent_messages=history,
                user_message=message,
                recommendations=[],
                fallback_message=fallback_message,
                outcome="empty_results",
                composer_executor=composer_executor,
            )
            return OrchestratorResponse(
                session_id=next_state.session_id,
                assistant_message=assistant_message,
                recommendations=[],
                itinerary=next_state.itinerary.model_dump(),
                state=next_state.model_dump(mode="json"),
            )

        next_state.status = "refine"
        fallback_message = self.build_results_message(recommendation_response.results)
        assistant_message = self._compose_or_fallback(
            session_state=next_state,
            recent_messages=history,
            user_message=message,
            recommendations=recommendation_response.results,
            fallback_message=fallback_message,
            outcome="results",
            composer_executor=composer_executor,
        )
        return OrchestratorResponse(
            session_id=next_state.session_id,
            assistant_message=assistant_message,
            recommendations=recommendation_response.results,
            itinerary=next_state.itinerary.model_dump(),
            state=next_state.model_dump(mode="json"),
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
        query_controls: RecommendationQueryControls | None = None,
    ) -> RecommendationQuery | None:
        """Build a normalized recommendation query from state and plan output."""

        controls = query_controls or RecommendationQueryControls()
        query_text = controls.query.strip() if controls.query else user_message
        payload: dict[str, Any] = {
            "session_id": session_state.session_id,
            "query": query_text,
            "constraints": self._build_constraints_payload(session_state),
            "filters": self._merge_query_filters(
                user_message=user_message,
                planner_filters=controls.filters,
            ),
            "max_results": min(
                controls.max_results or self._policy.max_recommendation_results,
                self._policy.max_recommendation_results,
            ),
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

    def _plan_turn(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        recent_messages: list[TranscriptMessage],
        planner_executor: PlannerExecutor | None,
    ) -> LLMOrchestrationPlan:
        if planner_executor is None:
            return build_guardrail_plan(
                message=user_message,
                session_state=session_state,
                max_results=self._policy.max_recommendation_results,
            )

        try:
            return planner_executor(
                build_planning_prompt_context(
                    session_state=session_state,
                    recent_messages=recent_messages,
                    user_message=user_message,
                    max_results=self._policy.max_recommendation_results,
                )
            )
        except Exception:
            return build_guardrail_plan(
                message=user_message,
                session_state=session_state,
                max_results=self._policy.max_recommendation_results,
            )

    def _compose_or_fallback(
        self,
        *,
        session_state: SessionState,
        recent_messages: list[TranscriptMessage],
        user_message: str,
        recommendations: list[RecommendationResult],
        fallback_message: str,
        outcome: ComposerOutcome,
        composer_executor: ComposerExecutor | None,
    ) -> str:
        if composer_executor is None:
            return fallback_message

        try:
            response = composer_executor(
                build_response_prompt_context(
                    session_state=session_state,
                    recent_messages=recent_messages,
                    user_message=user_message,
                    recommendations=recommendations,
                    fallback_message=fallback_message,
                    outcome=outcome,
                )
            )
        except Exception:
            return fallback_message
        return response.assistant_message.strip() or fallback_message

    def _merge_state_patch(
        self,
        *,
        session_state: SessionState,
        state_patch: dict[str, Any],
    ) -> SessionState:
        try:
            return apply_structured_state_patch(
                session_state=session_state,
                state_patch=state_patch,
            )
        except ValidationError:
            return session_state.model_copy(deep=True)

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
        planner_filters: dict[str, Any],
    ) -> dict[str, str]:
        extracted_filters = extract_query_filters(user_message)
        normalized_item_type = self._normalize_item_type(
            extracted_filters.get("item_type")
        )
        if normalized_item_type is not None:
            return {"item_type": normalized_item_type}

        planner_item_type = self._normalize_item_type(planner_filters.get("item_type"))
        if planner_item_type is not None:
            return {"item_type": planner_item_type}
        return {}

    def _normalize_item_type(self, item_type: Any) -> str | None:
        if not isinstance(item_type, str):
            return None
        normalized = item_type.strip().casefold()
        if normalized.endswith("s"):
            normalized = normalized[:-1]
        if normalized in _VALID_ITEM_TYPES:
            return normalized
        return None

    def _recommendation_display_name(self, item: RecommendationResult) -> str:
        name = item.features.get("name")
        if isinstance(name, str):
            normalized = name.strip()
            if normalized:
                return normalized
        return item.item_id

    def _captured_core_slots(
        self,
        *,
        previous_state: SessionState,
        next_state: SessionState,
    ) -> list[str]:
        captured: list[str] = []
        if not previous_state.constraints.destination and next_state.constraints.destination:
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
        planned_intent: str,
    ) -> str:
        if planned_intent != "clarify":
            return planned_intent

        prior_intent = previous_state.conversation.last_user_intent
        if (
            prior_intent in {"recommend", "refine"}
            and missing_core_constraint_slots(next_state)
        ):
            return prior_intent
        return planned_intent

    def _messages_from_agent_result(
        self,
        agent_result: dict[str, Any],
    ) -> list[BaseMessage]:
        raw_messages = agent_result.get("messages")
        if not isinstance(raw_messages, list):
            return []
        return [message for message in raw_messages if isinstance(message, BaseMessage)]

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

    def _clarification_response(
        self,
        *,
        session_state: SessionState,
        assistant_message: str,
        intent: str,
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
        intent: str,
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
