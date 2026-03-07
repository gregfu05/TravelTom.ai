"""Authentication, authorization, and rate limiting helpers."""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from fastapi import Depends, Request, status
from fastapi.security.oauth2 import SecurityScopes
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from limits.util import parse as parse_rate_limit
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings, get_settings
from app.core.errors import ApiError

try:
    from fastapi_azure_auth import B2CMultiTenantAuthorizationCodeBearer
    from fastapi_azure_auth.user import User as AzureAuthUser
except ImportError:  # pragma: no cover - dependency is installed in runtime env
    B2CMultiTenantAuthorizationCodeBearer = None
    AzureAuthUser = Any


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

    @classmethod
    def from_azure_user(cls, user: AzureAuthUser) -> "AuthenticatedPrincipal":
        return cls(
            subject=user.sub,
            issuer=user.iss,
            email=user.email or user.preferred_username,
            name=user.name,
            object_id=user.oid,
            tenant_id=user.tid,
            scopes=list(user.scp),
            raw_claims=dict(user.claims),
        )


class ChatRateLimiter:
    """In-memory chat rate limiter backed by ``limits`` primitives."""

    def __init__(self) -> None:
        self._storage = MemoryStorage()
        self._limiter = MovingWindowRateLimiter(self._storage)

    def reset(self) -> None:
        """Reset all in-memory rate limit state."""

        self._storage.reset()

    def check(self, *, rate_limit: str, key: str) -> int | None:
        """Consume one token from the configured rate limit."""

        parsed_limit = parse_rate_limit(rate_limit)
        if self._limiter.hit(parsed_limit, key):
            return None

        window = self._limiter.get_window_stats(parsed_limit, key)
        retry_after_seconds = max(0, int(window.reset_time - time.time()))
        return retry_after_seconds


@lru_cache()
def get_azure_b2c_scheme() -> B2CMultiTenantAuthorizationCodeBearer | None:
    """Return the configured Azure AD B2C auth scheme."""

    settings = get_settings()
    if not settings.auth_enabled:
        return None
    if B2CMultiTenantAuthorizationCodeBearer is None:
        raise RuntimeError("fastapi-azure-auth is not installed")
    if not settings.auth_app_client_id or not settings.auth_openid_config_url:
        raise RuntimeError("Azure AD B2C authentication is not fully configured")

    scopes = {
        scope: f"Required TravelTom API scope: {scope}"
        for scope in settings.auth_required_scopes_list
    }
    return B2CMultiTenantAuthorizationCodeBearer(
        app_client_id=settings.auth_app_client_id,
        auto_error=True,
        scopes=scopes or None,
        openid_config_url=settings.auth_openid_config_url,
    )


@lru_cache()
def get_chat_rate_limiter() -> ChatRateLimiter:
    """Return the shared chat rate limiter."""

    return ChatRateLimiter()


def _require_bearer_token(request: Request) -> None:
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Missing bearer token",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Invalid authorization header",
        )


async def require_authenticated_principal(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AuthenticatedPrincipal | None:
    """Return the authenticated principal when auth is enabled."""

    if not settings.auth_enabled:
        return None

    cached_principal = getattr(request.state, "principal", None)
    if isinstance(cached_principal, AuthenticatedPrincipal):
        return cached_principal

    _require_bearer_token(request)

    try:
        scheme = get_azure_b2c_scheme()
    except RuntimeError as exc:
        raise ApiError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="auth_configuration_error",
            message=str(exc),
        ) from exc

    if scheme is None:
        raise ApiError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="auth_configuration_error",
            message="Authentication scheme is not available",
        )

    security_scopes = SecurityScopes(scopes=settings.auth_required_scopes_list)
    try:
        azure_user = await scheme(request, security_scopes)
    except Exception as exc:
        status_code = getattr(exc, "status_code", status.HTTP_401_UNAUTHORIZED)
        detail = getattr(exc, "detail", "Authentication failed")
        message = str(detail or "Authentication failed")
        code = (
            "forbidden"
            if status_code == status.HTTP_403_FORBIDDEN
            else "unauthorized"
        )
        raise ApiError(
            status_code=status_code,
            code=code,
            message=message,
        ) from exc

    if azure_user is None:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Authentication failed",
        )

    principal = AuthenticatedPrincipal.from_azure_user(azure_user)
    request.state.principal = principal
    return principal


async def enforce_chat_rate_limit(
    request: Request,
    principal: AuthenticatedPrincipal | None = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_settings),
) -> None:
    """Enforce the configured chat rate limit."""

    limiter = get_chat_rate_limiter()
    if principal is not None:
        identifier = principal.subject
    elif request.client is not None:
        identifier = request.client.host
    else:
        identifier = "anonymous"
    retry_after_seconds = limiter.check(
        rate_limit=settings.chat_rate_limit,
        key=f"chat:{identifier}",
    )
    if retry_after_seconds is None:
        return

    raise ApiError(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code="rate_limit_exceeded",
        message="Chat rate limit exceeded",
        details={"retry_after_seconds": retry_after_seconds},
    )
