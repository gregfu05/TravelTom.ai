"""LangChain-native chat model construction for TravelTom agents."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Literal, Sequence

from fastapi import status
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from openai import RateLimitError as OpenAIRateLimitError

from app.core.errors import ApiError
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationResult,
    RecommendationToolResponse,
)
from app.services.orchestrator.extraction import extract_query_filters
from app.services.orchestrator.policies import (
    build_clarification_message,
    build_empty_results_message,
    build_guardrail_plan,
    build_tool_failure_message,
    build_tool_timeout_message,
    decide_next_action,
)
from app.services.orchestrator.providers.ollama import (
    get_ollama_available_model_names,
    match_ollama_model_name,
)
from app.services.orchestrator.service import (
    extract_direct_query,
    extract_runtime_recommendation_context,
    extract_runtime_state,
)

ProviderName = Literal["disabled", "ollama", "openai"]


def build_chat_model(
    *,
    provider: ProviderName,
    ollama_base_url: str,
    ollama_chat_model: str,
    llm_timeout_seconds: float,
    ollama_temperature: float,
    openai_base_url: str,
    openai_api_key: str | None,
    openai_chat_model: str,
    openai_temperature: float,
    max_results: int,
) -> BaseChatModel:
    """Create the configured chat model for the LangChain chat agent."""

    if provider == "disabled":
        return DeterministicTravelTomChatModel(max_results=max_results)

    if provider == "ollama":
        resolved_model_name = ollama_chat_model
        try:
            available_model_names = get_ollama_available_model_names(
                base_url=ollama_base_url,
                timeout_seconds=llm_timeout_seconds,
            )
        except Exception:
            available_model_names = []
        if available_model_names:
            matched_model_name = match_ollama_model_name(
                ollama_chat_model,
                available_model_names,
            )
            if matched_model_name is None:
                available_models = ", ".join(sorted(available_model_names))
                raise ValueError(
                    "Configured Ollama chat model "
                    f"'{ollama_chat_model}' was not found. Available models: "
                    f"{available_models}"
                )
            resolved_model_name = matched_model_name
        return ChatOllama(
            model=resolved_model_name,
            base_url=ollama_base_url,
            temperature=ollama_temperature,
            num_predict=512,
            validate_model_on_init=False,
        )

    if provider == "openai":
        api_key = (openai_api_key or "").strip()
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY (or ORCHESTRATOR_OPENAI_API_KEY) is required "
                "when ORCHESTRATOR_LLM_PROVIDER=openai"
            )
        return ChatOpenAI(
            model=openai_chat_model,
            api_key=api_key,
            base_url=openai_base_url,
            temperature=openai_temperature,
            timeout=llm_timeout_seconds,
            max_retries=1,
        )

    raise ValueError(f"Unsupported orchestrator LLM provider: {provider}")


def map_provider_exception_to_api_error(
    exc: Exception,
    *,
    provider: ProviderName,
) -> ApiError | None:
    """Map upstream provider rate-limit failures to a structured API error."""

    if provider == "disabled":
        return None

    for candidate in _iter_exception_chain(exc):
        candidate_status = _extract_status_code(candidate)
        if not _looks_like_rate_limit(candidate, status_code=candidate_status):
            continue

        retry_after_seconds = _extract_retry_after_seconds(candidate)
        details: dict[str, Any] = {
            "provider": provider,
            "source": "provider",
            "upstream_error_type": type(candidate).__name__,
            "upstream_status_code": candidate_status
            or status.HTTP_429_TOO_MANY_REQUESTS,
        }
        if retry_after_seconds is not None:
            details["retry_after_seconds"] = retry_after_seconds

        headers = (
            {"Retry-After": str(retry_after_seconds)}
            if retry_after_seconds is not None
            else None
        )
        return ApiError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="provider_rate_limited",
            message="Upstream chat provider is rate limited",
            details=details,
            headers=headers,
        )

    return None


def build_direct_recommendation_model() -> BaseChatModel:
    """Create the deterministic model used by direct recommendation agents."""

    return DeterministicRecommendationAgentModel()


def _iter_exception_chain(exc: Exception):
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _extract_status_code(candidate: BaseException) -> int | None:
    status_code = getattr(candidate, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(candidate, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status
    return None


def _looks_like_rate_limit(
    candidate: BaseException, *, status_code: int | None
) -> bool:
    if isinstance(candidate, OpenAIRateLimitError):
        return True
    if status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return True

    message = str(candidate).casefold()
    return "rate limit" in message or "quota" in message


def _extract_retry_after_seconds(candidate: BaseException) -> int | None:
    response = getattr(candidate, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None

    retry_after = headers.get("retry-after")
    if retry_after is None:
        retry_after = headers.get("Retry-After")
    if retry_after is None:
        return None

    raw_value = str(retry_after).strip()
    if not raw_value:
        return None
    if raw_value.isdigit():
        return max(0, int(raw_value))

    try:
        reset_at = parsedate_to_datetime(raw_value)
    except (TypeError, ValueError, IndexError):
        return None
    if reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)
    return max(0, int((reset_at - datetime.now(timezone.utc)).total_seconds()))


class _BoundDeterministicToolModel(Runnable):
    """Minimal runnable wrapper used by deterministic agent test models."""

    def __init__(self, model: "_DeterministicToolCallingModel") -> None:
        self._model = model

    def invoke(self, input: Any, config: Any | None = None, **kwargs: Any) -> AIMessage:
        del config
        if isinstance(input, list):
            messages = input
        else:
            messages = input.to_messages()
        return self._model.invoke(messages, **kwargs)


class _DeterministicToolCallingModel(BaseChatModel):
    """Base model for deterministic create_agent-backed TravelTom flows."""

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable:
        del tools
        del tool_choice
        del kwargs
        return _BoundDeterministicToolModel(self)

    @property
    def _llm_type(self) -> str:
        return "traveltom-deterministic"


class DeterministicTravelTomChatModel(_DeterministicToolCallingModel):
    """Fallback chat model that still runs through LangChain create_agent."""

    max_results: int = 5

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop
        del run_manager
        del kwargs

        tool_message = self._last_tool_message(messages)
        session_state = extract_runtime_state(messages) or SessionState(
            session_id="unknown-session"
        )
        if tool_message is not None:
            response = self._response_from_tool_message(
                tool_message=tool_message,
                session_state=session_state,
            )
            return ChatResult(generations=[ChatGeneration(message=response)])

        user_message = self._latest_user_message(messages)
        decision = decide_next_action(user_message, session_state)
        if not decision.should_call_recommendation_tool:
            response = AIMessage(
                content=(
                    build_guardrail_plan(
                        message=user_message,
                        session_state=session_state,
                        max_results=self.max_results,
                    ).clarification_message
                    or build_clarification_message(session_state)
                )
            )
            return ChatResult(generations=[ChatGeneration(message=response)])

        tool_call = {
            "name": "recommendation_query",
            "args": self._build_tool_args(
                session_state=session_state,
                user_message=user_message,
                messages=messages,
            ),
            "id": "recommendation_query_call",
            "type": "tool_call",
        }
        response = AIMessage(content="", tool_calls=[tool_call])
        return ChatResult(generations=[ChatGeneration(message=response)])

    def _response_from_tool_message(
        self,
        *,
        tool_message: ToolMessage,
        session_state: SessionState,
    ) -> AIMessage:
        artifact = getattr(tool_message, "artifact", None) or {}
        status = artifact.get("status")
        if status == "timeout":
            return AIMessage(content=build_tool_timeout_message())
        if status == "invalid_payload":
            return AIMessage(
                content=(
                    "I received an invalid recommendation payload, so I stopped "
                    "rather than guess."
                )
            )
        if status != "success":
            return AIMessage(content=build_tool_failure_message())

        response_payload = artifact.get("response") or {}
        try:
            response = RecommendationToolResponse.model_validate(response_payload)
        except Exception:
            return AIMessage(content=build_tool_failure_message())

        if not response.results:
            return AIMessage(content=build_empty_results_message(session_state))

        return AIMessage(
            content=_build_results_message(response.results, self.max_results)
        )

    def _build_tool_args(
        self,
        *,
        session_state: SessionState,
        user_message: str,
        messages: Sequence[BaseMessage],
    ) -> dict[str, Any]:
        constraints: dict[str, Any] = {}
        if session_state.constraints.origin:
            constraints["origin"] = session_state.constraints.origin
        if session_state.constraints.destination:
            constraints["destination"] = session_state.constraints.destination
        if session_state.constraints.dates:
            constraints["dates"] = session_state.constraints.dates.model_dump(
                mode="json"
            )
        if session_state.constraints.budget:
            constraints["budget"] = session_state.constraints.budget.model_dump(
                mode="json"
            )
        if session_state.constraints.party_size:
            constraints["party_size"] = (
                session_state.constraints.party_size.model_dump()
            )

        recommendation_context = extract_runtime_recommendation_context(messages)
        query_text = recommendation_context.get("effective_query")
        if not isinstance(query_text, str) or not query_text.strip():
            query_text = user_message

        filters = extract_query_filters(user_message)
        effective_item_type = recommendation_context.get("effective_item_type")
        if (
            not filters
            and isinstance(effective_item_type, str)
            and effective_item_type in {"destination", "hotel", "flight"}
        ):
            filters = {"item_type": effective_item_type}
        if not filters:
            filters = {"item_type": "destination"}
        payload = RecommendationQuery(
            session_id=session_state.session_id,
            query=query_text,
            constraints=constraints,
            filters=filters,
            max_results=self.max_results,
            ranking_version="heuristic-v1",
        )
        return payload.model_dump(mode="json")

    def _latest_user_message(self, messages: Sequence[BaseMessage]) -> str:
        for message in reversed(messages):
            if getattr(message, "type", None) != "human":
                continue
            content = getattr(message, "content", "")
            if isinstance(content, str):
                return content
        return ""

    def _last_tool_message(self, messages: Sequence[BaseMessage]) -> ToolMessage | None:
        for message in reversed(messages):
            if (
                isinstance(message, ToolMessage)
                and message.name == "recommendation_query"
            ):
                return message
        return None


class DeterministicRecommendationAgentModel(_DeterministicToolCallingModel):
    """Model that forces a single deterministic recommendation tool invocation."""

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop
        del run_manager
        del kwargs

        tool_message = self._last_tool_message(messages)
        if tool_message is not None:
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content="done"))]
            )

        request = extract_direct_query(messages)
        if request is None:
            return ChatResult(
                generations=[
                    ChatGeneration(
                        message=AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "recommendation_query",
                                    "args": {},
                                    "id": "recommendation_query_call",
                                    "type": "tool_call",
                                }
                            ],
                        )
                    )
                ]
            )

        tool_call = {
            "name": "recommendation_query",
            "args": request.model_dump(mode="json"),
            "id": "recommendation_query_call",
            "type": "tool_call",
        }
        return ChatResult(
            generations=[
                ChatGeneration(message=AIMessage(content="", tool_calls=[tool_call]))
            ]
        )

    def _last_tool_message(self, messages: Sequence[BaseMessage]) -> ToolMessage | None:
        for message in reversed(messages):
            if (
                isinstance(message, ToolMessage)
                and message.name == "recommendation_query"
            ):
                return message
        return None


def _build_results_message(
    results: list[RecommendationResult],
    max_results: int,
) -> str:
    preview_items = "\n".join(
        f"{i}. {_recommendation_display_name(item)}"
        for i, item in enumerate(results[: max(1, max_results)], start=1)
    )
    return (
        f"I found {len(results)} grounded option(s) that fit what you asked for. "
        f"My top picks are:\n{preview_items}"
    )


def _recommendation_display_name(item: RecommendationResult) -> str:
    name = item.features.get("name")
    if isinstance(name, str):
        normalized = name.strip()
        if normalized:
            return normalized
    return item.item_id
