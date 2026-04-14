"""Turn preparation phase for chat orchestration."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import ValidationError

from app.schemas.orchestrator import (
    LLMOrchestrationPlan,
    OrchestratorPolicyConfig,
    RecommendationQueryControls,
    TranscriptMessage,
)
from app.schemas.state import SessionState
from app.services.orchestrator.extraction import (
    apply_message_state_updates,
    apply_structured_state_patch,
    build_effective_recommendation_query_text,
    extract_query_filters,
    resolve_effective_item_type,
)
from app.services.orchestrator.policies import (
    build_clarification_message,
    build_guardrail_plan,
    build_planning_prompt_context,
    missing_core_constraint_slots,
)
from app.services.orchestrator.runtime_types import PreparedTurn

RecommendationItemType = Literal["destination", "hotel", "flight"]
_VALID_ITEM_TYPES = {"destination", "hotel", "flight"}
_PLANNER_FAILURE_COOLDOWN_SECONDS = 120
logger = logging.getLogger(__name__)


def _normalize_item_type_value(item_type: Any) -> RecommendationItemType | None:
    if not isinstance(item_type, str):
        return None
    normalized = item_type.strip().casefold()
    if normalized.endswith("s"):
        normalized = normalized[:-1]
    if normalized in _VALID_ITEM_TYPES:
        return normalized
    return None


def _normalize_text_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


class TurnPreparer:
    """Prepare validated turn state and planning metadata before routing."""

    def __init__(
        self,
        *,
        policy: OrchestratorPolicyConfig,
    ) -> None:
        self._policy = policy
        self._planner_cooldowns: dict[str, datetime] = {}

    def prepare_turn(
        self,
        *,
        user_message: str,
        previous_state: SessionState,
        recent_messages: Sequence[TranscriptMessage],
        planner_executor: Any | None,
    ) -> PreparedTurn:
        deterministic_state = apply_message_state_updates(
            message=user_message,
            session_state=previous_state,
        )
        acknowledged_slots = self.captured_core_slots(
            previous_state=previous_state,
            next_state=deterministic_state,
        )
        fallback_turn = PreparedTurn(
            session_state=deterministic_state,
            plan=self.normalize_planning_plan(
                user_message=user_message,
                previous_state=previous_state,
                session_state=deterministic_state,
                plan=build_guardrail_plan(
                    message=user_message,
                    session_state=deterministic_state,
                    max_results=self._policy.max_recommendation_results,
                ),
            ),
            acknowledged_slots=acknowledged_slots,
            planner_used=False,
        )
        if planner_executor is None:
            return fallback_turn

        if self._planner_is_in_cooldown(previous_state.session_id):
            return fallback_turn

        prompt = build_planning_prompt_context(
            session_state=previous_state,
            deterministic_hint_state=deterministic_state,
            recent_messages=list(recent_messages),
            user_message=user_message,
            max_results=self._policy.max_recommendation_results,
        )
        try:
            plan_payload = planner_executor(prompt)
        except Exception as exc:
            self._mark_planner_failure(previous_state.session_id)
            logger.warning(
                "planner_execution_failed",
                extra={
                    "context": {
                        "session_id": previous_state.session_id,
                        "error": str(exc),
                    }
                },
            )
            return fallback_turn
        if not isinstance(plan_payload, Mapping):
            self._mark_planner_failure(previous_state.session_id)
            logger.warning(
                "planner_output_invalid",
                extra={
                    "context": {
                        "session_id": previous_state.session_id,
                        "error": "planner output was not a JSON object",
                    }
                },
            )
            return fallback_turn

        normalized_plan_payload = self._sanitize_plan_payload(plan_payload)
        try:
            plan = LLMOrchestrationPlan.model_validate(normalized_plan_payload)
            planned_state = apply_structured_state_patch(
                session_state=previous_state,
                state_patch=plan.state_patch.model_dump(
                    mode="python",
                    exclude_unset=True,
                ),
            )
        except ValidationError as exc:
            self._mark_planner_failure(previous_state.session_id)
            logger.warning(
                "planner_output_invalid",
                extra={
                    "context": {
                        "session_id": previous_state.session_id,
                        "error": str(exc),
                    }
                },
            )
            return fallback_turn

        self._clear_planner_cooldown(previous_state.session_id)

        return PreparedTurn(
            session_state=planned_state,
            plan=self.normalize_planning_plan(
                user_message=user_message,
                previous_state=previous_state,
                session_state=planned_state,
                plan=plan,
            ),
            acknowledged_slots=self.captured_core_slots(
                previous_state=previous_state,
                next_state=planned_state,
            ),
            planner_used=True,
        )

    def enforce_recommendation_slot_gating(
        self,
        *,
        user_message: str,
        prepared_turn: PreparedTurn,
    ) -> PreparedTurn:
        if not prepared_turn.plan.should_call_recommendation_tool:
            return prepared_turn

        item_type_override = prepared_turn.plan.query_controls.filters.get("item_type")
        missing_slots = missing_core_constraint_slots(
            prepared_turn.session_state,
            item_type_override=str(item_type_override) if item_type_override else None,
        )
        if not missing_slots:
            return prepared_turn

        gated_plan = LLMOrchestrationPlan(
            intent="clarify",
            should_call_recommendation_tool=False,
            clarification_message=build_clarification_message(
                prepared_turn.session_state,
                acknowledged_slots=prepared_turn.acknowledged_slots or None,
                message=user_message,
            ),
            state_patch=prepared_turn.plan.state_patch,
            query_controls=prepared_turn.plan.query_controls,
        )
        return PreparedTurn(
            session_state=prepared_turn.session_state,
            plan=gated_plan,
            acknowledged_slots=prepared_turn.acknowledged_slots,
            planner_used=prepared_turn.planner_used,
        )

    def merge_query_filters(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        filters_override: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged_filters: dict[str, Any] = {}
        if filters_override:
            for key, value in filters_override.items():
                if key == "item_type":
                    normalized_override = self.normalize_item_type(value)
                    if normalized_override is not None:
                        merged_filters[key] = normalized_override
                    continue
                merged_filters[key] = value
        if "item_type" in merged_filters:
            return merged_filters

        item_type = extract_query_filters(user_message).get("item_type")
        normalized_item_type = self.normalize_item_type(item_type)
        if normalized_item_type is not None:
            merged_filters["item_type"] = normalized_item_type
            return merged_filters

        remembered_item_type = resolve_effective_item_type(
            message=user_message,
            session_state=session_state,
        )
        normalized_remembered_item_type = self.normalize_item_type(remembered_item_type)
        if normalized_remembered_item_type is not None:
            merged_filters["item_type"] = normalized_remembered_item_type
            return merged_filters

        merged_filters["item_type"] = "destination"
        return merged_filters

    def normalize_item_type(self, item_type: Any) -> RecommendationItemType | None:
        return _normalize_item_type_value(item_type)

    def normalize_query_override(self, query: Any) -> str | None:
        return _normalize_text_value(query)

    def captured_core_slots(
        self,
        *,
        previous_state: SessionState,
        next_state: SessionState,
    ) -> list[str]:
        captured: list[str] = []
        if not previous_state.constraints.origin and next_state.constraints.origin:
            captured.append("origin")
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

    def normalize_planning_plan(
        self,
        *,
        user_message: str,
        previous_state: SessionState,
        session_state: SessionState,
        plan: LLMOrchestrationPlan,
    ) -> LLMOrchestrationPlan:
        max_results = min(
            plan.query_controls.max_results or self._policy.max_recommendation_results,
            self._policy.max_recommendation_results,
        )
        effective_query = self.normalize_query_override(plan.query_controls.query)
        if effective_query is None:
            effective_query = build_effective_recommendation_query_text(
                message=user_message,
                session_state=session_state,
            )

        filters = self.merge_query_filters(
            user_message=user_message,
            session_state=session_state,
            filters_override=plan.query_controls.filters,
        )
        guardrail_plan = build_guardrail_plan(
            message=user_message,
            session_state=session_state,
            max_results=max_results,
        )

        should_call_recommendation_tool = plan.should_call_recommendation_tool
        if guardrail_plan.should_call_recommendation_tool:
            should_call_recommendation_tool = True
        elif plan.should_call_recommendation_tool:
            should_call_recommendation_tool = False

        intent = plan.intent
        if should_call_recommendation_tool and intent == "clarify":
            if guardrail_plan.intent in {"recommend", "refine"}:
                intent = guardrail_plan.intent
            else:
                intent = "recommend"

        clarification_message = _normalize_text_value(plan.clarification_message)
        if should_call_recommendation_tool:
            clarification_message = None
        elif clarification_message is None:
            clarification_message = (
                guardrail_plan.clarification_message
                or build_clarification_message(
                    session_state,
                    acknowledged_slots=self.captured_core_slots(
                        previous_state=previous_state,
                        next_state=session_state,
                    )
                    or None,
                    message=user_message,
                )
            )

        return LLMOrchestrationPlan(
            intent=intent,
            should_call_recommendation_tool=should_call_recommendation_tool,
            clarification_message=clarification_message,
            state_patch=plan.state_patch,
            query_controls=RecommendationQueryControls(
                query=effective_query,
                filters=filters,
                max_results=max_results,
            ),
        )

    def _planner_is_in_cooldown(self, session_id: str) -> bool:
        cooldown_until = self._planner_cooldowns.get(session_id)
        if cooldown_until is None:
            return False
        if cooldown_until <= datetime.now(timezone.utc):
            self._planner_cooldowns.pop(session_id, None)
            return False
        return True

    def _mark_planner_failure(self, session_id: str) -> None:
        self._planner_cooldowns[session_id] = datetime.now(timezone.utc) + timedelta(
            seconds=_PLANNER_FAILURE_COOLDOWN_SECONDS
        )

    def _clear_planner_cooldown(self, session_id: str) -> None:
        self._planner_cooldowns.pop(session_id, None)

    def _sanitize_plan_payload(
        self,
        plan_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized_payload = dict(plan_payload)
        state_patch = normalized_payload.get("state_patch")
        if isinstance(state_patch, Mapping):
            normalized_payload["state_patch"] = self._prune_null_patch_values(
                dict(state_patch)
            )
        return normalized_payload

    def _prune_null_patch_values(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            cleaned: dict[str, Any] = {}
            for key, nested_value in value.items():
                normalized_nested_value = self._prune_null_patch_values(nested_value)
                if normalized_nested_value is None:
                    continue
                if (
                    isinstance(normalized_nested_value, dict)
                    and not normalized_nested_value
                ):
                    continue
                cleaned[str(key)] = normalized_nested_value
            return cleaned
        if isinstance(value, list):
            cleaned_list = [self._prune_null_patch_values(item) for item in value]
            return [
                item
                for item in cleaned_list
                if item is not None and not (isinstance(item, dict) and not item)
            ]
        return value
