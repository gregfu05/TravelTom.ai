"""Chat persistence helpers for session identity and state validation."""

from __future__ import annotations

import uuid
from typing import Any

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


def load_session_state(
    *,
    raw_state: Any,
    session_id: str,
    user_id: str | None,
) -> SessionState:
    """Build a validated ``SessionState`` from the persisted JSON and incoming request."""

    raw_payload: dict[str, Any]
    if isinstance(raw_state, dict):
        raw_payload = dict(raw_state)
    else:
        raw_payload = {}

    raw_payload["session_id"] = session_id
    if user_id is not None:
        raw_payload["user_id"] = user_id

    return SessionState.model_validate(raw_payload)
