"""Telemetry bootstrap and tracing helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from fastapi import FastAPI
from app.core.config import Settings

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.trace import Span
except ImportError:  # pragma: no cover - optional until dependency install
    trace = None
    FastAPIInstrumentor = None
    LoggingInstrumentor = None
    Span = Any

try:
    from azure.monitor.opentelemetry import configure_azure_monitor
except ImportError:  # pragma: no cover - optional until dependency install
    configure_azure_monitor = None


def configure_telemetry(application: FastAPI, settings: Settings) -> None:
    """Install OpenTelemetry exporters and framework instrumentation."""

    connection_string = (
        settings.applicationinsights_connection_string or ""
    ).strip()
    if (
        not connection_string
        or configure_azure_monitor is None
        or FastAPIInstrumentor is None
        or LoggingInstrumentor is None
    ):
        return

    configure_azure_monitor(
        connection_string=connection_string,
        logger_name=settings.telemetry_service_name,
    )
    LoggingInstrumentor().instrument(set_logging_format=False)
    FastAPIInstrumentor.instrument_app(application)


def get_tracer(name: str | None = None):
    """Return the shared tracer."""

    if trace is None:
        return None
    return trace.get_tracer(name or "traveltom")


@contextmanager
def start_span(name: str, **attributes: object) -> Iterator[Span]:
    """Create a span around an application-level operation."""

    tracer = get_tracer()
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is None:
                continue
            span.set_attribute(key, value)
        yield span
