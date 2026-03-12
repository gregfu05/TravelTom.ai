"""Tests for LangChain-native chat model construction."""

from __future__ import annotations

import pytest
from app.services.orchestrator.llm_provider import (
    DeterministicRecommendationAgentModel,
    DeterministicTravelTomChatModel,
    build_chat_model,
    build_direct_recommendation_model,
)
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
