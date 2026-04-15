"""Recommendation outcome normalization for chat orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from app.schemas.orchestrator import OrchestratorPolicyConfig
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationResult,
    RecommendationToolResponse,
)
from app.services.orchestrator.extraction import is_follow_up_refinement
from app.services.orchestrator.policies import (
    build_empty_results_message,
    build_no_new_results_message,
)
from app.services.orchestrator.runtime_types import RecommendationOutcome


class ResponseAssembler:
    """Normalize recommendation outputs into stateful runtime outcomes."""

    def __init__(self, *, policy: OrchestratorPolicyConfig) -> None:
        self._policy = policy

    def build_results_message(
        self,
        results: list[RecommendationResult],
        *,
        session_state: SessionState | None = None,
    ) -> str:
        preference_preface = ""
        if session_state is not None:
            weighted_interests = sorted(
                session_state.preferences.weighted_interests.items(),
                key=lambda item: (-item[1], item[0]),
            )
            interest_list = [interest for interest, _weight in weighted_interests[:3]]
            if interest_list:
                preference_preface = (
                    f"Based on your interests in {', '.join(interest_list)}, "
                )

        preview_limit = max(1, self._policy.max_recommendation_results)
        limit_notice = next(
            (
                str(item.features.get("limit_notice"))
                for item in results
                if isinstance(item.features, dict) and item.features.get("limit_notice")
            ),
            None,
        )
        displayed_results = results[:preview_limit]
        preview_items = "\n".join(
            f"{i}. {self._recommendation_display_name(item)}"
            for i, item in enumerate(displayed_results, start=1)
        )
        result_label = self._result_collection_label(results)
        result_count = len(results)
        if result_count == 1:
            preview_name = self._recommendation_display_name(displayed_results[0])
            base = (
                preference_preface
                + f"I found 1 {self._result_singular_label(results)} that fits your request. "
                + f"Top pick: {preview_name}"
            )
        else:
            base = (
                preference_preface
                + f"I found {result_count} {result_label} that fit your request. "
                + f"Top picks:\n{preview_items}"
            )
        if limit_notice:
            return f"{limit_notice} {base}"
        return base

    def normalize_recommendation_outcome(
        self,
        *,
        previous_state: SessionState,
        session_state: SessionState,
        user_message: str,
        recommendation_response: RecommendationToolResponse,
        recommendation_item_type: str,
        recommendation_query: str,
        allow_retry_on_duplicate: bool,
        candidate_message: str | None = None,
    ) -> RecommendationOutcome:
        next_state = session_state.model_copy(deep=True)
        next_state.last_message_at = datetime.now(timezone.utc)
        next_state.last_recommendation_version = recommendation_response.ranking_version
        next_state.conversation.last_requested_slots = []
        next_state.conversation.last_recommendation_item_type = cast(
            Any, recommendation_item_type
        )
        next_state.conversation.last_recommendation_query = recommendation_query

        if not recommendation_response.results:
            next_state.conversation.last_recommendation_result_ids = []
            next_state.status = "explore"
            next_state.conversation.last_clarification_kind = "refine_preference"
            next_state.conversation.last_search_outcome = "empty_results"
            return RecommendationOutcome(
                next_state=next_state,
                recommendations=[],
                fallback_message=build_empty_results_message(next_state),
                outcome="empty_results",
                candidate_message=candidate_message,
            )

        displayed_results, duplicate_only = self._select_results_for_response(
            user_message=user_message,
            previous_state=previous_state,
            results=recommendation_response.results,
        )
        if duplicate_only and allow_retry_on_duplicate:
            return RecommendationOutcome(
                next_state=next_state,
                recommendations=[],
                fallback_message="",
                outcome="retry_duplicate",
                candidate_message=candidate_message,
                retry_with_expanded_results=True,
            )

        if duplicate_only:
            next_state.status = "refine"
            next_state.conversation.last_recommendation_result_ids = list(
                previous_state.conversation.last_recommendation_result_ids
            )
            next_state.conversation.last_clarification_kind = "refine_preference"
            next_state.conversation.last_search_outcome = "no_new_results"
            return RecommendationOutcome(
                next_state=next_state,
                recommendations=[],
                fallback_message=build_no_new_results_message(next_state),
                outcome="empty_results",
                candidate_message=candidate_message,
            )

        next_state.conversation.last_recommendation_result_ids = [
            item.item_id for item in displayed_results
        ]
        next_state.status = "refine"
        next_state.conversation.last_clarification_kind = None
        next_state.conversation.last_search_outcome = "results"
        return RecommendationOutcome(
            next_state=next_state,
            recommendations=displayed_results,
            fallback_message=self.build_results_message(
                displayed_results,
                session_state=next_state,
            ),
            outcome="results",
            candidate_message=candidate_message,
        )

    def _select_results_for_response(
        self,
        *,
        user_message: str,
        previous_state: SessionState,
        results: list[RecommendationResult],
    ) -> tuple[list[RecommendationResult], bool]:
        if not self._is_duplicate_sensitive_follow_up(
            user_message=user_message,
            previous_state=previous_state,
        ):
            return results[: self._policy.max_recommendation_results], False

        prior_result_ids = set(
            previous_state.conversation.last_recommendation_result_ids
        )
        if not prior_result_ids:
            return results[: self._policy.max_recommendation_results], False

        unseen_results = [
            item for item in results if item.item_id not in prior_result_ids
        ]
        if unseen_results:
            return unseen_results[: self._policy.max_recommendation_results], False
        return [], True

    def _is_duplicate_sensitive_follow_up(
        self,
        *,
        user_message: str,
        previous_state: SessionState,
    ) -> bool:
        if not previous_state.conversation.last_recommendation_result_ids:
            return False
        return is_follow_up_refinement(user_message)

    def _recommendation_display_name(self, item: RecommendationResult) -> str:
        name = item.features.get("name")
        map_url = item.features.get("map_url")
        if isinstance(name, str):
            normalized = name.strip()
            if normalized:
                if isinstance(map_url, str) and map_url:
                    return f"{normalized} - {map_url}"
                return normalized
        return item.item_id

    def _result_collection_label(
        self,
        results: list[RecommendationResult],
    ) -> str:
        if not results:
            return "results"

        item_type = results[0].item_type
        if item_type == "hotel":
            return "hotels"
        if item_type == "restaurant":
            return "restaurants"
        if item_type == "activity":
            return "activities"
        return "results"

    def _result_singular_label(
        self,
        results: list[RecommendationResult],
    ) -> str:
        if not results:
            return "result"
        item_type = results[0].item_type
        if item_type == "hotel":
            return "hotel"
        if item_type == "restaurant":
            return "restaurant"
        if item_type == "activity":
            return "activity"
        return "result"
