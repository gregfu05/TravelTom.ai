"""LLM provider bindings for orchestrator planning and response composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from app.services.orchestrator.providers import (
    OllamaStructuredClient,
    OpenAIStructuredClient,
)

StructuredModel = Callable[[dict[str, Any]], dict[str, Any]]
ProviderName = Literal["disabled", "ollama", "openai"]


@dataclass(frozen=True)
class OrchestratorLLMModels:
    """Container for orchestrator structured model callables."""

    planning_model: StructuredModel | None
    response_model: StructuredModel | None


def build_orchestrator_llm_models(
    *,
    provider: ProviderName,
    ollama_base_url: str,
    ollama_planning_model: str,
    ollama_response_model: str,
    llm_timeout_seconds: float,
    ollama_temperature: float,
    openai_base_url: str,
    openai_api_key: str | None,
    openai_planning_model: str,
    openai_response_model: str,
    openai_temperature: float,
) -> OrchestratorLLMModels:
    """Create planner/composer callables for the configured provider."""

    if provider == "disabled":
        return OrchestratorLLMModels(
            planning_model=None,
            response_model=None,
        )

    if provider == "ollama":
        ollama_client = OllamaStructuredClient(
            base_url=ollama_base_url,
            planning_model_name=ollama_planning_model,
            response_model_name=ollama_response_model,
            timeout_seconds=llm_timeout_seconds,
            temperature=ollama_temperature,
        )
        return OrchestratorLLMModels(
            planning_model=ollama_client.plan,
            response_model=ollama_client.compose,
        )

    if provider == "openai":
        api_key = (openai_api_key or "").strip()
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY (or ORCHESTRATOR_OPENAI_API_KEY) is required "
                "when ORCHESTRATOR_LLM_PROVIDER=openai"
            )

        openai_client = OpenAIStructuredClient(
            base_url=openai_base_url,
            api_key=api_key,
            planning_model_name=openai_planning_model,
            response_model_name=openai_response_model,
            timeout_seconds=llm_timeout_seconds,
            temperature=openai_temperature,
        )
        return OrchestratorLLMModels(
            planning_model=openai_client.plan,
            response_model=openai_client.compose,
        )

    raise ValueError(f"Unsupported orchestrator LLM provider: {provider}")
