"""Tests for LangChain-native chat model construction."""

from __future__ import annotations

import pytest
from app.core.errors import ApiError
from app.services.orchestrator.llm_provider import (
    DeterministicRecommendationAgentModel,
    DeterministicTravelTomChatModel,
    build_chat_model,
    build_direct_recommendation_model,
    map_provider_exception_to_api_error,
)
from app.services.orchestrator.providers import OllamaStructuredClient
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI


def test_build_chat_model_returns_deterministic_model_for_disabled_provider() -> None:
    model = build_chat_model(
        provider="disabled",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_chat_model="llama3.1:8b",
        llm_timeout_seconds=20.0,
        ollama_temperature=0.0,
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="test-key",
        openai_chat_model="gpt-4.1-mini",
        openai_temperature=0.0,
        max_results=5,
    )

    assert isinstance(model, DeterministicTravelTomChatModel)


def test_build_chat_model_requires_key_for_openai() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_chat_model(
            provider="openai",
            ollama_base_url="http://127.0.0.1:11434",
            ollama_chat_model="llama3.1:8b",
            llm_timeout_seconds=20.0,
            ollama_temperature=0.0,
            openai_base_url="https://api.openai.com/v1",
            openai_api_key=None,
            openai_chat_model="gpt-4.1-mini",
            openai_temperature=0.0,
            max_results=5,
        )


def test_build_chat_model_returns_langchain_openai_model() -> None:
    model = build_chat_model(
        provider="openai",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_chat_model="llama3.1:8b",
        llm_timeout_seconds=20.0,
        ollama_temperature=0.0,
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="test-key",
        openai_chat_model="gpt-4.1-mini",
        openai_temperature=0.0,
        max_results=5,
    )

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-4.1-mini"


def test_build_chat_model_returns_langchain_ollama_model() -> None:
    model = build_chat_model(
        provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_chat_model="llama3.1:8b",
        llm_timeout_seconds=20.0,
        ollama_temperature=0.0,
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="test-key",
        openai_chat_model="gpt-4.1-mini",
        openai_temperature=0.0,
        max_results=5,
    )

    assert isinstance(model, ChatOllama)
    assert model.model == "llama3.1:8b"


def test_build_direct_recommendation_model_returns_deterministic_model() -> None:
    model = build_direct_recommendation_model()
    assert isinstance(model, DeterministicRecommendationAgentModel)


def test_ollama_structured_client_uses_timeout_floor_for_planner_requests() -> None:
    captured_timeouts: list[float] = []
    captured_request: dict[str, object] = {}

    def transport(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        captured_request["url"] = url
        captured_request["payload"] = payload
        captured_timeouts.append(timeout)
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"intent":"clarify","should_call_recommendation_tool":false}'
                    }
                }
            ]
        }

    client = OllamaStructuredClient(
        base_url="http://127.0.0.1:11434",
        planning_model_name="llama3.1:8b",
        response_model_name="llama3.1:8b",
        timeout_seconds=20.0,
        temperature=0.0,
        transport=transport,
    )
    client._available_model_names = lambda: ["llama3.1:8b"]

    payload = client.plan({"prompt": "hello"})

    assert payload == {
        "intent": "clarify",
        "should_call_recommendation_tool": False,
    }
    assert captured_timeouts == [60.0]
    assert str(captured_request["url"]).endswith("/v1/chat/completions")
    response_format = dict(captured_request["payload"]).get("response_format")
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    assert isinstance(response_format["json_schema"], dict)


class _FakeResponse:
    status_code = 429
    headers = {"Retry-After": "13"}


class _FakeProviderError(Exception):
    def __init__(self) -> None:
        super().__init__("Provider quota exceeded")
        self.response = _FakeResponse()


def test_map_provider_exception_to_api_error_returns_structured_429() -> None:
    error = map_provider_exception_to_api_error(
        _FakeProviderError(),
        provider="openai",
    )

    assert isinstance(error, ApiError)
    assert error.status_code == 429
    assert error.code == "provider_rate_limited"
    assert error.details == {
        "provider": "openai",
        "source": "provider",
        "upstream_error_type": "_FakeProviderError",
        "upstream_status_code": 429,
        "retry_after_seconds": 13,
    }
    assert error.headers == {"Retry-After": "13"}
