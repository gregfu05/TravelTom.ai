"""Persistence helpers for local-auth bearer token sessions."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.local_auth import LOCAL_AUTH_ISSUER
from app.db.models.auth_session import AuthSession


class AuthSessionRepository:
    """Repository for local bearer-token session persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_local_session(
        self,
        *,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        ttl_seconds: int,
        idle_timeout_seconds: int,
        now: datetime | None = None,
    ) -> AuthSession:
        """Create and add a new local auth-session row."""

        current_time = now or datetime.now(timezone.utc)
        auth_session = AuthSession(
            id=session_id,
            user_id=user_id,
            auth_issuer=LOCAL_AUTH_ISSUER,
            expires_at=current_time + timedelta(seconds=ttl_seconds),
            idle_expires_at=current_time + timedelta(seconds=idle_timeout_seconds),
            last_seen_at=current_time,
        )
        self._session.add(auth_session)
        return auth_session

    async def get_by_id(self, session_id: uuid.UUID) -> AuthSession | None:
        """Return an auth-session row by primary key."""

        result = await self._session.execute(
            select(AuthSession).where(AuthSession.id == session_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def is_revoked(auth_session: AuthSession) -> bool:
        """Return whether the auth-session has been revoked."""

        return auth_session.revoked_at is not None

    @staticmethod
    def is_expired(auth_session: AuthSession, *, now: datetime) -> bool:
        """Return whether the auth-session is beyond its absolute expiry."""

        return auth_session.expires_at <= now

    @staticmethod
    def is_idle_expired(auth_session: AuthSession, *, now: datetime) -> bool:
        """Return whether the auth-session exceeded its idle timeout."""

        return auth_session.idle_expires_at <= now

    @staticmethod
    def touch(
        auth_session: AuthSession,
        *,
        now: datetime,
        idle_timeout_seconds: int,
    ) -> None:
        """Extend the idle timeout after a successful authenticated request."""

        auth_session.last_seen_at = now
        auth_session.idle_expires_at = now + timedelta(seconds=idle_timeout_seconds)

    @staticmethod
    def revoke(
        auth_session: AuthSession,
        *,
        now: datetime,
        reason: str,
    ) -> None:
        """Revoke an auth-session."""

        auth_session.revoked_at = now
        auth_session.revoked_reason = reason
