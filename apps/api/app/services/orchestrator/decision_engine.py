"""Routing-decision phase for chat orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.state import SessionState
from app.services.orchestrator.policies import missing_core_constraint_slots
from app.services.orchestrator.runtime_types import PreparedTurn


@dataclass(frozen=True)
class RoutingDecision:
    """Normalized next execution path after turn preparation."""

    path: Literal["direct_response", "invoke_agent"]


class RecommendationDecisionEngine:
    """Decide whether a prepared turn needs agent execution."""

    def decide(
        self,
        *,
        user_message: str,
        previous_state: SessionState,
        session_state: SessionState,
        prepared_turn: PreparedTurn,
        recommendation_executor_available: bool,
    ) -> RoutingDecision:
        del user_message
        if not prepared_turn.plan.should_call_recommendation_tool:
            return RoutingDecision(path="direct_response")
        if (
            recommendation_executor_available
            and self._should_bypass_agent_for_recommendation(
                previous_state=previous_state,
                session_state=session_state,
            )
        ):
            return RoutingDecision(path="direct_response")
        return RoutingDecision(path="invoke_agent")

    def _should_bypass_agent_for_recommendation(
        self,
        *,
        previous_state: SessionState,
        session_state: SessionState,
    ) -> bool:
        if (
            previous_state.conversation.last_requested_slots
            and not missing_core_constraint_slots(session_state)
        ):
            return True
        return bool(
            previous_state.conversation.last_clarification_kind == "search_type"
            and not missing_core_constraint_slots(session_state)
        )
