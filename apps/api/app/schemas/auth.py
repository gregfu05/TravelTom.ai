"""Shared authentication schema models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuthenticatedPrincipal(BaseModel):
    """Normalized authenticated user identity for backend authorization."""

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    email: str | None = None
    name: str | None = None
    object_id: str | None = None
    tenant_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    raw_claims: dict[str, Any] = Field(default_factory=dict)


class LocalAccessTokenClaims(BaseModel):
    """Claims carried by TravelTom-issued bearer tokens."""

    model_config = ConfigDict(extra="forbid")

    sub: str = Field(min_length=1)
    iss: str = Field(min_length=1)
    email: str = Field(min_length=1)
    iat: int
    exp: int
