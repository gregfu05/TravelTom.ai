"""Service helpers for health endpoint responses."""

from __future__ import annotations

from app.schemas.api.health import HealthResponse


def get_health_response() -> HealthResponse:
    """Return the static service health payload."""

    return HealthResponse(status="ok")
