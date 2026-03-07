"""User persistence helpers for authentication-backed flows."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.local_auth import LOCAL_AUTH_ISSUER, normalize_email
from app.core.security import AuthenticatedPrincipal
from app.db.models.user import User


class UserRepository:
    """Repository for resolving authenticated principals to user rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        """Return a user row by normalized email address."""

        result = await self._session.execute(
            select(User).where(User.email == normalize_email(email))
        )
        return result.scalar_one_or_none()

    async def get_by_auth_identity(self, *, issuer: str, subject: str) -> User | None:
        """Return a user row by auth issuer and subject."""

        result = await self._session.execute(
            select(User).where(
                User.auth_issuer == issuer,
                User.external_subject == subject,
            )
        )
        return result.scalar_one_or_none()

    async def create_local_user(self, *, email: str, password_hash: str) -> User:
        """Create a local email/password user row."""

        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            auth_issuer=LOCAL_AUTH_ISSUER,
            external_subject=str(user_id),
            email=normalize_email(email),
            password_hash=password_hash,
        )
        self._session.add(user)
        return user

    async def get_or_create_from_principal(
        self,
        principal: AuthenticatedPrincipal,
    ) -> User:
        """Resolve or create a user row from a validated auth principal."""

        user = await self.get_by_auth_identity(
            issuer=principal.issuer,
            subject=principal.subject,
        )
        if user is not None:
            if principal.email and user.email != principal.email:
                user.email = normalize_email(principal.email)
            return user

        if principal.issuer == LOCAL_AUTH_ISSUER:
            raise ApiError(
                status_code=401,
                code="unauthorized",
                message="Authenticated user does not exist",
            )

        user = User(
            id=uuid.uuid4(),
            auth_issuer=principal.issuer,
            external_subject=principal.subject,
            email=normalize_email(principal.email) if principal.email else None,
        )
        self._session.add(user)
        return user
