"""OpenAI structured JSON client for orchestrator planning/composition."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from app.services.orchestrator.providers.common import (
    JSONTransport,
    parse_structured_json_content,
    post_json,
)


class OpenAIStructuredClient:
    """Call OpenAI chat completions API and parse structured JSON responses."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        planning_model_name: str,
        response_model_name: str,
        timeout_seconds: float,
        temperature: float,
        transport: JSONTransport | None = None,
    ) -> None:
        self._completions_url = urljoin(base_url.rstrip("/") + "/", "chat/completions")
        self._api_key = api_key
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
            raise RuntimeError("OpenAI prompt cannot be empty")

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
            "temperature": self._temperature,
            "response_format": {"type": "json_object"},
        }
        response_payload = self._transport(
            self._completions_url,
            request_payload,
            self._timeout_seconds,
        )
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("OpenAI response missing choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError("OpenAI response choice payload is invalid")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("OpenAI response missing message payload")
        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("OpenAI response missing textual content")
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
            extra_headers={"Authorization": f"Bearer {self._api_key}"},
        )
