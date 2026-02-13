"""Recommendations query endpoint."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationToolResponse,
)
from app.services.orchestrator.service import placeholder_recommendation_tool

router = APIRouter()

RecommendationTool = Callable[
    [RecommendationQuery],
    RecommendationToolResponse | dict[str, Any],
]


@lru_cache()
def get_recommendation_tool() -> RecommendationTool:
    """Return the active recommendation tool implementation."""

    return placeholder_recommendation_tool


@router.post("/recommendations/query", response_model=RecommendationToolResponse)
async def query_recommendations(
    request: RecommendationQuery,
    recommendation_tool: RecommendationTool = Depends(get_recommendation_tool),
) -> RecommendationToolResponse:
    """Return deterministic recommendation results for a validated query."""

    try:
        tool_output = recommendation_tool(request)
        return RecommendationToolResponse.model_validate(tool_output)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid recommendation service response",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recommendation service unavailable",
        ) from exc
