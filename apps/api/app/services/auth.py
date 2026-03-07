"""Traditional email/password authentication services."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.local_auth import (
    create_access_token,
    hash_password,
    normalize_email,
    verify_password,
)
from app.db.models.auth_session import AuthSession
from app.db.models.user import User
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository
from app.schemas.auth import AuthenticatedPrincipal, LocalAccessTokenClaims


@dataclass(frozen=True)
class AuthSessionResult:
    """Response payload pieces for a successful local-auth exchange."""

    access_token: str
    expires_in: int
    idle_timeout_in: int
    user: User


class AuthService:
    """Handles local account creation, login, and current-user lookup."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._auth_sessions = AuthSessionRepository(session)

    async def signup(self, *, email: str, password: str) -> AuthSessionResult:
        """Create a local account and issue a bearer token."""

        secret = self._local_auth_secret()
        normalized_email = normalize_email(email)
        existing_user = await self._users.get_by_email(normalized_email)
        if existing_user is not None:
            raise ApiError(
                status_code=409,
                code="conflict",
                message="An account with that email already exists",
            )

        user = await self._users.create_local_user(
            email=normalized_email,
            password_hash=hash_password(password),
        )
        return await self._issue_local_session(user, secret=secret)

    async def login(self, *, email: str, password: str) -> AuthSessionResult:
        """Authenticate a local account and issue a bearer token."""

        secret = self._local_auth_secret()
        normalized_email = normalize_email(email)
        user = await self._users.get_by_email(normalized_email)
        if user is None or not user.password_hash:
            raise ApiError(
                status_code=401,
                code="unauthorized",
                message="Invalid email or password",
            )
        if not verify_password(password, user.password_hash):
            raise ApiError(
                status_code=401,
                code="unauthorized",
                message="Invalid email or password",
            )
        return await self._issue_local_session(user, secret=secret)

    async def get_current_user(self, principal: AuthenticatedPrincipal) -> User:
        """Resolve the user row represented by the authenticated principal."""

        user = await self._users.get_or_create_from_principal(principal)
        await self._session.commit()
        return user

    async def logout_local_session(
        self,
        *,
        claims: LocalAccessTokenClaims,
    ) -> None:
        """Revoke the current local bearer-token session."""

        try:
            session_id = uuid.UUID(claims.jti)
        except ValueError as exc:
            raise ApiError(
                status_code=401,
                code="unauthorized",
                message="Authenticated session does not exist",
            ) from exc

        auth_session = await self._auth_sessions.get_by_id(session_id)
        if auth_session is None or str(auth_session.user_id) != claims.sub:
            raise ApiError(
                status_code=401,
                code="unauthorized",
                message="Authenticated session does not exist",
            )

        self._auth_sessions.revoke(
            auth_session,
            now=self._utc_now(),
            reason="logout",
        )
        await self._session.commit()

    async def _issue_local_session(
        self,
        user: User,
        *,
        secret: str,
    ) -> AuthSessionResult:
        """Create a persisted auth session and return its bearer token payload."""

        token_id = uuid.uuid4()
        auth_session = await self._auth_sessions.create_local_session(
            user_id=user.id,
            session_id=token_id,
            ttl_seconds=self._settings.local_auth_token_ttl_seconds,
            idle_timeout_seconds=self._settings.local_auth_token_idle_timeout_seconds,
            now=self._utc_now(),
        )
        await self._session.commit()
        return self._build_auth_session(
            user,
            auth_session=auth_session,
            secret=secret,
        )

    def _build_auth_session(
        self,
        user: User,
        *,
        auth_session: AuthSession,
        secret: str,
    ) -> AuthSessionResult:
        """Return a signed access token and public user payload."""

        if not user.email:
            raise ApiError(
                status_code=500,
                code="auth_configuration_error",
                message="Authenticated user is missing an email address",
            )

        access_token = create_access_token(
            subject=str(user.id),
            email=user.email,
            secret=secret,
            ttl_seconds=self._settings.local_auth_token_ttl_seconds,
            token_id=str(auth_session.id),
        )
        return AuthSessionResult(
            access_token=access_token,
            expires_in=self._settings.local_auth_token_ttl_seconds,
            idle_timeout_in=self._settings.local_auth_token_idle_timeout_seconds,
            user=user,
        )

    def _local_auth_secret(self) -> str:
        """Return the configured local auth secret or raise a config error."""

        secret = (self._settings.local_auth_token_secret or "").strip()
        if not secret:
            raise ApiError(
                status_code=500,
                code="auth_configuration_error",
                message="Local auth is not configured",
            )
        return secret

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)
