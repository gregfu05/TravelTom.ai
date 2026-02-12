"""Chat endpoint with orchestrator execution and session persistence."""

from __future__ import annotations

import hashlib
import uuid
from functools import lru_cache
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.message import Message
from app.db.models.recommendation import Recommendation
from app.db.models.session import Session
from app.db.session import get_db
from app.schemas.state import SessionState
from app.services.orchestrator.service import OrchestratorResponse, OrchestratorService

router = APIRouter()


class ClientContext(BaseModel):
    """Optional metadata provided by the client application."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    timezone: str | None = None
    locale: str | None = None
    currency: str | None = None


class ChatRequest(BaseModel):
    """Request payload for the chat endpoint."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    user_id: str | None = None
    message: str = Field(min_length=1)
    client_context: ClientContext | None = None


class ChatRecommendation(BaseModel):
    """Recommendation payload returned to the web client."""

    item_id: str
    item_type: Literal["destination", "hotel", "flight"]
    score: float
    rank: int
    explanation: str
    metadata: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    """Response payload for the chat endpoint."""

    session_id: str
    message_id: str
    assistant_message: str
    recommendations: list[ChatRecommendation] = Field(default_factory=list)
    itinerary: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any]


@lru_cache()
def get_orchestrator_service() -> OrchestratorService:
    """Return a cached orchestrator service instance."""

    return OrchestratorService()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    orchestrator: OrchestratorService = Depends(get_orchestrator_service),
) -> ChatResponse:
    """Handle a chat message and persist session/message/recommendation records."""

    session_pk = _session_pk(request.session_id)
    request_user_uuid = _parse_optional_uuid(request.user_id)

    try:
        session_row = await _get_or_create_session(
            db=db,
            session_pk=session_pk,
            request=request,
            request_user_uuid=request_user_uuid,
        )
        session_state = _load_session_state(
            raw_state=session_row.state_json,
            request=request,
        )

        orchestration = orchestrator.handle_message(
            user_message=request.message,
            session_state=session_state,
        )
        persisted_state = SessionState.model_validate(orchestration.state)
        session_row.state_json = persisted_state.model_dump(mode="json")
        if request_user_uuid is not None:
            session_row.user_id = request_user_uuid

        _persist_messages(
            db=db,
            session_pk=session_pk,
            user_message=request.message,
            assistant_message=orchestration.assistant_message,
        )
        _persist_recommendation_snapshot(
            db=db,
            session_pk=session_pk,
            message=request.message,
            recommendations=orchestration.recommendations,
            ranking_version=persisted_state.last_recommendation_version
            or "heuristic-v1",
        )

        await db.commit()
    except ValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session state payload",
        ) from exc
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message",
        ) from exc

    return _to_chat_response(
        request_message_id=request.message_id,
        orchestration=orchestration,
    )


def _session_pk(session_id: str) -> uuid.UUID:
    """Map an opaque client session id to a deterministic UUID primary key."""

    return uuid.uuid5(uuid.NAMESPACE_URL, f"traveltom-session:{session_id}")


def _parse_optional_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


async def _get_or_create_session(
    *,
    db: AsyncSession,
    session_pk: uuid.UUID,
    request: ChatRequest,
    request_user_uuid: uuid.UUID | None,
) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_pk))
    session_row = result.scalar_one_or_none()
    if session_row is not None:
        return session_row

    state_payload = SessionState(
        session_id=request.session_id,
        user_id=request.user_id,
    ).model_dump(mode="json")
    session_row = Session(
        id=session_pk,
        user_id=request_user_uuid,
        state_json=state_payload,
    )
    db.add(session_row)
    return session_row


def _load_session_state(*, raw_state: Any, request: ChatRequest) -> SessionState:
    raw_payload: dict[str, Any]
    if isinstance(raw_state, dict):
        raw_payload = dict(raw_state)
    else:
        raw_payload = {}

    raw_payload["session_id"] = request.session_id
    if request.user_id is not None:
        raw_payload["user_id"] = request.user_id

    return SessionState.model_validate(raw_payload)


def _persist_messages(
    *,
    db: AsyncSession,
    session_pk: uuid.UUID,
    user_message: str,
    assistant_message: str,
) -> None:
    db.add(Message(session_id=session_pk, role="user", content=user_message))
    db.add(Message(session_id=session_pk, role="assistant", content=assistant_message))


def _persist_recommendation_snapshot(
    *,
    db: AsyncSession,
    session_pk: uuid.UUID,
    message: str,
    recommendations: list[Any],
    ranking_version: str,
) -> None:
    payload = {
        "results": [item.model_dump(mode="json") for item in recommendations],
    }
    db.add(
        Recommendation(
            session_id=session_pk,
            query_hash=_query_hash(session_pk=session_pk, message=message),
            results_json=payload,
            ranking_version=ranking_version,
        )
    )


def _query_hash(*, session_pk: uuid.UUID, message: str) -> str:
    digest = hashlib.sha256(f"{session_pk}:{message}".encode("utf-8"))
    return digest.hexdigest()


def _to_chat_response(
    *,
    request_message_id: str,
    orchestration: OrchestratorResponse,
) -> ChatResponse:
    recommendations = [
        ChatRecommendation(
            item_id=item.item_id,
            item_type=item.item_type,
            score=item.score,
            rank=item.rank,
            explanation=item.explanation,
            metadata=item.features or None,
        )
        for item in orchestration.recommendations
    ]
    return ChatResponse(
        session_id=orchestration.session_id,
        message_id=request_message_id,
        assistant_message=orchestration.assistant_message,
        recommendations=recommendations,
        itinerary=orchestration.itinerary,
        state=orchestration.state,
    )
