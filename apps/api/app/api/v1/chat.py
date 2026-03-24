"""Chat endpoint with TravelTom agent execution and session persistence."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ApiError, get_trace_id
from app.core.security import (
    enforce_chat_rate_limit,
    require_authenticated_principal,
)
from app.db.session import get_db
from app.schemas.api.chat import (
    ChatRecommendation,
    ChatRequest,
    ChatResponse,
    ChatSessionMessage,
    ChatSessionResponse,
)
from app.schemas.auth import AuthenticatedPrincipal
from app.schemas.orchestrator import OrchestratorResponse
from app.schemas.state import SessionState
from app.services.chat_persistence import (
    load_session_state,
    session_pk,
)
from app.services.chat_uow import ChatUnitOfWork
from app.services.travel_tom_agent import TravelTomAgent, get_travel_tom_agent

router = APIRouter()
logger = logging.getLogger(__name__)


def get_chat_uow(db: AsyncSession = Depends(get_db)) -> ChatUnitOfWork:
    """Return chat unit of work bound to the request-scoped DB session."""

    return ChatUnitOfWork(db)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    _: None = Depends(enforce_chat_rate_limit),
    principal: AuthenticatedPrincipal | None = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_settings),
    uow: ChatUnitOfWork = Depends(get_chat_uow),
    agent: TravelTomAgent = Depends(get_travel_tom_agent),
) -> ChatResponse:
    """Handle a chat message and persist session/message/recommendation records."""

    pk = session_pk(request.session_id)

    try:
        async with uow:
            owner_user_id = None
            state_user_id = None
            if principal is not None:
                user_row = await uow.user_repository.get_or_create_from_principal(
                    principal
                )
                owner_user_id = user_row.id
                state_user_id = str(user_row.id)

            session_row = await uow.chat_repository.get_or_create_session(
                pk=pk,
                session_id=request.session_id,
                owner_user_id=owner_user_id,
            )
            uow.chat_repository.ensure_session_owner(
                session_row=session_row,
                owner_user_id=owner_user_id,
            )
            state = load_session_state(
                raw_state=session_row.state_json,
                session_id=request.session_id,
                user_id=state_user_id,
            )
            recent_messages = await uow.chat_repository.get_recent_messages(
                pk=pk,
                limit=agent.recent_history_limit,
            )

            orchestration = agent.handle_chat(
                user_message=request.message,
                session_state=state,
                recent_messages=recent_messages,
            )
            persisted_state = SessionState.model_validate(orchestration.state)
            persisted_state.session_id = request.session_id
            persisted_state.user_id = state_user_id
            session_row.state_json = persisted_state.model_dump(mode="json")
            if owner_user_id is not None:
                session_row.user_id = owner_user_id

            await uow.flush()

            uow.chat_repository.add_messages(
                pk=pk,
                user_message=request.message,
                assistant_message=orchestration.assistant_message,
            )
            uow.chat_repository.add_recommendation_snapshot(
                pk=pk,
                message=request.message,
                recommendations=orchestration.recommendations,
                ranking_version=persisted_state.last_recommendation_version
                or "heuristic-v1",
            )

            await uow.commit()
            return _to_chat_response(
                request_message_id=request.message_id,
                orchestration=orchestration,
            )
    except ApiError as exc:
        if exc.code == "provider_rate_limited":
            logger.warning(
                "chat_provider_rate_limited",
                extra={
                    "trace_id": get_trace_id(http_request),
                    "context": {
                        "chat_provider": settings.orchestrator_llm_provider,
                        "error_code": exc.code,
                        "path": str(http_request.url.path),
                        "principal_subject": (
                            principal.subject if principal is not None else None
                        ),
                        "session_id": request.session_id,
                    },
                },
            )
        raise
    except ValidationError as exc:
        raise ApiError(
            status_code=400,
            code="invalid_session_state",
            message="Invalid session state payload",
        ) from exc
    except Exception as exc:
        raise ApiError(
            status_code=500,
            code="chat_processing_failed",
            message="Failed to process chat message",
        ) from exc

    raise RuntimeError("Chat handler completed without producing a response")


@router.get("/chat/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: str,
    principal: AuthenticatedPrincipal | None = Depends(require_authenticated_principal),
    uow: ChatUnitOfWork = Depends(get_chat_uow),
) -> ChatSessionResponse:
    """Return the persisted transcript, state, and latest recommendations."""

    pk = session_pk(session_id)

    try:
        async with uow:
            owner_user_id = None
            state_user_id = None
            if principal is not None:
                user_row = await uow.user_repository.get_or_create_from_principal(
                    principal
                )
                owner_user_id = user_row.id
                state_user_id = str(user_row.id)

            session_row = await uow.chat_repository.get_session(pk=pk)
            if session_row is None:
                raise ApiError(
                    status_code=404,
                    code="session_not_found",
                    message="Chat session was not found",
                )

            uow.chat_repository.ensure_session_owner(
                session_row=session_row,
                owner_user_id=owner_user_id,
            )
            state = load_session_state(
                raw_state=session_row.state_json,
                session_id=session_id,
                user_id=state_user_id,
            )
            messages = await uow.chat_repository.get_messages(pk=pk)
            latest_snapshot = await uow.chat_repository.get_latest_recommendation_snapshot(
                pk=pk
            )
            return _to_chat_session_response(
                session_id=session_id,
                state=state,
                messages=messages,
                raw_recommendations=(
                    latest_snapshot.results_json.get("results", [])
                    if latest_snapshot is not None
                    else []
                ),
            )
    except ValidationError as exc:
        raise ApiError(
            status_code=400,
            code="invalid_session_state",
            message="Invalid session state payload",
        ) from exc


def _to_chat_response(
    *,
    request_message_id: str,
    orchestration: OrchestratorResponse,
) -> ChatResponse:
    """Map orchestrator output to the API response schema."""

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


def _to_chat_session_response(
    *,
    session_id: str,
    state: SessionState,
    messages: list[object],
    raw_recommendations: list[object],
) -> ChatSessionResponse:
    """Map persisted session records to the session hydration API response."""

    transcript = [
        ChatSessionMessage(
            id=str(getattr(message, "id")),
            role=getattr(message, "role"),
            content=getattr(message, "content"),
            created_at=getattr(message, "created_at"),
        )
        for message in messages
        if getattr(message, "role", None) in {"user", "assistant"}
    ]
    recommendations = [
        ChatRecommendation(
            item_id=str(item["item_id"]),
            item_type=item["item_type"],
            score=float(item["score"]),
            rank=int(item["rank"]),
            explanation=str(item["explanation"]),
            metadata=item.get("features") if isinstance(item.get("features"), dict) else None,
        )
        for item in raw_recommendations
        if isinstance(item, dict)
    ]
    return ChatSessionResponse(
        session_id=session_id,
        state=state.model_dump(mode="json"),
        messages=transcript,
        recommendations=recommendations,
    )
