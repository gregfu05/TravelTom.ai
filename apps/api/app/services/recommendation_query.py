"""Recommendation query execution helpers for API routes."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from pydantic import ValidationError

from app.core.telemetry import start_span
from app.schemas.api.recommendations import (
    RecommendationQuery,
    RecommendationResponse,
)
from app.schemas.api.recommendations import (
    RecommendationResult as ApiRecommendationResult,
)
from app.schemas.tools.recommendations import (
    RecommendationQuery as RecommendationToolQuery,
)
from app.schemas.tools.recommendations import (
    RecommendationToolResponse as RecommendationToolOutput,
)

RecommendationTool = Callable[
    [RecommendationToolQuery],
    RecommendationToolOutput | dict[str, Any],
]


class InvalidRecommendationResponseError(Exception):
    """Raised when tool output cannot be validated against the schema."""


class RecommendationServiceUnavailableError(Exception):
    """Raised when recommendation execution fails unexpectedly."""


async def execute_recommendation_query(
    *,
    request: RecommendationQuery,
    recommendation_tool: RecommendationTool,
) -> RecommendationResponse:
    """Execute recommendation query and normalize response to API schema."""

    tool_request = RecommendationToolQuery.model_validate(
        request.model_dump(mode="json")
    )
    try:
        with start_span(
            "recommendation.retrieval",
            session_id=request.session_id,
            item_type=request.filters.get("item_type"),
            max_results=request.max_results,
        ):
            tool_output = await asyncio.to_thread(recommendation_tool, tool_request)
            validated_output = RecommendationToolOutput.model_validate(tool_output)
    except ValidationError as exc:
        raise InvalidRecommendationResponseError(
            "Invalid recommendation service response"
        ) from exc
    except Exception as exc:
        raise RecommendationServiceUnavailableError(
            "Recommendation service unavailable"
        ) from exc

    return RecommendationResponse(
        results=[
            ApiRecommendationResult(
                item_id=item.item_id,
                item_type=item.item_type,
                rank=item.rank,
                features=dict(item.features or {}),
            )
            for item in validated_output.results
        ],
        ranking_version=validated_output.ranking_version,
    )
