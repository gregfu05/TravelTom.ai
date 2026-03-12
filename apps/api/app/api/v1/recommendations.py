"""Recommendations query endpoint."""

from __future__ import annotations

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
)
from app.services.travel_tom_agent import TravelTomAgent, get_travel_tom_agent

router = APIRouter()


@router.post("/recommendations/query", response_model=RecommendationResponse)
async def query_recommendations(
    request: RecommendationQuery,
    principal: AuthenticatedPrincipal | None = Depends(require_authenticated_principal),
    agent: TravelTomAgent = Depends(get_travel_tom_agent),
) -> RecommendationResponse:
    """Return deterministic recommendation results for a validated query."""

    del principal
    try:
        return await agent.handle_recommendation_query(request=request)
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
