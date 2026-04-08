"""Tests for Ollama provider URL helpers."""

from __future__ import annotations

import pytest
from app.services.orchestrator.providers.ollama import (
    get_ollama_endpoint_mode,
    normalize_ollama_base_url,
)


def test_normalize_ollama_base_url_trims_and_adds_trailing_slash() -> None:
    normalized = normalize_ollama_base_url(" http://127.0.0.1:11434/// ")
    assert normalized == "http://127.0.0.1:11434/"


def test_normalize_ollama_base_url_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="OLLAMA_BASE_URL"):
        normalize_ollama_base_url("   ")


def test_get_ollama_endpoint_mode_marks_loopback_as_local() -> None:
    assert get_ollama_endpoint_mode("http://localhost:11434") == "local"
    assert get_ollama_endpoint_mode("http://127.0.0.1:11434") == "local"


def test_get_ollama_endpoint_mode_marks_non_loopback_as_remote() -> None:
    assert get_ollama_endpoint_mode("https://ollama.example.com") == "remote"
