"""Chat persistence helpers for session identity and state validation."""

from __future__ import annotations

import uuid
from typing import Any

from app.schemas.state import SessionState


def session_pk(session_id: str) -> uuid.UUID:
    """Map an opaque client session id to a deterministic UUID primary key."""

    return uuid.uuid5(uuid.NAMESPACE_URL, f"traveltom-session:{session_id}")


def load_session_state(
    *,
    raw_state: Any,
    session_id: str,
    user_id: str | None,
) -> SessionState:
    """Build a validated ``SessionState`` from persisted JSON and request data."""

    raw_payload: dict[str, Any]
    if isinstance(raw_state, dict):
        raw_payload = dict(raw_state)
    else:
        raw_payload = {}

    raw_payload["session_id"] = session_id
    if user_id is None:
        raw_payload.pop("user_id", None)
    else:
        raw_payload["user_id"] = user_id

    return SessionState.model_validate(raw_payload)
