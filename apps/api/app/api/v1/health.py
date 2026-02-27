"""Health check endpoint."""

from fastapi import APIRouter

from app.schemas.api.health import HealthResponse
from app.services.health_status import get_health_response

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return get_health_response()
