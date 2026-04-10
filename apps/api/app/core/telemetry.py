"""Telemetry bootstrap and tracing helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

from fastapi import FastAPI

from app.core.config import Settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from opentelemetry.trace import Span

try:
    from opentelemetry import trace as _imported_trace
    from opentelemetry.instrumentation.fastapi import (
        FastAPIInstrumentor as _imported_fastapi_instrumentor,
    )
    from opentelemetry.instrumentation.logging import (
        LoggingInstrumentor as _imported_logging_instrumentor,
    )
except ImportError:  # pragma: no cover - optional until dependency install
    _trace_api: Any | None = None
    _fastapi_instrumentor: type[Any] | None = None
    _logging_instrumentor: type[Any] | None = None
else:
    _trace_api = _imported_trace
    _fastapi_instrumentor = _imported_fastapi_instrumentor
    _logging_instrumentor = _imported_logging_instrumentor

try:
    from azure.monitor.opentelemetry import (
        configure_azure_monitor as _imported_configure_azure_monitor,
    )
except ImportError:  # pragma: no cover - optional until dependency install
    _configure_azure_monitor: Callable[..., None] | None = None
else:
    _configure_azure_monitor = _imported_configure_azure_monitor


def configure_telemetry(application: FastAPI, settings: Settings) -> None:
    """Install OpenTelemetry exporters and framework instrumentation."""

    connection_string = (settings.applicationinsights_connection_string or "").strip()
    if (
        not connection_string
        or _configure_azure_monitor is None
        or _fastapi_instrumentor is None
        or _logging_instrumentor is None
    ):
        return

    _configure_azure_monitor(
        connection_string=connection_string,
        logger_name=settings.telemetry_service_name,
    )
    _logging_instrumentor().instrument(set_logging_format=False)
    _fastapi_instrumentor.instrument_app(application)


def get_tracer(name: str | None = None):
    """Return the shared tracer."""

    if _trace_api is None:
        return None
    return _trace_api.get_tracer(name or "traveltom")


@contextmanager
def start_span(name: str, **attributes: object) -> Iterator[Span | None]:
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
