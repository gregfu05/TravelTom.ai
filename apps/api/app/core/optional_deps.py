"""Typed adapters for optional dependencies.

This module centralizes optional third-party integrations so the rest of the
codebase can keep imports unconditional and type-safe.

Optional dependencies handled here:
- limits (rate limiting backend)
- fastapi-azure-auth (Azure AD B2C scheme)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, cast, runtime_checkable


class OptionalDepsNotInstalledError(RuntimeError):
    """Raised when an optional dependency is required but not installed."""


@runtime_checkable
class ChatRateLimiterBackend(Protocol):
    def reset(self) -> None:
        ...

    def check(self, *, rate_limit: str, key: str) -> int | None:
        ...


class _NoopChatRateLimiterBackend:
    """Fallback backend used when the `limits` package is missing."""

    def reset(self) -> None:  # pragma: no cover
        return

    def check(self, *, rate_limit: str, key: str) -> int | None:  # pragma: no cover
        del rate_limit
        del key
        return None


def get_chat_rate_limiter_backend() -> ChatRateLimiterBackend:
    """Return a chat rate limiter backend.

    If `limits` is not installed, returns a no-op backend which never rate-limits.
    """

    try:
        from limits.storage import MemoryStorage
        from limits.strategies import MovingWindowRateLimiter
        from limits.util import parse as parse_rate_limit
    except ModuleNotFoundError:
        return _NoopChatRateLimiterBackend()

    @dataclass
    class _LimitsChatRateLimiterBackend:
        storage: Any
        limiter: Any

        def reset(self) -> None:
            self.storage.reset()

        def check(self, *, rate_limit: str, key: str) -> int | None:
            import time

            parsed_limit = parse_rate_limit(rate_limit)
            if self.limiter.hit(parsed_limit, key):
                return None

            window = self.limiter.get_window_stats(parsed_limit, key)
            retry_after_seconds = max(0, int(window.reset_time - time.time()))
            return retry_after_seconds

    storage = MemoryStorage()
    limiter = MovingWindowRateLimiter(storage)
    return _LimitsChatRateLimiterBackend(storage=storage, limiter=limiter)


# Azure B2C scheme typing


class AzureB2CScheme(Protocol):
    async def __call__(self, request: Any, scopes: Any) -> Any:
        ...


class AzureB2CSchemeFactory(Protocol):
    def build(
        self,
        *,
        app_client_id: str,
        scopes: Optional[dict[str, str]],
        openid_config_url: str,
    ) -> AzureB2CScheme:
        ...


def get_azure_b2c_scheme_factory() -> AzureB2CSchemeFactory:
    """Return an Azure B2C auth scheme factory.

    Raises OptionalDepsNotInstalledError when fastapi-azure-auth is missing.
    """

    try:
        from fastapi_azure_auth import B2CMultiTenantAuthorizationCodeBearer
    except ModuleNotFoundError as exc:
        raise OptionalDepsNotInstalledError(
            "fastapi-azure-auth is not installed"
        ) from exc

    class _Factory:
        def build(
            self,
            *,
            app_client_id: str,
            scopes: Optional[dict[str, str]],
            openid_config_url: str,
        ) -> AzureB2CScheme:
            return cast(
                AzureB2CScheme,
                B2CMultiTenantAuthorizationCodeBearer(
                    app_client_id=app_client_id,
                    auto_error=True,
                    scopes=scopes or None,
                    openid_config_url=openid_config_url,
                ),
            )

    return _Factory()
