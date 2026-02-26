"""Request and response schemas for the chat endpoint."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ClientContext(BaseModel):
    """Optional metadata provided by the client application."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    timezone: str | None = None
    locale: str | None = None
    currency: str | None = None


class ChatRequest(BaseModel):
    """Request payload for the chat endpoint."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    user_id: str | None = None
    message: str = Field(min_length=1)
    client_context: ClientContext | None = None


class ChatRecommendation(BaseModel):
    """Recommendation payload returned to the web client."""

    item_id: str
    item_type: Literal["destination", "hotel", "flight"]
    score: float
    rank: int
    explanation: str
    metadata: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    """Response payload for the chat endpoint."""

    session_id: str
    message_id: str
    assistant_message: str
    recommendations: list[ChatRecommendation] = Field(default_factory=list)
    itinerary: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any]
