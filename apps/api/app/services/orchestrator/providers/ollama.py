"""Ollama structured JSON client for orchestrator planning/composition."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from app.services.orchestrator.providers.common import (
    JSONTransport,
    parse_structured_json_content,
    post_json,
)


class OllamaStructuredClient:
    """Call Ollama chat API and parse structured JSON responses."""

    def __init__(
        self,
        *,
        base_url: str,
        planning_model_name: str,
        response_model_name: str,
        timeout_seconds: float,
        temperature: float,
        transport: JSONTransport | None = None,
    ) -> None:
        self._chat_url = urljoin(base_url.rstrip("/") + "/", "api/chat")
        self._planning_model_name = planning_model_name
        self._response_model_name = response_model_name
        self._timeout_seconds = timeout_seconds
        self._temperature = temperature
        self._transport = transport or self._default_transport

    def plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate a structured orchestration plan payload."""

        return self._invoke_structured(
            model_name=self._planning_model_name,
            prompt=str(payload.get("prompt", "")),
        )

    def compose(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate a structured assistant response payload."""

        return self._invoke_structured(
            model_name=self._response_model_name,
            prompt=str(payload.get("prompt", "")),
        )

    def _invoke_structured(
        self,
        *,
        model_name: str,
        prompt: str,
    ) -> dict[str, Any]:
        if not prompt.strip():
            raise RuntimeError("Ollama prompt cannot be empty")
        request_payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only valid JSON matching the requested schema. "
                        "Do not include markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": self._temperature},
        }
        response_payload = self._transport(
            self._chat_url,
            request_payload,
            self._timeout_seconds,
        )
        message = response_payload.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama response missing message payload")
        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("Ollama response missing textual content")
        return parse_structured_json_content(content)

    def _default_transport(
        self,
        url: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        return post_json(
            url=url,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )
