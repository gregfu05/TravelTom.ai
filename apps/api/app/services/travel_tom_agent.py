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
from app.core.telemetry import start_span
from app.schemas.api.recommendations import (
    RecommendationQuery as ApiRecommendationQuery,
)
from app.schemas.api.recommendations import RecommendationResponse
from app.schemas.orchestrator import (
    LLMComposedResponse,
    OrchestratorDiagnostics,
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
_LOCAL_OLLAMA_MIN_PLANNER_TIMEOUT_SECONDS = 60.0
_LOCAL_OLLAMA_MIN_COMPOSER_TIMEOUT_SECONDS = 90.0


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
        local_environment: bool = False,
    ) -> None:
        self._orchestrator = orchestrator_service
        self._provider_name = provider_name
        self._planner_client = planner_client
        self._composer_client = composer_client
        self._recommendation_handler = (
            recommendation_tool or get_runtime_recommendation_tool()
        )
        self._policy = policy_config or OrchestratorPolicyConfig()
        self._local_environment = local_environment
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

        diagnostics = OrchestratorDiagnostics(provider=self._provider_name)
        with start_span("orchestrator.turn", provider=self._provider_name) as span:
            response = self._orchestrator.handle_message(
                user_message=user_message,
                session_state=session_state,
                recent_messages=recent_messages,
                planner_executor=lambda prompt: self._plan_orchestration(
                    prompt,
                    diagnostics=diagnostics,
                ),
                recommendation_executor=self._execute_recommendation_query,
                response_composer=lambda prompt: self._compose_response(
                    prompt,
                    diagnostics=diagnostics,
                ),
                diagnostics=diagnostics,
            )
            if span is not None:
                span.set_attribute(
                    "orchestrator.planner_attempted", diagnostics.planner_attempted
                )
                span.set_attribute(
                    "orchestrator.planner_used", diagnostics.planner_used
                )
                span.set_attribute(
                    "orchestrator.planner_status", diagnostics.planner_status
                )
                span.set_attribute(
                    "orchestrator.composer_attempted", diagnostics.composer_attempted
                )
                span.set_attribute(
                    "orchestrator.composer_used", diagnostics.composer_used
                )
                span.set_attribute(
                    "orchestrator.composer_status", diagnostics.composer_status
                )
                span.set_attribute("orchestrator.degraded", diagnostics.degraded)
                if diagnostics.fallback_reason is not None:
                    span.set_attribute(
                        "orchestrator.fallback_reason",
                        diagnostics.fallback_reason,
                    )
        logger.info(
            "orchestrator_turn_completed",
            extra={
                "context": {
                    "provider": self._provider_name,
                    "planner_attempted": diagnostics.planner_attempted,
                    "planner_used": diagnostics.planner_used,
                    "planner_status": diagnostics.planner_status,
                    "composer_attempted": diagnostics.composer_attempted,
                    "composer_used": diagnostics.composer_used,
                    "composer_status": diagnostics.composer_status,
                    "fallback_reason": diagnostics.fallback_reason,
                    "degraded": diagnostics.degraded,
                }
            },
        )
        return response

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

    def _plan_orchestration(
        self,
        prompt: str,
        *,
        diagnostics: OrchestratorDiagnostics | None = None,
    ) -> dict[str, Any] | None:
        return self._run_structured_stage(
            circuit=self._planner_circuit,
            client=self._planner_client,
            prompt=prompt,
            stage_name="planner",
            validator=lambda payload: payload if isinstance(payload, dict) else None,
            executor=lambda client, prompt_text: client.plan({"prompt": prompt_text}),
            diagnostics=diagnostics,
        )

    def _compose_response(
        self,
        prompt: str,
        *,
        diagnostics: OrchestratorDiagnostics | None = None,
    ) -> str | None:
        payload = self._run_structured_stage(
            circuit=self._composer_circuit,
            client=self._composer_client,
            prompt=prompt,
            stage_name="composer",
            validator=self._validate_composed_response,
            executor=lambda client, prompt_text: client.compose(
                {"prompt": prompt_text}
            ),
            diagnostics=diagnostics,
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
        diagnostics: OrchestratorDiagnostics | None = None,
    ) -> dict[str, Any] | None:
        if client is None:
            status = (
                "disabled"
                if self._provider_name == "disabled"
                else "client_unavailable"
            )
            self._mark_stage_diagnostics(
                diagnostics,
                stage_name=stage_name,
                attempted=False,
                status=status,
            )
            self._log_stage_degraded(stage_name=stage_name, reason=status)
            return None
        if circuit.is_open():
            self._mark_stage_diagnostics(
                diagnostics,
                stage_name=stage_name,
                attempted=False,
                status="circuit_open",
            )
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
            self._log_stage_degraded(stage_name=stage_name, reason="circuit_open")
            return None

        try:
            raw_payload = executor(client, prompt)
            validated_payload = validator(raw_payload)
        except Exception as exc:
            circuit_opened = circuit.record_failure()
            self._mark_stage_diagnostics(
                diagnostics,
                stage_name=stage_name,
                attempted=True,
                status="failed",
            )
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
            self._log_stage_degraded(stage_name=stage_name, reason="failed")
            return None
        if validated_payload is None:
            circuit_opened = circuit.record_failure()
            self._mark_stage_diagnostics(
                diagnostics,
                stage_name=stage_name,
                attempted=True,
                status="invalid_output",
            )
            logger.warning(
                "provider_stage_failed",
                extra={
                    "context": {
                        "provider": self._provider_name,
                        "stage": stage_name,
                        "error": "validator returned no usable payload",
                        "circuit_opened": circuit_opened,
                        "consecutive_failures": circuit.consecutive_failures,
                    }
                },
            )
            self._log_stage_degraded(stage_name=stage_name, reason="invalid_output")
            return None

        circuit.record_success()
        self._mark_stage_diagnostics(
            diagnostics,
            stage_name=stage_name,
            attempted=True,
            status="succeeded",
        )
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

    def _mark_stage_diagnostics(
        self,
        diagnostics: OrchestratorDiagnostics | None,
        *,
        stage_name: str,
        attempted: bool,
        status: str,
    ) -> None:
        if diagnostics is None:
            return
        if stage_name == "planner":
            diagnostics.planner_attempted = attempted
            diagnostics.planner_status = status
        else:
            diagnostics.composer_attempted = attempted
            diagnostics.composer_status = status
        if self._provider_name != "disabled" and status not in {
            "succeeded",
            "skipped_fast_path",
            "not_requested",
        }:
            diagnostics.degraded = True

    def _log_stage_degraded(self, *, stage_name: str, reason: str) -> None:
        if self._provider_name == "disabled" or not self._local_environment:
            return
        logger.warning(
            "provider_stage_degraded",
            extra={
                "context": {
                    "provider": self._provider_name,
                    "stage": stage_name,
                    "reason": reason,
                }
            },
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
    planner_timeout_seconds = _resolve_structured_stage_timeout_seconds(
        provider_name=settings.orchestrator_llm_provider,
        stage_name="planner",
        timeout_seconds=planner_timeout_seconds,
        local_environment=settings.is_local_environment,
    )
    composer_timeout_seconds = _resolve_structured_stage_timeout_seconds(
        provider_name=settings.orchestrator_llm_provider,
        stage_name="composer",
        timeout_seconds=composer_timeout_seconds,
        local_environment=settings.is_local_environment,
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
    elif settings.orchestrator_llm_provider == "phi35mini":
        planner_client = OllamaStructuredClient(
            base_url=settings.phi35mini_base_url,
            planning_model_name=settings.phi35mini_planning_model,
            response_model_name=settings.phi35mini_response_model,
            timeout_seconds=planner_timeout_seconds,
            temperature=settings.phi35mini_temperature,
        )
        composer_client = OllamaStructuredClient(
            base_url=settings.phi35mini_base_url,
            planning_model_name=settings.phi35mini_planning_model,
            response_model_name=settings.phi35mini_response_model,
            timeout_seconds=composer_timeout_seconds,
            temperature=settings.phi35mini_temperature,
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
        local_environment=settings.is_local_environment,
    )


def _resolve_structured_stage_timeout_seconds(
    *,
    provider_name: str,
    stage_name: str,
    timeout_seconds: float,
    local_environment: bool,
) -> float:
    """Give local Ollama enough time for structured planner/composer turns."""

    if provider_name not in {"ollama", "phi35mini"} or not local_environment:
        return timeout_seconds
    if stage_name == "composer":
        return max(timeout_seconds, _LOCAL_OLLAMA_MIN_COMPOSER_TIMEOUT_SECONDS)
    return max(timeout_seconds, _LOCAL_OLLAMA_MIN_PLANNER_TIMEOUT_SECONDS)
