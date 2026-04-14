"""Recommendation execution phase for chat orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from pydantic import ValidationError

from app.schemas.orchestrator import OrchestratorPolicyConfig
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationToolResponse,
)
from app.services.orchestrator.extraction import (
    build_effective_recommendation_query_text,
)
from app.services.orchestrator.policies import is_follow_up_refinement
from app.services.orchestrator.runtime_types import RecommendationExecutionResult
from app.services.orchestrator.turn_preparer import TurnPreparer

RecommendationExecutor = Callable[[RecommendationQuery], RecommendationToolResponse]


class RecommendationRunner:
    """Build and execute validated recommendation queries."""

    def __init__(
        self,
        *,
        policy: OrchestratorPolicyConfig,
        turn_preparer: TurnPreparer,
    ) -> None:
        self._policy = policy
        self._turn_preparer = turn_preparer

    def build_query(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        max_results: int | None = None,
        query_text_override: str | None = None,
        filters_override: Mapping[str, Any] | None = None,
    ) -> RecommendationQuery | None:
        effective_query = self._turn_preparer.normalize_query_override(
            query_text_override
        )
        if effective_query is None:
            effective_query = build_effective_recommendation_query_text(
                message=user_message,
                session_state=session_state,
            )
        payload: dict[str, Any] = {
            "session_id": session_state.session_id,
            "query": effective_query,
            "constraints": self._build_constraints_payload(session_state),
            "filters": self._turn_preparer.merge_query_filters(
                user_message=user_message,
                session_state=session_state,
                filters_override=filters_override,
            ),
            "max_results": max_results or self._policy.max_recommendation_results,
            "ranking_version": "heuristic-v1",
        }
        try:
            return RecommendationQuery.model_validate(payload)
        except ValidationError:
            return None

    def execute(
        self,
        *,
        query: RecommendationQuery,
        recommendation_executor: RecommendationExecutor,
    ) -> RecommendationExecutionResult:
        return RecommendationExecutionResult(
            query=query,
            response=RecommendationToolResponse.model_validate(
                recommendation_executor(query)
            ),
        )

    def expanded_follow_up_max_results(
        self,
        *,
        requested_max_results: int | None,
        previous_state: SessionState,
        user_message: str,
    ) -> int:
        base_max_results = (
            requested_max_results or self._policy.max_recommendation_results
        )
        if not self._is_duplicate_sensitive_follow_up(
            user_message=user_message,
            previous_state=previous_state,
        ):
            return base_max_results

        prior_result_count = len(
            previous_state.conversation.last_recommendation_result_ids
        )
        if prior_result_count <= 0:
            return base_max_results

        return min(50, max(1, base_max_results) + prior_result_count)

    def _is_duplicate_sensitive_follow_up(
        self,
        *,
        user_message: str,
        previous_state: SessionState,
    ) -> bool:
        if not previous_state.conversation.last_recommendation_result_ids:
            return False
        return is_follow_up_refinement(user_message)

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
            constraints[
                "party_size"
            ] = session_state.constraints.party_size.model_dump()
        return constraints
