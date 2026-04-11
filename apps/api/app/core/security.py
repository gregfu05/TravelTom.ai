"""Authentication, authorization, and rate limiting helpers."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from fastapi import Depends, Request, status
from fastapi.security.oauth2 import SecurityScopes
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from limits.util import parse as parse_rate_limit
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ApiError, get_trace_id
from app.core.local_auth import (
    InvalidLocalTokenError,
    NotLocalTokenError,
    decode_access_token,
)
from app.db.session import get_db
from app.repositories.auth_sessions import AuthSessionRepository
from app.schemas.auth import AuthenticatedPrincipal, LocalAccessTokenClaims

if TYPE_CHECKING:
    from fastapi_azure_auth import (
        B2CMultiTenantAuthorizationCodeBearer as AzureB2CScheme,
    )

azure_b2c_scheme_class: type[Any] | None
FASTAPI_AZURE_AUTH_INSTALLED = True

try:
    from fastapi_azure_auth import (
        B2CMultiTenantAuthorizationCodeBearer as _AzureB2CSchemeClass,
    )

    azure_b2c_scheme_class = _AzureB2CSchemeClass
except ImportError:  # pragma: no cover - dependency is installed in runtime env
    FASTAPI_AZURE_AUTH_INSTALLED = False
    azure_b2c_scheme_class = None

logger = logging.getLogger(__name__)


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
def get_azure_b2c_scheme() -> AzureB2CScheme | None:
    """Return the configured Azure AD B2C auth scheme."""

    settings = get_settings()
    if not settings.auth_enabled:
        return None
    if not FASTAPI_AZURE_AUTH_INSTALLED:
        raise RuntimeError("fastapi-azure-auth is not installed")
    if not settings.auth_app_client_id or not settings.auth_openid_config_url:
        raise RuntimeError("Azure AD B2C authentication is not fully configured")

    scopes = {
        scope: f"Required TravelTom API scope: {scope}"
        for scope in settings.auth_required_scopes_list
    }
    assert azure_b2c_scheme_class is not None
    return azure_b2c_scheme_class(
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


def _get_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Invalid authorization header",
        )
    return token


async def require_authenticated_principal(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedPrincipal | None:
    """Return the authenticated principal when auth is enabled."""

    cached_principal = getattr(request.state, "principal", None)
    if isinstance(cached_principal, AuthenticatedPrincipal):
        return cached_principal

    token = _get_bearer_token(request)
    if token is None:
        if settings.auth_enabled:
            _require_bearer_token(request)
        return None

    if settings.local_auth_enabled:
        try:
            claims = decode_access_token(
                token=token,
                secret=(settings.local_auth_token_secret or "").strip(),
            )
        except NotLocalTokenError:
            pass
        except InvalidLocalTokenError as exc:
            if not settings.auth_enabled:
                raise ApiError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="unauthorized",
                    message=str(exc),
                ) from exc
        else:
            auth_sessions = AuthSessionRepository(db)
            auth_session = await _validate_local_auth_session(
                claims=claims,
                repository=auth_sessions,
            )
            auth_sessions.touch(
                auth_session,
                now=_utc_now(),
                idle_timeout_seconds=settings.local_auth_token_idle_timeout_seconds,
            )
            await db.commit()
            principal = AuthenticatedPrincipal(
                subject=claims.sub,
                issuer=claims.iss,
                email=claims.email,
                scopes=[],
                raw_claims=claims.model_dump(mode="json"),
            )
            request.state.principal = principal
            request.state.local_auth_claims = claims
            request.state.local_auth_session_id = str(auth_session.id)
            return principal

    if not settings.auth_enabled:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Invalid bearer token",
        )

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
            "forbidden" if status_code == status.HTTP_403_FORBIDDEN else "unauthorized"
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

    principal = AuthenticatedPrincipal(
        subject=azure_user.sub,
        issuer=azure_user.iss,
        email=azure_user.email or azure_user.preferred_username,
        name=azure_user.name,
        object_id=azure_user.oid,
        tenant_id=azure_user.tid,
        scopes=list(azure_user.scp),
        raw_claims=dict(azure_user.claims),
    )
    request.state.principal = principal
    return principal


async def _validate_local_auth_session(
    *,
    claims: LocalAccessTokenClaims,
    repository: AuthSessionRepository,
):
    """Validate the persisted local auth-session referenced by the bearer token."""

    try:
        session_id = uuid.UUID(claims.jti)
    except ValueError as exc:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Invalid bearer token",
        ) from exc

    auth_session = await repository.get_by_id(session_id)
    now = _utc_now()
    if auth_session is None or str(auth_session.user_id) != claims.sub:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Authenticated session does not exist",
        )
    if repository.is_revoked(auth_session):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Bearer token has been logged out",
        )
    if repository.is_expired(auth_session, now=now):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Bearer token has expired",
        )
    if repository.is_idle_expired(auth_session, now=now):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Bearer token timed out due to inactivity",
        )
    return auth_session


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def enforce_chat_rate_limit(
    request: Request,
    principal: AuthenticatedPrincipal | None = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_settings),
) -> None:
    """Enforce the configured chat rate limit."""

    if not settings.chat_rate_limit_enabled_effective:
        return

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

    trace_id = get_trace_id(request)
    logger.warning(
        "chat_rate_limit_rejected",
        extra={
            "trace_id": trace_id,
            "context": {
                "auth_enabled": settings.auth_enabled,
                "chat_rate_limit": settings.chat_rate_limit,
                "client_host": (
                    request.client.host if request.client is not None else None
                ),
                "identifier": identifier,
                "path": str(request.url.path),
                "principal_subject": (
                    principal.subject if principal is not None else None
                ),
                "retry_after_seconds": retry_after_seconds,
            },
        },
    )
    raise ApiError(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code="rate_limit_exceeded",
        message="Chat rate limit exceeded",
        details={
            "retry_after_seconds": retry_after_seconds,
            "source": "traveltom",
        },
        headers={"Retry-After": str(retry_after_seconds)},
    )
