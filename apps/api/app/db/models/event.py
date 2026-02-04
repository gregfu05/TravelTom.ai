"""Event model."""

import uuid

from sqlalchemy import DateTime, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_type_time", "event_type", "occurred_at"),
        Index("idx_events_session_time", "session_id", "occurred_at"),
        Index("idx_events_idempotency", "idempotency_key", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(Text, unique=True)
    event_type: Mapped[str] = mapped_column(Text)
    event_version: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
