"""User persistence helpers for authentication-backed flows."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthenticatedPrincipal
from app.db.models.user import User


class UserRepository:
    """Repository for resolving authenticated principals to user rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_from_principal(
        self,
        principal: AuthenticatedPrincipal,
    ) -> User:
        """Resolve or create a user row from a validated auth principal."""

        result = await self._session.execute(
            select(User).where(
                User.auth_issuer == principal.issuer,
                User.external_subject == principal.subject,
            )
        )
        user = result.scalar_one_or_none()
        if user is not None:
            if principal.email and user.email != principal.email:
                user.email = principal.email
            return user

        user = User(
            id=uuid.uuid4(),
            auth_issuer=principal.issuer,
            external_subject=principal.subject,
            email=principal.email,
        )
        self._session.add(user)
        return user
