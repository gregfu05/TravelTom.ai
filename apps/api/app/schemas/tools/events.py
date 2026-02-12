"""Schemas for analytics and system event ingestion tools."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventPayload(BaseModel):
    """Event ingestion payload with idempotency requirements."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    event_version: int = Field(ge=1)
    occurred_at: datetime
    session_id: str = Field(min_length=1)
    user_id: str | None = None
    idempotency_key: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
