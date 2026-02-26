"""Chat session persistence: session, message, and recommendation snapshot management."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.message import Message
from app.db.models.recommendation import Recommendation
from app.db.models.session import Session
from app.schemas.api.chat import ChatRequest
from app.schemas.state import SessionState


def session_pk(session_id: str) -> uuid.UUID:
    """Map an opaque client session id to a deterministic UUID primary key."""

    return uuid.uuid5(uuid.NAMESPACE_URL, f"traveltom-session:{session_id}")


def parse_optional_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a string to UUID, returning *None* on empty or invalid input."""

    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


async def get_or_create_session(
    *,
    db: AsyncSession,
    pk: uuid.UUID,
    request: ChatRequest,
    user_uuid: uuid.UUID | None,
) -> Session:
    """Return an existing session row or create a new one with default state."""

    result = await db.execute(select(Session).where(Session.id == pk))
    session_row = result.scalar_one_or_none()
    if session_row is not None:
        return session_row

    state_payload = SessionState(
        session_id=request.session_id,
        user_id=request.user_id,
    ).model_dump(mode="json")
    session_row = Session(
        id=pk,
        user_id=user_uuid,
        state_json=state_payload,
    )
    db.add(session_row)
    return session_row


def load_session_state(*, raw_state: Any, request: ChatRequest) -> SessionState:
    """Build a validated ``SessionState`` from the persisted JSON and incoming request."""

    raw_payload: dict[str, Any]
    if isinstance(raw_state, dict):
        raw_payload = dict(raw_state)
    else:
        raw_payload = {}

    raw_payload["session_id"] = request.session_id
    if request.user_id is not None:
        raw_payload["user_id"] = request.user_id

    return SessionState.model_validate(raw_payload)


def persist_messages(
    *,
    db: AsyncSession,
    pk: uuid.UUID,
    user_message: str,
    assistant_message: str,
) -> None:
    """Add user and assistant message rows to the current unit of work."""

    db.add(Message(session_id=pk, role="user", content=user_message))
    db.add(Message(session_id=pk, role="assistant", content=assistant_message))


def persist_recommendation_snapshot(
    *,
    db: AsyncSession,
    pk: uuid.UUID,
    message: str,
    recommendations: list[Any],
    ranking_version: str,
) -> None:
    """Serialize recommendation results and add a snapshot row."""

    payload = {
        "results": [item.model_dump(mode="json") for item in recommendations],
    }
    db.add(
        Recommendation(
            session_id=pk,
            query_hash=_query_hash(pk=pk, message=message),
            results_json=payload,
            ranking_version=ranking_version,
        )
    )


def _query_hash(*, pk: uuid.UUID, message: str) -> str:
    """Return a SHA-256 hex digest scoped to session + message text."""

    digest = hashlib.sha256(f"{pk}:{message}".encode("utf-8"))
    return digest.hexdigest()
