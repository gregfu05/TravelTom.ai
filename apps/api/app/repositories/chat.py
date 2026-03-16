"""Chat-specific repository for session, message, and snapshot persistence."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.models.message import Message
from app.db.models.recommendation import Recommendation
from app.db.models.session import Session
from app.schemas.orchestrator import TranscriptMessage
from app.schemas.state import SessionState


class ChatRepository:
    """Repository that encapsulates chat persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_session(
        self,
        *,
        pk: uuid.UUID,
        session_id: str,
        owner_user_id: uuid.UUID | None,
    ) -> Session:
        """Return existing session row or create a new one with default state."""

        result = await self._session.execute(select(Session).where(Session.id == pk))
        session_row = result.scalar_one_or_none()
        if session_row is not None:
            return session_row

        state_payload = SessionState(
            session_id=session_id,
            user_id=str(owner_user_id) if owner_user_id is not None else None,
        ).model_dump(mode="json")
        session_row = Session(
            id=pk,
            user_id=owner_user_id,
            state_json=state_payload,
        )
        self._session.add(session_row)
        return session_row

    @staticmethod
    def ensure_session_owner(
        *,
        session_row: Session,
        owner_user_id: uuid.UUID | None,
    ) -> None:
        """Ensure the authenticated user owns the session."""

        if owner_user_id is None:
            return
        if session_row.user_id is None or session_row.user_id != owner_user_id:
            raise ApiError(
                status_code=403,
                code="forbidden",
                message="Session does not belong to the authenticated user",
            )

    def add_messages(
        self,
        *,
        pk: uuid.UUID,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """Add user and assistant message rows to the unit of work."""

        self._session.add(Message(session_id=pk, role="user", content=user_message))
        self._session.add(
            Message(session_id=pk, role="assistant", content=assistant_message)
        )

    def add_recommendation_snapshot(
        self,
        *,
        pk: uuid.UUID,
        message: str,
        recommendations: list[Any],
        ranking_version: str,
    ) -> None:
        """Serialize recommendation results and add a snapshot row."""

        payload = {
            "results": [item.model_dump(mode="json") for item in recommendations],
        }
        self._session.add(
            Recommendation(
                session_id=pk,
                query_hash=self._query_hash(pk=pk, message=message),
                results_json=payload,
                ranking_version=ranking_version,
            )
        )

    async def get_recent_messages(
        self,
        *,
        pk: uuid.UUID,
        limit: int,
    ) -> list[TranscriptMessage]:
        """Return a bounded recent transcript window in chronological order."""

        if limit <= 0:
            return []

        result = await self._session.execute(
            select(Message)
            .where(Message.session_id == pk)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = list(result.scalars())
        rows.reverse()
        transcript: list[TranscriptMessage] = []
        for row in rows:
            if row.role not in {"user", "assistant"}:
                continue
            transcript.append(
                TranscriptMessage(
                    role=row.role,
                    content=row.content,
                )
            )
        return transcript

    @staticmethod
    def _query_hash(*, pk: uuid.UUID, message: str) -> str:
        """Return SHA-256 digest scoped to session id and message text."""

        digest = hashlib.sha256(f"{pk}:{message}".encode("utf-8"))
        return digest.hexdigest()
