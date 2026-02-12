"""Schemas for catalog search tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CatalogSearchQuery(BaseModel):
    """Catalog search input payload."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    q: str = Field(min_length=1)
    item_type: Literal["destination", "hotel", "flight"] | None = Field(
        default=None,
        alias="type",
    )
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
