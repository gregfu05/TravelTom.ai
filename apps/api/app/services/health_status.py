"""Service helpers for health endpoint responses."""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.schemas.api.health import HealthResponse
from app.services.orchestrator.providers.ollama import (
    get_ollama_endpoint_mode,
    normalize_ollama_base_url,
)

logger = logging.getLogger(__name__)


def get_health_response() -> HealthResponse:
    """Return the service health payload with provider context logging."""

    settings = get_settings()
    log_context = {
        "provider": settings.orchestrator_llm_provider,
        "environment": settings.environment,
    }
    if settings.orchestrator_llm_provider == "ollama":
        try:
            normalized_base_url = normalize_ollama_base_url(settings.ollama_base_url)
        except ValueError as exc:
            log_context["ollama_base_url_error"] = str(exc)
        else:
            log_context["ollama_base_url"] = normalized_base_url
            log_context["ollama_endpoint_mode"] = get_ollama_endpoint_mode(
                normalized_base_url
            )
    logger.info("healthcheck_ok", extra={"context": log_context})

    return HealthResponse(status="ok")
