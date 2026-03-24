"""Ollama structured JSON client for orchestrator planning/composition."""

from __future__ import annotations

from typing import Any, Sequence
from urllib.parse import urljoin

from app.schemas.orchestrator import LLMComposedResponse, LLMOrchestrationPlan
from app.services.orchestrator.providers.common import (
    JSONTransport,
    StructuredModelTransportError,
    get_json,
    parse_structured_json_content,
    post_json,
)


def match_ollama_model_name(
    configured_model_name: str,
    available_model_names: Sequence[str],
) -> str | None:
    """Return the best installed model match for a configured Ollama model name."""

    normalized_configured = configured_model_name.strip()
    if not normalized_configured:
        return configured_model_name

    available_names = [name.strip() for name in available_model_names if name.strip()]
    if normalized_configured in available_names:
        return normalized_configured

    prefix_matches = [
        candidate
        for candidate in available_names
        if candidate.startswith(normalized_configured)
    ]
    if prefix_matches:
        return prefix_matches[0]

    contains_matches = [
        candidate for candidate in available_names if normalized_configured in candidate
    ]
    if contains_matches:
        return contains_matches[0]

    return None


def get_ollama_available_model_names(
    *,
    base_url: str,
    timeout_seconds: float,
) -> list[str]:
    """Return installed Ollama model names from the most compatible endpoint."""

    normalized_base_url = base_url.rstrip("/") + "/"
    models_url = urljoin(normalized_base_url, "v1/models")
    tags_url = urljoin(normalized_base_url, "api/tags")

    try:
        models_payload = get_json(
            url=models_url,
            timeout_seconds=timeout_seconds,
        )
    except StructuredModelTransportError as exc:
        if exc.status_code != 404:
            raise
    else:
        data = models_payload.get("data")
        if isinstance(data, list):
            names = [
                str(item.get("id"))
                for item in data
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]
            if names:
                return names

    tags_payload = get_json(
        url=tags_url,
        timeout_seconds=timeout_seconds,
    )
    models = tags_payload.get("models")
    if not isinstance(models, list):
        return []
    return [
        str(item.get("name"))
        for item in models
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]


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
        normalized_base_url = base_url.rstrip("/") + "/"
        self._base_url = normalized_base_url
        self._chat_url = urljoin(normalized_base_url, "api/chat")
        self._openai_chat_url = urljoin(normalized_base_url, "v1/chat/completions")
        self._generate_url = urljoin(normalized_base_url, "api/generate")
        self._models_url = urljoin(normalized_base_url, "v1/models")
        self._tags_url = urljoin(normalized_base_url, "api/tags")
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
            schema=LLMOrchestrationPlan.model_json_schema(),
        )

    def compose(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate a structured assistant response payload."""

        return self._invoke_structured(
            model_name=self._response_model_name,
            prompt=str(payload.get("prompt", "")),
            schema=LLMComposedResponse.model_json_schema(),
        )

    def _invoke_structured(
        self,
        *,
        model_name: str,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        if not prompt.strip():
            raise RuntimeError("Ollama prompt cannot be empty")
        resolved_model_name = self._resolve_model_name(model_name)
        attempts = [
            lambda: self._invoke_openai_chat_completions(
                resolved_model_name,
                prompt,
                schema,
            ),
            lambda: self._invoke_api_chat(resolved_model_name, prompt, schema),
            lambda: self._invoke_generate(resolved_model_name, prompt, schema),
        ]
        last_error: Exception | None = None
        for attempt in attempts:
            try:
                return attempt()
            except StructuredModelTransportError as exc:
                last_error = exc
                if exc.status_code == 404:
                    continue
                raise
            except RuntimeError as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        raise RuntimeError("Ollama structured invocation failed")

    def _invoke_api_chat(
        self,
        model_name: str,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
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
            "format": schema,
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

    def _invoke_openai_chat_completions(
        self,
        model_name: str,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        response_payload = self._transport(
            self._openai_chat_url,
            {
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
                "response_format": {
                    "type": "json_schema",
                    "json_schema": schema,
                },
            },
            self._timeout_seconds,
        )
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Ollama OpenAI-compatible response missing choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError("Ollama OpenAI-compatible choice payload is invalid")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama OpenAI-compatible response missing message")
        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("Ollama OpenAI-compatible content is invalid")
        return parse_structured_json_content(content)

    def _invoke_generate(
        self,
        model_name: str,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        response_payload = self._transport(
            self._generate_url,
            {
                "model": model_name,
                "prompt": (
                    "Return only valid JSON matching the requested schema. "
                    "Do not include markdown.\n\n" + prompt
                ),
                "stream": False,
                "format": schema,
                "options": {"temperature": self._temperature},
            },
            self._timeout_seconds,
        )
        content = response_payload.get("response")
        if not isinstance(content, str):
            raise RuntimeError("Ollama generate response missing textual content")
        return parse_structured_json_content(content)

    def _resolve_model_name(self, configured_model_name: str) -> str:
        available_model_names = self._available_model_names()
        if not available_model_names:
            return configured_model_name

        matched_model_name = match_ollama_model_name(
            configured_model_name,
            available_model_names,
        )
        if matched_model_name is None:
            available_models = ", ".join(sorted(available_model_names))
            raise RuntimeError(
                "Configured Ollama model "
                f"'{configured_model_name}' was not found. Available models: "
                f"{available_models}"
            )
        return matched_model_name

    def _available_model_names(self) -> list[str]:
        return get_ollama_available_model_names(
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
        )

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
