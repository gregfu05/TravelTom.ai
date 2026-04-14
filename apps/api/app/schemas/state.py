"""Session state schemas used by the orchestrator and API layer."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DateRange(BaseModel):
    """Inclusive start and end dates for a trip."""

    model_config = ConfigDict(extra="forbid")

    start: date
    end: date

    @model_validator(mode="after")
    def validate_range(self) -> "DateRange":
        if self.end < self.start:
            raise ValueError("end must be on or after start")
        return self


class BudgetRange(BaseModel):
    """Budget constraints expressed in a single currency."""

    model_config = ConfigDict(extra="forbid")

    min: float = Field(ge=0)
    max: float = Field(ge=0)
    currency: str = Field(min_length=3, max_length=8)

    @model_validator(mode="after")
    def validate_bounds(self) -> "BudgetRange":
        if self.max < self.min:
            raise ValueError("max must be greater than or equal to min")
        return self


class PartySize(BaseModel):
    """Traveler composition for recommendation constraints."""

    model_config = ConfigDict(extra="forbid")

    adults: int = Field(ge=1)
    children: int = Field(default=0, ge=0)


class Constraints(BaseModel):
    """Structured travel constraints extracted from chat."""

    model_config = ConfigDict(extra="forbid")

    origin: str | None = None
    destination: str | None = None
    dates: DateRange | None = None
    trip_length_days: int | None = Field(default=None, ge=1)
    budget: BudgetRange | None = None
    party_size: PartySize | None = None


class Preferences(BaseModel):
    """User preferences and disqualifiers."""

    model_config = ConfigDict(extra="forbid")

    weighted_interests: dict[str, float] = Field(default_factory=dict)
    dislikes: list[str] = Field(default_factory=list)

    @field_validator("weighted_interests")
    @classmethod
    def validate_interest_weights(cls, values: dict[str, float]) -> dict[str, float]:
        for key, value in values.items():
            if not 0 <= value <= 1:
                raise ValueError(f"weighted_interests[{key}] must be between 0 and 1")
        return values


class Entities(BaseModel):
    """Named entities detected from user messages."""

    model_config = ConfigDict(extra="forbid")

    destinations: list[str] = Field(default_factory=list)


class ItineraryState(BaseModel):
    """Session itinerary payload."""

    model_config = ConfigDict(extra="forbid")

    days: list[dict[str, Any]] = Field(default_factory=list)


class ConversationState(BaseModel):
    """Conversation metadata used by the orchestrator across turns."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    last_requested_slots: list[str] = Field(default_factory=list)
    last_user_intent: Literal["recommend", "refine", "clarify"] | None = None
    last_clarification_kind: (
        Literal[
            "core_slot",
            "search_type",
            "refine_preference",
        ]
        | None
    ) = None
    last_search_outcome: (
        Literal[
            "results",
            "empty_results",
            "no_new_results",
        ]
        | None
    ) = None
    last_recommendation_item_type: (
        Literal["hotel", "restaurant", "activity"] | None
    ) = None
    last_recommendation_query: str | None = None
    last_recommendation_result_ids: list[str] = Field(default_factory=list)


class SessionState(BaseModel):
    """Canonical orchestrator session state (v1)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    state_version: Literal["v1"] = "v1"
    session_id: str = Field(min_length=1)
    user_id: str | None = None
    constraints: Constraints = Field(default_factory=Constraints)
    preferences: Preferences = Field(default_factory=Preferences)
    entities: Entities = Field(default_factory=Entities)
    conversation: ConversationState = Field(default_factory=ConversationState)
    shortlist: list[str] = Field(default_factory=list)
    itinerary: ItineraryState = Field(default_factory=ItineraryState)
    status: Literal["explore", "refine", "itinerary", "booking"] = "explore"
    last_recommendation_version: str | None = None
    last_message_at: datetime | None = None
