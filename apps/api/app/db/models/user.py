"""User model."""

import uuid
from datetime import datetime
from typing import Union

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[Union[str, None]] = mapped_column(Text, unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    auth_issuer: Mapped[str] = mapped_column(Text, nullable=False)
    external_subject: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    weighted_interests: Mapped[dict[str, float]] = mapped_column(
        JSONB(astext_type=Text()),
        nullable=False,
        server_default="{}",
        default=dict,
    )
