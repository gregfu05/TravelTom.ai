"""Shared TravelTom agent entrypoint for API routes."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from functools import lru_cache
from typing import Any, cast

from langchain.agents import create_agent
from langchain.tools import tool
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.api.recommendations import (
    RecommendationQuery as ApiRecommendationQuery,
)
from app.schemas.api.recommendations import RecommendationResponse
from app.schemas.orchestrator import (
    OrchestratorPolicyConfig,
    OrchestratorResponse,
    RecommendationToolRuntimePayload,
    TranscriptMessage,
)
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationConstraints,
    RecommendationQuery,
    RecommendationToolResponse,
)
from app.services.orchestrator.llm_provider import (
    build_chat_model,
    build_direct_recommendation_model,
    map_provider_exception_to_api_error,
)
from app.services.orchestrator.policies import build_empty_results_message
from app.services.orchestrator.providers import (
    OllamaStructuredClient,
    OpenAIStructuredClient,
)
from app.services.orchestrator.runtime_types import AgentRunResult
from app.services.orchestrator.service import (
    OrchestratorService,
    PlannerExecutionError,
    build_direct_query_message,
)
from app.services.recommendation_query import (
    InvalidRecommendationResponseError,
    RecommendationServiceUnavailableError,
    RecommendationTool,
)
from app.services.recommendation_runtime import get_runtime_recommendation_tool

_CHAT_AGENT_SYSTEM_PROMPT = """
You are TravelTom's backend chat agent.

You may either:
- ask a short clarification question, or
- call recommendation_query exactly when grounded recommendations are needed.

Runtime notes:
- hidden system messages contain validated session state, recent transcript, and
  planner-shaped recommendation context
- trust the validated hidden state as the source of truth for captured trip
  details; do not reinterpret the raw user message to mutate constraints
- on underspecified follow-ups like "show me more" or "another option", keep the
  prior recommendation intent unless the user explicitly overrides it
- if the user is exploring destinations, you may start recommendation_query from
  partial signal like vibe, trip length, or budget
- if the user is asking for hotels or flights, wait until destination, dates,
  and budget are grounded
- if the user just supplied the final missing detail for an active
  recommendation flow, call recommendation_query immediately instead of asking
  them to restate the request

Hard rules:
- recommendation_query is the only source of recommendation items
- never invent recommendation items, prices, or availability
- if planner/context already captures destination, dates, budget, or item type,
  do not re-ask for them unless the user is clearly changing them
- do not rely on your own wording for the final user-facing reply; backend
  response composition happens after transcript normalization
- if the tool returns no results, explain that there are no strong matches yet
- if the user message is vague, ask only for the missing trip details you need
""".strip()

_DIRECT_RECOMMENDATION_SYSTEM_PROMPT = """
You are TravelTom's deterministic recommendation executor.

Always call recommendation_query once with the provided serialized request.
Do not add recommendation content of your own.
""".strip()


class TravelTomAgent:
    """Route-facing TravelTom agent built on LangChain create_agent."""

    def __init__(
        self,
        *,
        orchestrator_service: OrchestratorService,
        provider_name: str,
        chat_model: Any,
        direct_recommendation_model: Any,
        structured_client: Any | None = None,
        recommendation_tool: RecommendationTool | None = None,
        policy_config: OrchestratorPolicyConfig | None = None,
    ) -> None:
        self._orchestrator = orchestrator_service
        self._provider_name = provider_name
        self._structured_client = structured_client
        self._recommendation_handler = (
            recommendation_tool or get_runtime_recommendation_tool()
        )
        self._policy = policy_config or OrchestratorPolicyConfig()
        self._recommendation_tool = self._build_recommendation_tool()
        self._chat_agent = create_agent(
            model=chat_model,
            tools=[self._recommendation_tool],
            system_prompt=_CHAT_AGENT_SYSTEM_PROMPT,
            name="traveltom_chat_agent",
        )
        self._direct_recommendation_agent = create_agent(
            model=direct_recommendation_model,
            tools=[self._recommendation_tool],
            system_prompt=_DIRECT_RECOMMENDATION_SYSTEM_PROMPT,
            name="traveltom_direct_recommendation_agent",
        )

    @property
    def uses_langchain(self) -> bool:
        """The runtime requires LangChain for both chat and recommendations."""

        return True

    @property
    def recent_history_limit(self) -> int:
        """Return the bounded transcript window used for orchestration."""

        return self._policy.recent_history_message_limit

    def handle_chat(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        recent_messages: list[TranscriptMessage] | None = None,
    ) -> OrchestratorResponse:
        """Handle chat orchestration through the shared LangChain agent."""

        return self._orchestrator.handle_message(
            user_message=user_message,
            session_state=session_state,
            recent_messages=recent_messages,
            agent_executor=self._invoke_chat_agent,
            planner_executor=self._plan_orchestration,
            recommendation_executor=self._execute_recommendation_query,
        )

    async def handle_recommendation_query(
        self,
        *,
        request: ApiRecommendationQuery,
    ) -> RecommendationResponse:
        """Handle deterministic recommendation requests through a LangChain agent."""

        return await asyncio.to_thread(
            self._invoke_direct_recommendation_agent,
            request,
        )

    def _invoke_chat_agent(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        chat_agent = cast(Any, self._chat_agent)
        try:
            return cast(dict[str, Any], chat_agent.invoke({"messages": messages}))
        except Exception as exc:
            provider_error = map_provider_exception_to_api_error(
                exc,
                provider=cast(Any, self._provider_name),
            )
            if provider_error is not None:
                raise provider_error from exc
            raise

    def _invoke_direct_recommendation_agent(
        self,
        request: ApiRecommendationQuery,
    ) -> RecommendationResponse:
        direct_agent = cast(Any, self._direct_recommendation_agent)
        agent_result = cast(
            dict[str, Any],
            direct_agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": build_direct_query_message(request),
                        }
                    ]
                }
            ),
        )
        runtime_payload = self._orchestrator.response_from_direct_agent_result(
            agent_result=AgentRunResult.from_raw(agent_result)
        )
        if runtime_payload.status == "invalid_payload":
            raise InvalidRecommendationResponseError(
                runtime_payload.error_message
                or "Invalid recommendation service response"
            )
        if runtime_payload.status != "success" or runtime_payload.response is None:
            raise RecommendationServiceUnavailableError(
                runtime_payload.error_message or "Recommendation service unavailable"
            )

        return RecommendationResponse.model_validate(
            runtime_payload.response.model_dump(mode="json")
        )

    def _plan_orchestration(self, prompt: str) -> dict[str, Any] | None:
        if self._structured_client is None:
            return None

        try:
            payload = cast(Any, self._structured_client).plan({"prompt": prompt})
        except Exception as exc:
            raise PlannerExecutionError(str(exc)) from exc
        if not isinstance(payload, dict):
            raise PlannerExecutionError("Planner response was not a JSON object")
        return cast(dict[str, Any], payload)

    def _build_recommendation_tool(self):
        @tool(
            "recommendation_query",
            args_schema=RecommendationQuery,
            description="Run deterministic TravelTom recommendation retrieval.",
            response_format="content_and_artifact",
        )
        def recommendation_query_tool(
            session_id: str,
            query: str,
            constraints: RecommendationConstraints | None = None,
            filters: dict[str, Any] | None = None,
            max_results: int = 20,
            ranking_version: str = "heuristic-v1",
        ) -> tuple[str, dict[str, Any]]:
            runtime_payload = self._run_recommendation_tool(
                session_id=session_id,
                query=query,
                constraints=constraints,
                filters=filters,
                max_results=max_results,
                ranking_version=ranking_version,
            )
            return (
                self._tool_content_from_runtime_payload(runtime_payload),
                runtime_payload.model_dump(mode="json"),
            )

        return recommendation_query_tool

    def _run_recommendation_tool(
        self,
        *,
        session_id: str,
        query: str,
        constraints: RecommendationConstraints | None,
        filters: dict[str, Any] | None,
        max_results: int,
        ranking_version: str,
    ) -> RecommendationToolRuntimePayload:
        try:
            tool_request = RecommendationQuery.model_validate(
                {
                    "session_id": session_id,
                    "query": query,
                    "constraints": constraints or RecommendationConstraints(),
                    "filters": filters or {},
                    "max_results": max_results,
                    "ranking_version": ranking_version,
                }
            )
        except ValidationError as exc:
            return RecommendationToolRuntimePayload(
                status="invalid_payload",
                error_code="invalid_request_payload",
                error_message=str(exc),
            )

        try:
            response = self._execute_recommendation_query(tool_request)
        except FuturesTimeoutError:
            return RecommendationToolRuntimePayload(
                status="timeout",
                error_code="recommendation_timeout",
                error_message="Recommendation query timed out",
            )
        except ValidationError as exc:
            return RecommendationToolRuntimePayload(
                status="invalid_payload",
                error_code="invalid_response_payload",
                error_message=str(exc),
            )
        except Exception as exc:
            return RecommendationToolRuntimePayload(
                status="failure",
                error_code="recommendation_failure",
                error_message=str(exc),
            )

        return RecommendationToolRuntimePayload(
            status="success",
            response=response,
        )

    def _execute_recommendation_query(
        self,
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._recommendation_handler, query)
            raw_output = future.result(
                timeout=self._policy.recommendation_timeout_seconds
            )
        return RecommendationToolResponse.model_validate(raw_output)

    def _tool_content_from_runtime_payload(
        self,
        payload: RecommendationToolRuntimePayload,
    ) -> str:
        if payload.status == "timeout":
            return "Recommendation lookup timed out."
        if payload.status == "invalid_payload":
            return "Recommendation lookup returned an invalid payload."
        if payload.status != "success" or payload.response is None:
            return "Recommendation lookup failed."

        response = payload.response
        if not response.results:
            return build_empty_results_message(SessionState(session_id="tool-result"))

        return self._orchestrator.build_results_message(
            response.results,
            session_state=SessionState(session_id="tool-result"),
        )


@lru_cache()
def get_travel_tom_agent() -> TravelTomAgent:
    """Return the shared TravelTom agent instance used by API routes."""

    settings = get_settings()
    policy = OrchestratorPolicyConfig()
    structured_client: Any | None = None
    if settings.orchestrator_llm_provider == "ollama":
        structured_client = OllamaStructuredClient(
            base_url=settings.ollama_base_url,
            planning_model_name=settings.ollama_planning_model,
            response_model_name=settings.ollama_response_model,
            timeout_seconds=settings.orchestrator_structured_timeout_seconds,
            temperature=settings.ollama_temperature,
        )
    elif settings.orchestrator_llm_provider == "openai":
        api_key = (settings.openai_api_key or "").strip()
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY (or ORCHESTRATOR_OPENAI_API_KEY) is required "
                "when ORCHESTRATOR_LLM_PROVIDER=openai"
            )
        structured_client = OpenAIStructuredClient(
            base_url=settings.openai_base_url,
            api_key=api_key,
            planning_model_name=settings.openai_planning_model,
            response_model_name=settings.openai_response_model,
            timeout_seconds=settings.orchestrator_structured_timeout_seconds,
            temperature=settings.openai_temperature,
        )
    chat_model = build_chat_model(
        provider=settings.orchestrator_llm_provider,
        ollama_base_url=settings.ollama_base_url,
        ollama_chat_model=settings.ollama_response_model,
        llm_timeout_seconds=settings.orchestrator_llm_timeout_seconds,
        ollama_temperature=settings.ollama_temperature,
        openai_base_url=settings.openai_base_url,
        openai_api_key=settings.openai_api_key,
        openai_chat_model=settings.openai_response_model,
        openai_temperature=settings.openai_temperature,
        max_results=policy.max_recommendation_results,
    )
    return TravelTomAgent(
        orchestrator_service=OrchestratorService(policy_config=policy),
        provider_name=settings.orchestrator_llm_provider,
        chat_model=chat_model,
        direct_recommendation_model=build_direct_recommendation_model(),
        structured_client=structured_client,
        recommendation_tool=get_runtime_recommendation_tool(settings=settings),
        policy_config=policy,
    )
