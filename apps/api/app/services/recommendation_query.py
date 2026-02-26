"""Recommendation query execution helpers for API routes."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from pydantic import ValidationError

from app.schemas.api.recommendations import RecommendationQuery, RecommendationResponse
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

    return RecommendationResponse.model_validate(
        validated_output.model_dump(mode="json")
    )
