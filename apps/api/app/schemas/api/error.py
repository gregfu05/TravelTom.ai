"""Error response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    """Structured API error payload."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] | None = None
    trace_id: str = Field(min_length=1)


class ErrorResponse(BaseModel):
    """Top-level API error envelope."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
