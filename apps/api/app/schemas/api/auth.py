"""Request and response schemas for authentication endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.local_auth import is_valid_email, normalize_email


class _EmailPasswordRequest(BaseModel):
    """Shared validation for email/password payloads."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = normalize_email(value)
        if not is_valid_email(email):
            raise ValueError("Email address is invalid")
        return email


class SignupRequest(_EmailPasswordRequest):
    """Request body for account creation."""


class LoginRequest(_EmailPasswordRequest):
    """Request body for local account login."""


class AuthUserResponse(BaseModel):
    """Public user payload returned by auth endpoints."""

    id: str
    email: str


class AuthTokenResponse(BaseModel):
    """Response payload for signup and login."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: AuthUserResponse
