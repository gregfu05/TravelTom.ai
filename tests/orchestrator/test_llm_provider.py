"""Tests for LangChain-native chat model construction."""

from __future__ import annotations

from typing import cast

import pytest
from app.core.errors import ApiError
from app.services.orchestrator.llm_provider import (
    DeterministicRecommendationAgentModel,
    DeterministicTravelTomChatModel,
    _resolve_ollama_health_timeout_seconds,
    build_chat_model,
    build_direct_recommendation_model,
    map_provider_exception_to_api_error,
)
from app.services.orchestrator.providers import OllamaStructuredClient
from app.services.travel_tom_agent import _resolve_structured_stage_timeout_seconds
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


def test_build_chat_model_returns_langchain_ollama_model(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_ollama_models(*, base_url: str, timeout_seconds: float) -> list[str]:
        captured["base_url"] = base_url
        captured["timeout_seconds"] = timeout_seconds
        return ["llama3.1:8b-instruct-q4_0"]

    monkeypatch.setattr(
        "app.services.orchestrator.llm_provider.get_ollama_available_model_names",
        fake_get_ollama_models,
    )

    model = build_chat_model(
        provider="ollama",
        ollama_base_url=" http://127.0.0.1:11434 ",
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
    assert model.model == "llama3.1:8b-instruct-q4_0"
    assert captured["base_url"] == "http://127.0.0.1:11434/"
    assert captured["timeout_seconds"] == 5.0


def test_resolve_ollama_health_timeout_seconds_bounds() -> None:
    assert _resolve_ollama_health_timeout_seconds(0.2) == 1.0
    assert _resolve_ollama_health_timeout_seconds(3.0) == 3.0
    assert _resolve_ollama_health_timeout_seconds(20.0) == 5.0


def test_resolve_structured_stage_timeout_seconds_clamps_local_ollama() -> None:
    assert (
        _resolve_structured_stage_timeout_seconds(
            provider_name="ollama",
            stage_name="planner",
            timeout_seconds=20.0,
            local_environment=True,
        )
        == 60.0
    )
    assert (
        _resolve_structured_stage_timeout_seconds(
            provider_name="openai",
            stage_name="planner",
            timeout_seconds=20.0,
            local_environment=True,
        )
        == 20.0
    )
    assert (
        _resolve_structured_stage_timeout_seconds(
            provider_name="ollama",
            stage_name="planner",
            timeout_seconds=50.0,
            local_environment=True,
        )
        == 60.0
    )
    assert (
        _resolve_structured_stage_timeout_seconds(
            provider_name="ollama",
            stage_name="composer",
            timeout_seconds=50.0,
            local_environment=True,
        )
        == 90.0
    )


def test_build_direct_recommendation_model_returns_deterministic_model() -> None:
    model = build_direct_recommendation_model()
    assert isinstance(model, DeterministicRecommendationAgentModel)


def test_ollama_structured_client_uses_configured_timeout_for_planner_requests(
    monkeypatch,
) -> None:
    captured_timeouts: list[float] = []
    captured_request: dict[str, object] = {}

    def transport(
        url: str, payload: dict[str, object], timeout: float
    ) -> dict[str, object]:
        captured_request["url"] = url
        captured_request["payload"] = payload
        captured_timeouts.append(timeout)
        return {
            "message": {
                "content": (
                    '{"intent":"clarify",'
                    '"should_call_recommendation_tool":false,'
                    '"state_patch":{},'
                    '"query_controls":{}}'
                )
            }
        }

    client = OllamaStructuredClient(
        base_url="http://127.0.0.1:11434",
        planning_model_name="llama3.1:8b",
        response_model_name="llama3.1:8b",
        timeout_seconds=20.0,
        temperature=0.0,
        transport=transport,
    )
    monkeypatch.setattr(
        client,
        "_available_model_names",
        lambda: ["llama3.1:8b"],
        raising=False,
    )

    payload = client.plan({"prompt": "hello"})

    assert payload == {
        "intent": "clarify",
        "should_call_recommendation_tool": False,
        "state_patch": {},
        "query_controls": {},
    }
    assert captured_timeouts == [20.0]
    assert str(captured_request["url"]).endswith("/api/chat")
    response_payload = cast(dict[str, object], captured_request["payload"])
    response_format = response_payload.get("format")
    assert isinstance(response_format, dict)
    assert "properties" in response_format


def test_ollama_structured_client_falls_back_when_openai_payload_shape_is_invalid(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def transport(
        url: str, payload: dict[str, object], timeout: float
    ) -> dict[str, object]:
        del payload
        del timeout
        calls.append(url)
        if url.endswith("/api/chat"):
            raise RuntimeError("api chat unavailable")
        if url.endswith("/api/generate"):
            return {
                "response": (
                    '{"intent":"clarify",'
                    '"should_call_recommendation_tool":false,'
                    '"state_patch":{},'
                    '"query_controls":{}}'
                )
            }
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"schema":"2.1","should_call_recommendation_tool":false}'
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
    monkeypatch.setattr(
        client,
        "_available_model_names",
        lambda: ["llama3.1:8b"],
        raising=False,
    )

    payload = client.plan({"prompt": "hello"})

    assert payload["intent"] == "clarify"
    assert payload["should_call_recommendation_tool"] is False
    assert len(calls) == 2
    assert calls[0].endswith("/api/chat")
    assert calls[1].endswith("/api/generate")


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
