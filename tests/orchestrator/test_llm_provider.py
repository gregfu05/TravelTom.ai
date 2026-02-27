"""Tests for orchestrator LLM provider bindings."""

from __future__ import annotations

from typing import Any

import pytest
from app.services.orchestrator.llm_provider import build_orchestrator_llm_models
from app.services.orchestrator.providers import (
    OllamaStructuredClient,
    OpenAIStructuredClient,
)


def _base_provider_kwargs() -> dict[str, Any]:
    return {
        "ollama_base_url": "http://127.0.0.1:11434",
        "ollama_planning_model": "llama3.1:8b",
        "ollama_response_model": "llama3.1:8b",
        "llm_timeout_seconds": 20.0,
        "ollama_temperature": 0.0,
        "openai_base_url": "https://api.openai.com/v1",
        "openai_api_key": "test-key",
        "openai_planning_model": "gpt-4.1-mini",
        "openai_response_model": "gpt-4.1-mini",
        "openai_temperature": 0.0,
    }


def test_build_orchestrator_llm_models_returns_none_for_disabled() -> None:
    bindings = build_orchestrator_llm_models(
        provider="disabled",
        **_base_provider_kwargs(),
    )
    assert bindings.planning_model is None
    assert bindings.response_model is None


def test_build_orchestrator_llm_models_requires_key_for_openai() -> None:
    kwargs = _base_provider_kwargs()
    kwargs["openai_api_key"] = None

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_orchestrator_llm_models(
            provider="openai",
            **kwargs,
        )


def test_ollama_structured_client_parses_json_content() -> None:
    seen_payloads: list[dict[str, Any]] = []

    def transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert url == "http://127.0.0.1:11434/api/chat"
        assert timeout == 15.0
        seen_payloads.append(payload)
        return {
            "message": {
                "content": (
                    '{"intent":"recommend","should_call_recommendation_tool":true,'
                    '"state_patch":{},"query_controls":{}}'
                )
            }
        }

    client = OllamaStructuredClient(
        base_url="http://127.0.0.1:11434",
        planning_model_name="llama3.1:8b",
        response_model_name="llama3.1:8b",
        timeout_seconds=15.0,
        temperature=0.0,
        transport=transport,
    )
    payload = client.plan({"prompt": "test prompt"})

    assert payload["intent"] == "recommend"
    assert len(seen_payloads) == 1
    assert seen_payloads[0]["model"] == "llama3.1:8b"
    assert seen_payloads[0]["stream"] is False
    assert seen_payloads[0]["format"] == "json"


def test_ollama_structured_client_rejects_invalid_content() -> None:
    def transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        del url
        del payload
        del timeout
        return {"message": {"content": "not valid json"}}

    client = OllamaStructuredClient(
        base_url="http://127.0.0.1:11434",
        planning_model_name="llama3.1:8b",
        response_model_name="llama3.1:8b",
        timeout_seconds=15.0,
        temperature=0.0,
        transport=transport,
    )

    with pytest.raises(RuntimeError, match="JSON"):
        client.plan({"prompt": "plan prompt"})


def test_openai_structured_client_parses_json_content() -> None:
    seen_payloads: list[dict[str, Any]] = []

    def transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert url == "https://api.openai.com/v1/chat/completions"
        assert timeout == 12.0
        seen_payloads.append(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"assistant_message":"Grounded response from model."}'
                        )
                    }
                }
            ]
        }

    client = OpenAIStructuredClient(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        planning_model_name="gpt-4.1-mini",
        response_model_name="gpt-4.1-mini",
        timeout_seconds=12.0,
        temperature=0.0,
        transport=transport,
    )
    payload = client.compose({"prompt": "compose prompt"})

    assert payload["assistant_message"] == "Grounded response from model."
    assert len(seen_payloads) == 1
    assert seen_payloads[0]["model"] == "gpt-4.1-mini"
    assert seen_payloads[0]["response_format"] == {"type": "json_object"}


def test_openai_structured_client_rejects_invalid_content() -> None:
    def transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        del url
        del payload
        del timeout
        return {"choices": [{"message": {"content": "not valid json"}}]}

    client = OpenAIStructuredClient(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        planning_model_name="gpt-4.1-mini",
        response_model_name="gpt-4.1-mini",
        timeout_seconds=12.0,
        temperature=0.0,
        transport=transport,
    )

    with pytest.raises(RuntimeError, match="JSON"):
        client.plan({"prompt": "plan prompt"})
