"""LangChain-agent orchestration helpers and deterministic fallback logic."""

from __future__ import annotations

import json
from collections.abc import Mapping
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Sequence, cast

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import ValidationError

from app.schemas.api.recommendations import (
    RecommendationQuery as ApiRecommendationQuery,
)
from app.schemas.orchestrator import (
    Intent,
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
from app.services.orchestrator.decision_engine import RecommendationDecisionEngine
from app.services.orchestrator.extraction import (
    build_effective_recommendation_query_text,
    extract_query_filters,
    has_conversational_recommendation_signal,
    is_follow_up_refinement,
    is_unsupported_flight_request,
    is_unsupported_flight_route_reply,
    resolve_effective_item_type,
)
from app.services.orchestrator.policies import (
    build_clarification_message,
    build_empty_message,
    build_guardrail_plan,
    build_invalid_request_message,
    build_invalid_tool_payload_message,
    build_response_prompt_context,
    build_tool_failure_message,
    build_tool_timeout_message,
    clarification_kind_for_state,
    is_greeting,
    is_meta_question,
    is_repair_turn,
    missing_core_constraint_slots,
    requested_slots_for_clarification,
)
from app.services.orchestrator.recommendation_runner import RecommendationRunner
from app.services.orchestrator.response_assembler import ResponseAssembler
from app.services.orchestrator.runtime_types import (
    AgentRunResult,
    RecommendationOutcome,
)
from app.services.orchestrator.turn_preparer import TurnPreparer

RecommendationExecutor = Callable[[RecommendationQuery], RecommendationToolResponse]
AgentExecutor = Callable[[list[dict[str, str]]], dict[str, Any]]
PlannerExecutor = Callable[[str], Mapping[str, Any] | None]
ResponseComposer = Callable[[str], str | None]
RecommendationItemType = Literal["hotel", "restaurant", "activity"]

_VALID_ITEM_TYPES = {"hotel", "restaurant", "activity"}
_STATE_CONTEXT_PREFIX = "TRAVELTOM_SESSION_STATE_JSON:"
_DIRECT_QUERY_PREFIX = "TRAVELTOM_DIRECT_RECOMMENDATION_QUERY_JSON:"
_RECOMMENDATION_CONTEXT_PREFIX = "TRAVELTOM_RECOMMENDATION_CONTEXT_JSON:"


class PlannerExecutionError(RuntimeError):
    """Raised when planner execution fails after planner support was configured."""


def _normalize_item_type_value(item_type: Any) -> RecommendationItemType | None:
    if not isinstance(item_type, str):
        return None
    normalized = item_type.strip().casefold()
    if normalized.endswith("s"):
        normalized = normalized[:-1]
    if normalized in _VALID_ITEM_TYPES:
        return cast(RecommendationItemType, normalized)
    return None


def _normalize_text_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


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
    query_controls: RecommendationQueryControls | None = None,
) -> str:
    """Serialize effective recommendation carry-forward context."""

    effective_query = _normalize_text_value(
        query_controls.query if query_controls is not None else None
    )
    if effective_query is None:
        effective_query = build_effective_recommendation_query_text(
            message=user_message,
            session_state=session_state,
        )

    effective_item_type = _normalize_item_type_value(
        query_controls.filters.get("item_type") if query_controls is not None else None
    )
    if effective_item_type is None:
        effective_item_type = _normalize_item_type_value(
            resolve_effective_item_type(
                message=user_message,
                session_state=session_state,
            )
        )
    weighted_interests = sorted(
        session_state.preferences.weighted_interests.items(),
        key=lambda item: (-item[1], item[0]),
    )
    payload = {
        "follow_up_refinement": is_follow_up_refinement(user_message),
        "effective_query": effective_query,
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
        self._turn_preparer = TurnPreparer(policy=self._policy)
        self._decision_engine = RecommendationDecisionEngine()
        self._recommendation_runner = RecommendationRunner(
            policy=self._policy,
            turn_preparer=self._turn_preparer,
        )
        self._response_assembler = ResponseAssembler(policy=self._policy)

    def build_chat_messages(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        recent_messages: Sequence[TranscriptMessage] | None = None,
        query_controls: RecommendationQueryControls | None = None,
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
                    query_controls=query_controls,
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
        planner_executor: PlannerExecutor | None = None,
        recommendation_executor: RecommendationExecutor | None = None,
        response_composer: ResponseComposer | None = None,
    ) -> OrchestratorResponse:
        """Run the chat agent and normalize the transcript into API output."""

        message = user_message.strip()
        history = list(recent_messages or [])
        if not message:
            return self._clarification_response(
                previous_state=session_state,
                session_state=session_state,
                user_message=message,
                recent_messages=history,
                fallback_message=build_empty_message(session_state),
                final_ai_message=None,
                response_composer=response_composer,
                intent="clarify",
                requested_slots=session_state.conversation.last_requested_slots,
            )

        prepared_turn = self._turn_preparer.prepare_turn(
            user_message=message,
            previous_state=session_state,
            recent_messages=history,
            planner_executor=planner_executor,
        )
        prepared_turn = self._turn_preparer.enforce_recommendation_slot_gating(
            user_message=message,
            prepared_turn=prepared_turn,
        )
        prepared_state = prepared_turn.session_state
        acknowledged_slots = prepared_turn.acknowledged_slots
        routing_decision = self._decision_engine.decide(
            user_message=message,
            previous_state=session_state,
            session_state=prepared_state,
            prepared_turn=prepared_turn,
            recommendation_executor_available=recommendation_executor is not None,
        )
        if routing_decision.path == "direct_response":
            return self._direct_response_from_plan(
                user_message=message,
                session_state=prepared_state,
                previous_state=session_state,
                plan=prepared_turn.plan,
                acknowledged_slots=acknowledged_slots,
                recent_messages=history,
                recommendation_executor=recommendation_executor,
                response_composer=response_composer,
            )

        try:
            agent_result = AgentRunResult.from_raw(
                agent_executor(
                    self.build_chat_messages(
                        user_message=message,
                        session_state=prepared_state,
                        recent_messages=history,
                        query_controls=prepared_turn.plan.query_controls,
                    )
                )
            )
        except Exception:
            return self._fallback_from_agent_failure(
                user_message=message,
                session_state=prepared_state,
                previous_state=session_state,
                plan=prepared_turn.plan,
                acknowledged_slots=acknowledged_slots,
                recommendation_executor=recommendation_executor,
                recent_messages=history,
                response_composer=response_composer,
            )

        return self._response_from_agent_result(
            user_message=message,
            session_state=prepared_state,
            previous_state=session_state,
            plan=prepared_turn.plan,
            acknowledged_slots=acknowledged_slots,
            agent_result=agent_result,
            recent_messages=history,
            recommendation_executor=recommendation_executor,
            response_composer=response_composer,
        )

    def response_from_direct_agent_result(
        self,
        *,
        agent_result: AgentRunResult | dict[str, Any],
    ) -> RecommendationToolRuntimePayload:
        """Extract the tool payload from a deterministic recommendation agent."""

        if isinstance(agent_result, dict):
            agent_result = AgentRunResult.from_raw(agent_result)
        tool_message = agent_result.last_recommendation_tool_message()
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

    def _direct_response_from_plan(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        previous_state: SessionState,
        plan: LLMOrchestrationPlan,
        acknowledged_slots: list[str],
        recent_messages: Sequence[TranscriptMessage],
        recommendation_executor: RecommendationExecutor | None,
        response_composer: ResponseComposer | None,
    ) -> OrchestratorResponse:
        conversation_intent = self._turn_intent(
            previous_state,
            user_message,
            session_state,
            planned_intent=plan.intent,
        )
        if not plan.should_call_recommendation_tool:
            return self._clarification_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                recent_messages=recent_messages,
                fallback_message=plan.clarification_message
                or build_clarification_message(
                    session_state,
                    acknowledged_slots=acknowledged_slots or None,
                    message=user_message,
                ),
                final_ai_message=None,
                response_composer=response_composer,
                intent=conversation_intent,
                requested_slots=self._requested_slots_for_clarification(
                    session_state=session_state,
                    user_message=user_message,
                ),
                rebuild_clarification_from_state=True,
            )

        if recommendation_executor is None:
            return self._safe_error_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                assistant_message=build_tool_failure_message(),
                intent=conversation_intent,
            )

        return self._run_recommendation_fallback(
            user_message=user_message,
            session_state=session_state,
            previous_state=previous_state,
            recent_messages=recent_messages,
            recommendation_executor=recommendation_executor,
            max_results=(
                plan.query_controls.max_results
                or self._policy.max_recommendation_results
            ),
            query_text_override=plan.query_controls.query,
            filters_override=plan.query_controls.filters,
            response_composer=response_composer,
            intent=conversation_intent,
        )

    def build_recommendation_query(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        max_results: int | None = None,
        query_text_override: str | None = None,
        filters_override: Mapping[str, Any] | None = None,
    ) -> RecommendationQuery | None:
        """Build a normalized recommendation query from state and user text."""

        return self._recommendation_runner.build_query(
            user_message=user_message,
            session_state=session_state,
            max_results=max_results,
            query_text_override=query_text_override,
            filters_override=filters_override,
        )

    def _merge_query_filters(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        filters_override: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._turn_preparer.merge_query_filters(
            user_message=user_message,
            session_state=session_state,
            filters_override=filters_override,
        )

    def build_results_message(
        self,
        results: list[RecommendationResult],
        *,
        session_state: SessionState | None = None,
    ) -> str:
        """Build deterministic grounded copy from recommendation results."""

        return self._response_assembler.build_results_message(
            results,
            session_state=session_state,
        )

    def _response_from_agent_result(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        previous_state: SessionState,
        plan: LLMOrchestrationPlan,
        acknowledged_slots: list[str],
        agent_result: AgentRunResult,
        recent_messages: Sequence[TranscriptMessage],
        recommendation_executor: RecommendationExecutor | None,
        response_composer: ResponseComposer | None,
    ) -> OrchestratorResponse:
        final_ai_message = agent_result.last_final_ai_message()
        tool_message = agent_result.last_recommendation_tool_message()
        conversation_intent = self._turn_intent(
            previous_state,
            user_message,
            session_state,
            planned_intent=plan.intent,
        )

        if tool_message is None:
            if (
                plan.should_call_recommendation_tool
                and recommendation_executor is not None
            ):
                return self._run_recommendation_fallback(
                    user_message=user_message,
                    session_state=session_state,
                    previous_state=previous_state,
                    recent_messages=recent_messages,
                    recommendation_executor=recommendation_executor,
                    max_results=(
                        plan.query_controls.max_results
                        or self._policy.max_recommendation_results
                    ),
                    query_text_override=plan.query_controls.query,
                    filters_override=plan.query_controls.filters,
                    response_composer=response_composer,
                    intent=conversation_intent,
                )

            return self._clarification_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                recent_messages=recent_messages,
                fallback_message=plan.clarification_message
                or build_clarification_message(
                    session_state,
                    acknowledged_slots=acknowledged_slots or None,
                    message=user_message,
                ),
                final_ai_message=final_ai_message,
                response_composer=response_composer,
                intent=conversation_intent,
                requested_slots=self._requested_slots_for_clarification(
                    session_state=session_state,
                    user_message=user_message,
                ),
                rebuild_clarification_from_state=True,
            )

        if getattr(tool_message, "status", "success") == "error":
            return self._safe_error_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                assistant_message=build_invalid_request_message(session_state),
                intent=conversation_intent,
            )

        runtime_payload = RecommendationToolRuntimePayload.model_validate(
            getattr(tool_message, "artifact", None)
        )
        if runtime_payload.status == "timeout":
            return self._safe_error_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                assistant_message=build_tool_timeout_message(),
                intent=conversation_intent,
            )
        if runtime_payload.status == "invalid_payload":
            return self._safe_error_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                assistant_message=build_invalid_tool_payload_message(),
                intent=conversation_intent,
            )
        if runtime_payload.status != "success" or runtime_payload.response is None:
            return self._safe_error_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                assistant_message=build_tool_failure_message(),
                intent=conversation_intent,
            )

        recommendation_response = runtime_payload.response
        tool_call = agent_result.last_recommendation_tool_call()
        tool_query = self._extract_tool_call_query(tool_call)
        tool_filters = self._extract_tool_call_filters(tool_call) or dict(
            plan.query_controls.filters
        )
        effective_item_type: RecommendationItemType | None = (
            self._extract_tool_call_item_type(tool_call)
        )
        if effective_item_type is None:
            effective_item_type = self._normalize_item_type(
                plan.query_controls.filters.get("item_type")
            )
        if effective_item_type is None:
            resolved_item_type = resolve_effective_item_type(
                message=user_message,
                session_state=session_state,
            )
            effective_item_type = self._normalize_item_type(resolved_item_type)
        effective_query = (
            tool_query
            or self._normalize_query_override(plan.query_controls.query)
            or build_effective_recommendation_query_text(
                message=user_message,
                session_state=session_state,
            )
        )
        outcome = self._response_assembler.normalize_recommendation_outcome(
            previous_state=previous_state,
            session_state=session_state,
            user_message=user_message,
            recommendation_response=recommendation_response,
            recommendation_item_type=effective_item_type or "",
            recommendation_query=effective_query,
            allow_retry_on_duplicate=recommendation_executor is not None,
            candidate_message=final_ai_message.text if final_ai_message else None,
        )
        outcome.next_state.conversation.last_user_intent = conversation_intent
        if outcome.retry_with_expanded_results and recommendation_executor is not None:
            return self._run_recommendation_fallback(
                user_message=user_message,
                session_state=session_state,
                previous_state=previous_state,
                recent_messages=recent_messages,
                recommendation_executor=recommendation_executor,
                max_results=self._recommendation_runner.expanded_follow_up_max_results(
                    requested_max_results=plan.query_controls.max_results,
                    previous_state=previous_state,
                    user_message=user_message,
                ),
                query_text_override=tool_query or plan.query_controls.query,
                filters_override=tool_filters,
                response_composer=response_composer,
                intent=conversation_intent,
            )
        return self._orchestrator_response_from_recommendation_outcome(
            outcome=outcome,
            recent_messages=recent_messages,
            user_message=user_message,
            response_composer=response_composer,
        )

    def _fallback_from_agent_failure(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        previous_state: SessionState,
        plan: LLMOrchestrationPlan,
        acknowledged_slots: list[str],
        recommendation_executor: RecommendationExecutor | None,
        recent_messages: Sequence[TranscriptMessage],
        response_composer: ResponseComposer | None,
    ) -> OrchestratorResponse:
        conversation_intent = self._turn_intent(
            previous_state,
            user_message,
            session_state,
            planned_intent=plan.intent,
        )
        if not plan.should_call_recommendation_tool:
            return self._clarification_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                recent_messages=recent_messages,
                fallback_message=plan.clarification_message
                or build_clarification_message(
                    session_state,
                    acknowledged_slots=acknowledged_slots or None,
                    message=user_message,
                ),
                final_ai_message=None,
                response_composer=response_composer,
                intent=conversation_intent,
                requested_slots=self._requested_slots_for_clarification(
                    session_state=session_state,
                    user_message=user_message,
                ),
            )

        if recommendation_executor is None:
            return self._safe_error_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                assistant_message=build_tool_failure_message(),
                intent=conversation_intent,
            )

        return self._run_recommendation_fallback(
            user_message=user_message,
            session_state=session_state,
            previous_state=previous_state,
            recent_messages=recent_messages,
            recommendation_executor=recommendation_executor,
            max_results=(
                plan.query_controls.max_results
                or self._policy.max_recommendation_results
            ),
            query_text_override=plan.query_controls.query,
            filters_override=plan.query_controls.filters,
            response_composer=response_composer,
            intent=conversation_intent,
        )

    def _run_recommendation_fallback(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        previous_state: SessionState,
        recent_messages: Sequence[TranscriptMessage],
        recommendation_executor: RecommendationExecutor,
        max_results: int,
        query_text_override: str | None = None,
        filters_override: Mapping[str, Any] | None = None,
        response_composer: ResponseComposer | None,
        intent: Intent | None = None,
    ) -> OrchestratorResponse:
        effective_max_results = (
            self._recommendation_runner.expanded_follow_up_max_results(
                requested_max_results=max_results,
                previous_state=previous_state,
                user_message=user_message,
            )
        )
        query = self.build_recommendation_query(
            user_message=user_message,
            session_state=session_state,
            max_results=effective_max_results,
            query_text_override=query_text_override,
            filters_override=filters_override,
        )
        if query is None:
            return self._clarification_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                recent_messages=recent_messages,
                fallback_message=build_invalid_request_message(session_state),
                final_ai_message=None,
                response_composer=response_composer,
                intent=intent
                or self._turn_intent(previous_state, user_message, session_state),
                requested_slots=self._requested_slots_for_clarification(
                    session_state=session_state,
                    user_message=user_message,
                ),
                outcome="invalid_request",
            )

        try:
            execution_result = self._recommendation_runner.execute(
                query=query,
                recommendation_executor=recommendation_executor,
            )
        except ValidationError:
            return self._safe_error_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                assistant_message=build_invalid_tool_payload_message(),
                intent=intent
                or self._turn_intent(previous_state, user_message, session_state),
            )
        except FuturesTimeoutError:
            return self._safe_error_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                assistant_message=build_tool_timeout_message(),
                intent=intent
                or self._turn_intent(previous_state, user_message, session_state),
            )
        except Exception:
            return self._safe_error_response(
                previous_state=previous_state,
                session_state=session_state,
                user_message=user_message,
                assistant_message=build_tool_failure_message(),
                intent=intent
                or self._turn_intent(previous_state, user_message, session_state),
            )

        outcome = self._response_assembler.normalize_recommendation_outcome(
            previous_state=previous_state,
            session_state=session_state,
            user_message=user_message,
            recommendation_response=execution_result.response,
            recommendation_item_type=self._normalize_item_type(
                execution_result.query.filters.get("item_type")
            )
            or "",
            recommendation_query=execution_result.query.query,
            allow_retry_on_duplicate=False,
        )
        outcome.next_state.conversation.last_user_intent = intent or self._turn_intent(
            previous_state,
            user_message,
            session_state,
        )
        return self._orchestrator_response_from_recommendation_outcome(
            outcome=outcome,
            recent_messages=recent_messages,
            user_message=user_message,
            response_composer=response_composer,
        )

    def _normalize_item_type(
        self,
        item_type: Any,
    ) -> RecommendationItemType | None:
        return self._turn_preparer.normalize_item_type(item_type)

    def _normalize_query_override(self, query: Any) -> str | None:
        return self._turn_preparer.normalize_query_override(query)

    def _compose_assistant_message(
        self,
        *,
        session_state: SessionState,
        recent_messages: Sequence[TranscriptMessage],
        user_message: str,
        recommendations: list[RecommendationResult],
        fallback_message: str,
        outcome: Literal[
            "clarification", "results", "empty_results", "invalid_request"
        ],
        response_composer: ResponseComposer | None,
        candidate_message: str | None = None,
    ) -> str:
        normalized_candidate = _normalize_text_value(candidate_message)
        if (
            outcome == "clarification"
            and normalized_candidate is not None
            and not is_greeting(user_message)
            and not is_meta_question(user_message)
            and not is_repair_turn(user_message)
            and not session_state.conversation.last_requested_slots
        ):
            return normalized_candidate

        if response_composer is not None:
            prompt = build_response_prompt_context(
                session_state=session_state,
                recent_messages=list(recent_messages),
                user_message=user_message,
                recommendations=recommendations,
                fallback_message=fallback_message,
                outcome=outcome,
            )
            try:
                composed_message = response_composer(prompt)
            except Exception:
                composed_message = None
            if isinstance(composed_message, str):
                normalized = composed_message.strip()
                if normalized:
                    return normalized
            return fallback_message

        return fallback_message

    def _orchestrator_response_from_recommendation_outcome(
        self,
        *,
        outcome: RecommendationOutcome,
        recent_messages: Sequence[TranscriptMessage],
        user_message: str,
        response_composer: ResponseComposer | None,
    ) -> OrchestratorResponse:
        assistant_message = self._compose_assistant_message(
            session_state=outcome.next_state,
            recent_messages=recent_messages,
            user_message=user_message,
            recommendations=outcome.recommendations,
            fallback_message=outcome.fallback_message,
            outcome=cast(
                Literal["clarification", "results", "empty_results", "invalid_request"],
                outcome.outcome,
            ),
            response_composer=response_composer,
            candidate_message=outcome.candidate_message,
        )
        return OrchestratorResponse(
            session_id=outcome.next_state.session_id,
            assistant_message=assistant_message,
            recommendations=outcome.recommendations,
            itinerary=outcome.next_state.itinerary.model_dump(),
            state=outcome.next_state.model_dump(mode="json"),
        )

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

    def _extract_tool_call_filters(
        self,
        tool_call: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if tool_call is None:
            return None
        args = tool_call.get("args")
        if not isinstance(args, dict):
            return None
        filters = args.get("filters")
        if not isinstance(filters, dict):
            return None
        return dict(filters)

    def _captured_core_slots(
        self,
        *,
        previous_state: SessionState,
        next_state: SessionState,
    ) -> list[str]:
        return self._turn_preparer.captured_core_slots(
            previous_state=previous_state,
            next_state=next_state,
        )

    def _conversation_intent(
        self,
        *,
        previous_state: SessionState,
        next_state: SessionState,
        user_message: str,
        planned_intent: Intent,
    ) -> Intent:
        if planned_intent != "clarify":
            return planned_intent

        if is_greeting(user_message) or is_meta_question(user_message):
            return planned_intent

        prior_intent = previous_state.conversation.last_user_intent
        if (
            previous_state.conversation.last_clarification_kind == "refine_preference"
            and previous_state.conversation.last_search_outcome
            in {"empty_results", "no_new_results"}
        ):
            return prior_intent or "refine"
        if prior_intent in {"recommend", "refine"} and missing_core_constraint_slots(
            next_state
        ):
            return prior_intent
        if (
            prior_intent in {"recommend", "refine"}
            and clarification_kind_for_state(next_state) == "search_type"
        ):
            return prior_intent
        if self._has_trip_setup_context(next_state):
            return "recommend"
        if has_conversational_recommendation_signal(user_message):
            return "recommend"
        if is_unsupported_flight_request(
            user_message
        ) and previous_state.conversation.last_user_intent in {"recommend", "refine"}:
            return cast(Intent, previous_state.conversation.last_user_intent)
        return planned_intent

    def _turn_intent(
        self,
        previous_state: SessionState,
        user_message: str,
        session_state: SessionState,
        planned_intent: Intent | None = None,
    ) -> Intent:
        if planned_intent in {"recommend", "refine"}:
            return planned_intent
        if extract_query_filters(user_message):
            return "refine" if previous_state.status == "refine" else "recommend"
        if has_conversational_recommendation_signal(user_message):
            return "recommend"
        if is_unsupported_flight_request(
            user_message
        ) and previous_state.conversation.last_user_intent in {"recommend", "refine"}:
            return cast(Intent, previous_state.conversation.last_user_intent)
        if is_follow_up_refinement(user_message):
            return "refine"
        if planned_intent is not None:
            return self._conversation_intent(
                previous_state=previous_state,
                next_state=session_state,
                user_message=user_message,
                planned_intent=planned_intent,
            )
        fallback_plan = build_guardrail_plan(
            message=user_message,
            session_state=session_state,
            max_results=self._policy.max_recommendation_results,
        )
        return self._conversation_intent(
            previous_state=previous_state,
            next_state=session_state,
            user_message=user_message,
            planned_intent=fallback_plan.intent,
        )

    def _remember_pending_recommendation_context(
        self,
        *,
        next_state: SessionState,
        previous_state: SessionState,
        user_message: str,
        intent: Intent,
    ) -> None:
        if intent not in {"recommend", "refine"}:
            return

        remembered_item_type = self._normalize_item_type(
            resolve_effective_item_type(
                message=user_message,
                session_state=previous_state,
            )
        )
        if remembered_item_type is None:
            remembered_item_type = self._normalize_item_type(
                previous_state.conversation.last_recommendation_item_type
            )
        next_state.conversation.last_recommendation_item_type = remembered_item_type
        remembered_query = build_effective_recommendation_query_text(
            message=user_message,
            session_state=previous_state,
        )
        if remembered_query:
            next_state.conversation.last_recommendation_query = remembered_query
        else:
            next_state.conversation.last_recommendation_query = (
                previous_state.conversation.last_recommendation_query
            )

    def _requested_slots_for_clarification(
        self,
        *,
        session_state: SessionState,
        user_message: str,
    ) -> list[str]:
        if is_greeting(user_message):
            return []
        if is_unsupported_flight_request(
            user_message
        ) or is_unsupported_flight_route_reply(
            message=user_message,
            session_state=session_state,
        ):
            return []
        return requested_slots_for_clarification(session_state)

    def _clarification_response(
        self,
        *,
        previous_state: SessionState,
        session_state: SessionState,
        user_message: str,
        recent_messages: Sequence[TranscriptMessage],
        fallback_message: str,
        final_ai_message: AIMessage | None,
        response_composer: ResponseComposer | None,
        intent: Intent,
        requested_slots: list[str],
        outcome: Literal["clarification", "invalid_request"] = "clarification",
        rebuild_clarification_from_state: bool = False,
    ) -> OrchestratorResponse:
        next_state = session_state.model_copy(deep=True)
        next_state.status = "refine" if intent == "refine" else "explore"
        next_state.last_message_at = datetime.now(timezone.utc)
        next_state.conversation.last_requested_slots = requested_slots
        next_state.conversation.last_user_intent = intent
        self._remember_pending_recommendation_context(
            next_state=next_state,
            previous_state=previous_state,
            user_message=user_message,
            intent=intent,
        )
        if is_unsupported_flight_request(
            user_message
        ) or is_unsupported_flight_route_reply(
            message=user_message,
            session_state=previous_state,
        ):
            next_state.conversation.last_requested_slots = []
        else:
            next_state.conversation.last_requested_slots = (
                self._requested_slots_for_clarification(
                    session_state=next_state,
                    user_message=user_message,
                )
            )
        next_state.conversation.last_clarification_kind = clarification_kind_for_state(
            next_state
        )
        if next_state.conversation.last_clarification_kind != "refine_preference":
            next_state.conversation.last_search_outcome = None
        effective_fallback_message = fallback_message
        if (
            rebuild_clarification_from_state
            and outcome == "clarification"
            and user_message
            and not is_greeting(user_message)
            and not is_meta_question(user_message)
            and not is_repair_turn(user_message)
            and not is_unsupported_flight_request(user_message)
            and not is_unsupported_flight_route_reply(
                message=user_message,
                session_state=previous_state,
            )
        ):
            effective_fallback_message = build_clarification_message(
                next_state,
                acknowledged_slots=self._captured_core_slots(
                    previous_state=previous_state,
                    next_state=next_state,
                )
                or None,
                message=user_message,
            )
        assistant_message = self._compose_assistant_message(
            session_state=next_state,
            recent_messages=recent_messages,
            user_message=user_message,
            recommendations=[],
            fallback_message=effective_fallback_message,
            outcome=outcome,
            response_composer=response_composer,
            candidate_message=final_ai_message.text if final_ai_message else None,
        )
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
        previous_state: SessionState,
        session_state: SessionState,
        user_message: str,
        assistant_message: str,
        intent: Intent,
    ) -> OrchestratorResponse:
        next_state = session_state.model_copy(deep=True)
        next_state.last_message_at = datetime.now(timezone.utc)
        next_state.conversation.last_user_intent = intent
        self._remember_pending_recommendation_context(
            next_state=next_state,
            previous_state=previous_state,
            user_message=user_message,
            intent=intent,
        )
        next_state.conversation.last_clarification_kind = None
        return OrchestratorResponse(
            session_id=next_state.session_id,
            assistant_message=assistant_message,
            recommendations=[],
            itinerary=next_state.itinerary.model_dump(),
            state=next_state.model_dump(mode="json"),
        )

    def _has_trip_setup_context(self, session_state: SessionState) -> bool:
        return any(
            (
                session_state.constraints.origin,
                session_state.constraints.destination,
                session_state.constraints.dates,
                session_state.constraints.budget,
            )
        )
