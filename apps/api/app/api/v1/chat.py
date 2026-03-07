"""Chat endpoint with orchestrator execution and session persistence."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import (
    enforce_chat_rate_limit,
    require_authenticated_principal,
)
from app.db.session import get_db
from app.schemas.api.chat import ChatRecommendation, ChatRequest, ChatResponse
from app.schemas.auth import AuthenticatedPrincipal
from app.schemas.orchestrator import OrchestratorResponse
from app.schemas.state import SessionState
from app.services.chat_persistence import (
    load_session_state,
    session_pk,
)
from app.services.chat_uow import ChatUnitOfWork
from app.services.orchestrator.llm_provider import build_orchestrator_llm_models
from app.services.orchestrator.service import OrchestratorService
from traveltom.recommendor.recommendor_v1 import recommendation_tool

router = APIRouter()


@lru_cache()
def get_orchestrator_service() -> OrchestratorService:
    """Return a cached orchestrator service instance."""

    settings = get_settings()
    llm_models = build_orchestrator_llm_models(
        provider=settings.orchestrator_llm_provider,
        ollama_base_url=settings.ollama_base_url,
        ollama_planning_model=settings.ollama_planning_model,
        ollama_response_model=settings.ollama_response_model,
        llm_timeout_seconds=settings.orchestrator_llm_timeout_seconds,
        ollama_temperature=settings.ollama_temperature,
        openai_base_url=settings.openai_base_url,
        openai_api_key=settings.openai_api_key,
        openai_planning_model=settings.openai_planning_model,
        openai_response_model=settings.openai_response_model,
        openai_temperature=settings.openai_temperature,
    )
    return OrchestratorService(
        recommendation_tool=recommendation_tool,
        planning_model=llm_models.planning_model,
        response_model=llm_models.response_model,
    )


def get_chat_uow(db: AsyncSession = Depends(get_db)) -> ChatUnitOfWork:
    """Return chat unit of work bound to the request-scoped DB session."""

    return ChatUnitOfWork(db)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _: None = Depends(enforce_chat_rate_limit),
    principal: AuthenticatedPrincipal | None = Depends(require_authenticated_principal),
    uow: ChatUnitOfWork = Depends(get_chat_uow),
    orchestrator: OrchestratorService = Depends(get_orchestrator_service),
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

            orchestration = orchestrator.handle_message(
                user_message=request.message,
                session_state=state,
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
    except ApiError:
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
