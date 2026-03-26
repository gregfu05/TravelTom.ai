"""User model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "auth_issuer",
            "external_subject",
            name="uq_users_auth_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    auth_issuer: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def hashed_password(self) -> str:
        """Expose the password hash under the fastapi-users protocol name."""

        return self.password_hash or ""

    @hashed_password.setter
    def hashed_password(self, value: str) -> None:
        self.password_hash = value

    @property
    def is_active(self) -> bool:
        """Local and external identities are active unless disabled elsewhere."""

        return True

    @property
    def is_superuser(self) -> bool:
        """TravelTom does not persist backend superuser flags on users."""

        return False

    @property
    def is_verified(self) -> bool:
        """Local accounts are treated as usable immediately after signup."""

        return True
