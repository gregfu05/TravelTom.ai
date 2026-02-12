"""Schemas for deterministic recommendation tool calls."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.state import BudgetRange, DateRange, PartySize


class RecommendationConstraints(BaseModel):
    """Hard constraints applied during retrieval and ranking."""

    model_config = ConfigDict(extra="forbid")

    origin: str | None = None
    destination: str | None = None
    dates: DateRange | None = None
    budget: BudgetRange | None = None
    party_size: PartySize | None = None
    star_rating_min: int | None = Field(default=None, ge=0, le=5)


class RecommendationQuery(BaseModel):
    """Input payload for the recommendation tool."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    constraints: RecommendationConstraints = Field(
        default_factory=RecommendationConstraints
    )
    filters: dict[str, Any] = Field(default_factory=dict)
    max_results: int = Field(default=20, ge=1, le=50)
    ranking_version: str = Field(default="heuristic-v1", min_length=1)


class RecommendationResult(BaseModel):
    """Ranked recommendation output item."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    item_type: Literal["destination", "hotel", "flight"]
    score: float
    rank: int = Field(ge=1)
    features: dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(min_length=1)


class RecommendationToolResponse(BaseModel):
    """Structured output returned by the recommendation tool."""

    model_config = ConfigDict(extra="forbid")

    results: list[RecommendationResult] = Field(default_factory=list)
    ranking_version: str = Field(min_length=1)

