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
)
from app.services.orchestrator.policies import build_empty_results_message
from app.services.orchestrator.service import (
    OrchestratorService,
    build_direct_query_message,
)
from app.services.recommendation_query import (
    InvalidRecommendationResponseError,
    RecommendationServiceUnavailableError,
    RecommendationTool,
)
from traveltom.recommendor.recommendor_v1 import recommendation_tool

_CHAT_AGENT_SYSTEM_PROMPT = """
You are TravelTom's backend chat agent.

You may either:
- ask a short clarification question, or
- call recommendation_query exactly when grounded recommendations are needed.

Hard rules:
- recommendation_query is the only source of recommendation items
- never invent recommendation items, prices, or availability
- use only the tool output when describing recommendations
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
        chat_model: Any,
        direct_recommendation_model: Any,
        recommendation_tool: RecommendationTool = recommendation_tool,
        policy_config: OrchestratorPolicyConfig | None = None,
    ) -> None:
        self._orchestrator = orchestrator_service
        self._recommendation_handler = recommendation_tool
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

    def handle_chat(
        self,
        *,
        user_message: str,
        session_state: SessionState,
    ) -> OrchestratorResponse:
        """Handle chat orchestration through the shared LangChain agent."""

        return self._orchestrator.handle_message(
            user_message=user_message,
            session_state=session_state,
            agent_executor=self._invoke_chat_agent,
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
        return cast(dict[str, Any], chat_agent.invoke({"messages": messages}))

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
            agent_result=agent_result
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

        return self._orchestrator.build_results_message(response.results)


@lru_cache()
def get_travel_tom_agent() -> TravelTomAgent:
    """Return the shared TravelTom agent instance used by API routes."""

    settings = get_settings()
    policy = OrchestratorPolicyConfig()
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
        chat_model=chat_model,
        direct_recommendation_model=build_direct_recommendation_model(),
        recommendation_tool=recommendation_tool,
        policy_config=policy,
    )
