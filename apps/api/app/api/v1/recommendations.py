"""Recommendations query endpoint."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends

from app.core.errors import ApiError
from app.core.security import require_authenticated_principal
from app.schemas.api.recommendations import (
    RecommendationQuery,
    RecommendationResponse,
)
from app.schemas.auth import AuthenticatedPrincipal
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
    principal: AuthenticatedPrincipal | None = Depends(require_authenticated_principal),
    recommendation_tool: RecommendationTool = Depends(get_recommendation_tool),
) -> RecommendationResponse:
    """Return deterministic recommendation results for a validated query."""

    del principal
    try:
        return await execute_recommendation_query(
            request=request,
            recommendation_tool=recommendation_tool,
        )
    except InvalidRecommendationResponseError as exc:
        raise ApiError(
            status_code=502,
            code="bad_gateway",
            message="Invalid recommendation service response",
        ) from exc
    except RecommendationServiceUnavailableError as exc:
        raise ApiError(
            status_code=500,
            code="recommendation_service_unavailable",
            message="Recommendation service unavailable",
        ) from exc
