"""Shared HTTP and JSON helpers for structured LLM clients."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

JSONTransport = Callable[[str, dict[str, Any], float], dict[str, Any]]


def post_json(
    *,
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """POST JSON and parse object response."""

    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)

    request = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("Failed to reach structured model endpoint") from exc

    try:
        parsed_payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Structured model response was not valid JSON") from exc
    if not isinstance(parsed_payload, dict):
        raise RuntimeError("Structured model response root must be a JSON object")
    return parsed_payload


def parse_structured_json_content(content: str) -> dict[str, Any]:
    """Parse model text content expected to contain a JSON object."""

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        payload = _extract_first_json_object(content)

    if not isinstance(payload, dict):
        raise RuntimeError("Structured model output must be a JSON object")
    return payload


def _extract_first_json_object(content: str) -> dict[str, Any]:
    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace < 0 or last_brace <= first_brace:
        raise RuntimeError("Model output did not contain JSON object content")

    snippet = content[first_brace : last_brace + 1]
    try:
        parsed_payload = json.loads(snippet)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Model output JSON content was invalid") from exc
    if not isinstance(parsed_payload, dict):
        raise RuntimeError("Extracted model output was not a JSON object")
    return parsed_payload
