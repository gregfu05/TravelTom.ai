"""Chat endpoint with orchestrator execution and session persistence."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.api.chat import ChatRecommendation, ChatRequest, ChatResponse
from app.schemas.state import SessionState
from app.services.chat_persistence import (
    load_session_state,
    parse_optional_uuid,
    session_pk,
)
from app.services.chat_uow import ChatUnitOfWork
from app.services.orchestrator.service import OrchestratorResponse, OrchestratorService
from traveltom.recommendor.recommendor_v1 import recommendation_tool

router = APIRouter()


@lru_cache()
def get_orchestrator_service() -> OrchestratorService:
    """Return a cached orchestrator service instance."""

    return OrchestratorService(recommendation_tool=recommendation_tool)


def get_chat_uow(db: AsyncSession = Depends(get_db)) -> ChatUnitOfWork:
    """Return chat unit of work bound to the request-scoped DB session."""

    return ChatUnitOfWork(db)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    uow: ChatUnitOfWork = Depends(get_chat_uow),
    orchestrator: OrchestratorService = Depends(get_orchestrator_service),
) -> ChatResponse:
    """Handle a chat message and persist session/message/recommendation records."""

    pk = session_pk(request.session_id)
    user_uuid = parse_optional_uuid(request.user_id)

    try:
        async with uow:
            session_row = await uow.chat_repository.get_or_create_session(
                pk=pk,
                session_id=request.session_id,
                request_user_id=request.user_id,
                user_uuid=user_uuid,
            )
            state = load_session_state(
                raw_state=session_row.state_json,
                session_id=request.session_id,
                user_id=request.user_id,
            )

            orchestration = orchestrator.handle_message(
                user_message=request.message, session_state=state,
            )
            persisted_state = SessionState.model_validate(orchestration.state)
            session_row.state_json = persisted_state.model_dump(mode="json")
            if user_uuid is not None:
                session_row.user_id = user_uuid

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
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session state payload",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message",
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
