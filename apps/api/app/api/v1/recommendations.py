"""Recommendations query endpoint."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.api.recommendations import (
    RecommendationQuery,
    RecommendationResponse,
)
from app.services.recommendation_query import (
    InvalidRecommendationResponseError,
    RecommendationServiceUnavailableError,
    RecommendationTool,
    execute_recommendation_query,
)
from traveltom.recommendor.recommendor_v1 import recommendation_tool

router = APIRouter()


@lru_cache()
def get_recommendation_tool() -> RecommendationTool:
    """Return the active recommendation tool implementation."""

    return recommendation_tool


@router.post("/recommendations/query", response_model=RecommendationResponse)
async def query_recommendations(
    request: RecommendationQuery,
    recommendation_tool: RecommendationTool = Depends(get_recommendation_tool),
) -> RecommendationResponse:
    """Return deterministic recommendation results for a validated query."""

    try:
        return await execute_recommendation_query(
            request=request,
            recommendation_tool=recommendation_tool,
        )
    except InvalidRecommendationResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid recommendation service response",
        ) from exc
    except RecommendationServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recommendation service unavailable",
        ) from exc
