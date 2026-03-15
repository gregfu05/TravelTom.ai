"""fastapi-users adapter for TravelTom local accounts."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi_users import BaseUserManager, schemas
from fastapi_users.db import BaseUserDatabase
from fastapi_users.exceptions import InvalidID, InvalidPasswordException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.local_auth import normalize_email
from app.db.models.user import User
from app.repositories.users import UserRepository


class _LocalUserCreate(schemas.CreateUpdateDictModel):
    """Internal create payload consumed by ``BaseUserManager``."""

    email: str
    password: str
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = True


class TravelTomUserDatabase(BaseUserDatabase[User, uuid.UUID]):
    """Minimal fastapi-users database adapter over the existing user repo."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def get(self, id: uuid.UUID) -> User | None:
        return await self._users.get_by_id(id)

    async def get_by_email(self, email: str) -> User | None:
        return await self._users.get_by_email(normalize_email(email))

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> User | None:
        del oauth
        del account_id
        return None

    async def create(self, create_dict: dict[str, Any]) -> User:
        return await self._users.create_local_user(
            email=normalize_email(str(create_dict["email"])),
            password_hash=str(create_dict["hashed_password"]),
        )

    async def update(self, user: User, update_dict: dict[str, Any]) -> User:
        if "email" in update_dict and update_dict["email"] is not None:
            user.email = normalize_email(str(update_dict["email"]))
        if (
            "hashed_password" in update_dict
            and update_dict["hashed_password"] is not None
        ):
            user.password_hash = str(update_dict["hashed_password"])
        self._session.add(user)
        return user

    async def delete(self, user: User) -> None:
        await self._session.delete(user)

    async def add_oauth_account(self, user: User, create_dict: dict[str, Any]) -> User:
        del create_dict
        return user

    async def update_oauth_account(
        self,
        user: User,
        oauth_account: Any,
        update_dict: dict[str, Any],
    ) -> User:
        del oauth_account
        del update_dict
        return user


class TravelTomUserManager(BaseUserManager[User, uuid.UUID]):
    """Use fastapi-users password and create flows without adopting its routers."""

    reset_password_token_secret = "traveltom-local-reset-token-unused"
    verification_token_secret = "traveltom-local-verify-token-unused"

    def parse_id(self, value: Any) -> uuid.UUID:
        try:
            return uuid.UUID(str(value))
        except ValueError as exc:
            raise InvalidID() from exc

    async def validate_password(
        self, password: str, user: _LocalUserCreate | User
    ) -> None:
        del user
        if len(password) < 8:
            raise InvalidPasswordException(
                reason="Password must be at least 8 characters long"
            )

    async def create_local_user(self, *, email: str, password: str) -> User:
        return await self.create(
            _LocalUserCreate(email=normalize_email(email), password=password),
            safe=True,
        )

    async def authenticate_local_user(
        self, *, email: str, password: str
    ) -> User | None:
        normalized_email = normalize_email(email)
        user = await self.user_db.get_by_email(normalized_email)
        if user is None or not user.password_hash:
            # Match fastapi-users timing-attack mitigation for unknown users.
            self.password_helper.hash(password)
            return None

        verified, updated_hash = self.password_helper.verify_and_update(
            password,
            user.password_hash,
        )
        if not verified:
            return None
        if updated_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_hash})
        return user


def get_local_user_manager(*, session: AsyncSession) -> TravelTomUserManager:
    """Return the request-scoped local user manager."""

    return TravelTomUserManager(TravelTomUserDatabase(session=session))
