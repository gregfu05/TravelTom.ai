"""Shared TravelTom agent entrypoint for API routes."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.api.recommendations import (
    RecommendationQuery as ApiRecommendationQuery,
)
from app.schemas.api.recommendations import RecommendationResponse
from app.schemas.orchestrator import (
    LLMComposedResponse,
    OrchestratorPolicyConfig,
    OrchestratorResponse,
    TranscriptMessage,
)
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationToolResponse,
)
from app.services.orchestrator.providers import (
    OllamaStructuredClient,
    OpenAIStructuredClient,
)
from app.services.orchestrator.service import OrchestratorService
from app.services.recommendation_query import (
    InvalidRecommendationResponseError,
    RecommendationServiceUnavailableError,
    RecommendationTool,
)
from app.services.recommendation_runtime import get_runtime_recommendation_tool

logger = logging.getLogger(__name__)


@dataclass
class _ProviderStageCircuit:
    """Track provider failures for a single stage."""

    stage_name: str
    failure_threshold: int
    cooldown_seconds: float
    consecutive_failures: int = 0
    open_until: datetime | None = None

    def is_open(self) -> bool:
        if self.open_until is None:
            return False
        if self.open_until <= datetime.now(timezone.utc):
            self.open_until = None
            self.consecutive_failures = 0
            return False
        return True

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.open_until = None

    def record_failure(self) -> bool:
        self.consecutive_failures += 1
        if self.consecutive_failures < self.failure_threshold:
            return False
        self.open_until = datetime.now(timezone.utc) + timedelta(
            seconds=self.cooldown_seconds
        )
        return True


class TravelTomAgent:
    """Route-facing TravelTom adapter for planning, composition, and search."""

    def __init__(
        self,
        *,
        orchestrator_service: OrchestratorService,
        provider_name: str,
        planner_client: Any | None = None,
        composer_client: Any | None = None,
        recommendation_tool: RecommendationTool | None = None,
        policy_config: OrchestratorPolicyConfig | None = None,
        provider_failure_threshold: int = 2,
        provider_cooldown_seconds: float = 60.0,
    ) -> None:
        self._orchestrator = orchestrator_service
        self._provider_name = provider_name
        self._planner_client = planner_client
        self._composer_client = composer_client
        self._recommendation_handler = (
            recommendation_tool or get_runtime_recommendation_tool()
        )
        self._policy = policy_config or OrchestratorPolicyConfig()
        self._planner_circuit = _ProviderStageCircuit(
            stage_name="planner",
            failure_threshold=provider_failure_threshold,
            cooldown_seconds=provider_cooldown_seconds,
        )
        self._composer_circuit = _ProviderStageCircuit(
            stage_name="composer",
            failure_threshold=provider_failure_threshold,
            cooldown_seconds=provider_cooldown_seconds,
        )

    @property
    def uses_langchain(self) -> bool:
        """The chat runtime no longer depends on LangChain execution."""

        return False

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
        """Handle chat through deterministic orchestration with optional LLM help."""

        return self._orchestrator.handle_message(
            user_message=user_message,
            session_state=session_state,
            recent_messages=recent_messages,
            planner_executor=self._plan_orchestration,
            recommendation_executor=self._execute_recommendation_query,
            response_composer=self._compose_response,
        )

    async def handle_recommendation_query(
        self,
        *,
        request: ApiRecommendationQuery,
    ) -> RecommendationResponse:
        """Handle direct deterministic recommendation requests."""

        return await asyncio.to_thread(
            self._invoke_deterministic_recommendation_query,
            request,
        )

    def _invoke_deterministic_recommendation_query(
        self,
        request: ApiRecommendationQuery,
    ) -> RecommendationResponse:
        tool_request = RecommendationQuery.model_validate(
            request.model_dump(mode="json")
        )
        try:
            response = self._execute_recommendation_query(tool_request)
        except ValidationError as exc:
            raise InvalidRecommendationResponseError(
                "Invalid recommendation service response"
            ) from exc
        except FuturesTimeoutError as exc:
            raise RecommendationServiceUnavailableError(
                "Recommendation query timed out"
            ) from exc
        except Exception as exc:
            raise RecommendationServiceUnavailableError(
                "Recommendation service unavailable"
            ) from exc

        return RecommendationResponse.model_validate(response.model_dump(mode="json"))

    def _plan_orchestration(self, prompt: str) -> dict[str, Any] | None:
        return self._run_structured_stage(
            circuit=self._planner_circuit,
            client=self._planner_client,
            prompt=prompt,
            stage_name="planner",
            validator=lambda payload: payload if isinstance(payload, dict) else None,
            executor=lambda client, prompt_text: client.plan({"prompt": prompt_text}),
        )

    def _compose_response(self, prompt: str) -> str | None:
        payload = self._run_structured_stage(
            circuit=self._composer_circuit,
            client=self._composer_client,
            prompt=prompt,
            stage_name="composer",
            validator=self._validate_composed_response,
            executor=lambda client, prompt_text: client.compose({"prompt": prompt_text}),
        )
        if not isinstance(payload, dict):
            return None
        return str(payload["assistant_message"])

    def _run_structured_stage(
        self,
        *,
        circuit: _ProviderStageCircuit,
        client: Any | None,
        prompt: str,
        stage_name: str,
        validator: Any,
        executor: Any,
    ) -> dict[str, Any] | None:
        if client is None:
            return None
        if circuit.is_open():
            logger.info(
                "provider_stage_skipped",
                extra={
                    "context": {
                        "provider": self._provider_name,
                        "stage": stage_name,
                        "reason": "circuit_open",
                    }
                },
            )
            return None

        try:
            raw_payload = executor(client, prompt)
            validated_payload = validator(raw_payload)
        except Exception as exc:
            circuit_opened = circuit.record_failure()
            logger.warning(
                "provider_stage_failed",
                extra={
                    "context": {
                        "provider": self._provider_name,
                        "stage": stage_name,
                        "error": str(exc),
                        "circuit_opened": circuit_opened,
                        "consecutive_failures": circuit.consecutive_failures,
                    }
                },
            )
            return None

        circuit.record_success()
        logger.info(
            "provider_stage_succeeded",
            extra={
                "context": {
                    "provider": self._provider_name,
                    "stage": stage_name,
                }
            },
        )
        return validated_payload

    def _validate_composed_response(
        self,
        payload: Any,
    ) -> dict[str, Any]:
        validated_payload = LLMComposedResponse.model_validate(payload)
        return validated_payload.model_dump(mode="json")

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


@lru_cache()
def get_travel_tom_agent() -> TravelTomAgent:
    """Return the shared TravelTom agent instance used by API routes."""

    settings = get_settings()
    policy = OrchestratorPolicyConfig()
    planner_client: Any | None = None
    composer_client: Any | None = None
    planner_timeout_seconds = (
        settings.orchestrator_planner_timeout_seconds
        or settings.orchestrator_structured_timeout_seconds
    )
    composer_timeout_seconds = (
        settings.orchestrator_composer_timeout_seconds
        or settings.orchestrator_structured_timeout_seconds
    )

    if settings.orchestrator_llm_provider == "ollama":
        planner_client = OllamaStructuredClient(
            base_url=settings.ollama_base_url,
            planning_model_name=settings.ollama_planning_model,
            response_model_name=settings.ollama_response_model,
            timeout_seconds=planner_timeout_seconds,
            temperature=settings.ollama_temperature,
        )
        composer_client = OllamaStructuredClient(
            base_url=settings.ollama_base_url,
            planning_model_name=settings.ollama_planning_model,
            response_model_name=settings.ollama_response_model,
            timeout_seconds=composer_timeout_seconds,
            temperature=settings.ollama_temperature,
        )
    elif settings.orchestrator_llm_provider == "openai":
        api_key = (settings.openai_api_key or "").strip()
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY (or ORCHESTRATOR_OPENAI_API_KEY) is required "
                "when ORCHESTRATOR_LLM_PROVIDER=openai"
            )
        planner_client = OpenAIStructuredClient(
            base_url=settings.openai_base_url,
            api_key=api_key,
            planning_model_name=settings.openai_planning_model,
            response_model_name=settings.openai_response_model,
            timeout_seconds=planner_timeout_seconds,
            temperature=settings.openai_temperature,
        )
        composer_client = OpenAIStructuredClient(
            base_url=settings.openai_base_url,
            api_key=api_key,
            planning_model_name=settings.openai_planning_model,
            response_model_name=settings.openai_response_model,
            timeout_seconds=composer_timeout_seconds,
            temperature=settings.openai_temperature,
        )

    return TravelTomAgent(
        orchestrator_service=OrchestratorService(policy_config=policy),
        provider_name=settings.orchestrator_llm_provider,
        planner_client=planner_client,
        composer_client=composer_client,
        recommendation_tool=get_runtime_recommendation_tool(settings=settings),
        policy_config=policy,
        provider_failure_threshold=settings.orchestrator_provider_failure_threshold,
        provider_cooldown_seconds=settings.orchestrator_provider_cooldown_seconds,
    )
