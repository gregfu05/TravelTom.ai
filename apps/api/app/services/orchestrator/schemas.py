"""Orchestrator schema models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.tools.recommendations import RecommendationResult


class OrchestratorResponse(BaseModel):
    """Normalized orchestrator output for API layer integration."""

    session_id: str
    assistant_message: str
    recommendations: list[RecommendationResult] = Field(default_factory=list)
    itinerary: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any]
