"""Response schema for the health endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health endpoint response payload."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
