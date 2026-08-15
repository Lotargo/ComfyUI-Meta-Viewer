from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_tracing_ready = False


def setup_tracing(service_name: str = "comfy-meta-viewer", level: str = "INFO") -> None:
    global _tracing_ready
    if _tracing_ready:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON
    except ImportError:
        logger.debug("opentelemetry not installed; tracing disabled")
        return

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource, sampler=ALWAYS_ON)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor

        FlaskInstrumentor().instrument()
    except ImportError:
        logger.debug("flask instrumentation not installed")

    _tracing_ready = True
    logger.info("opentelemetry tracing enabled -> stdout (console exporter)")


def get_tracer(name: str = __name__):
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return _NoOpTracer()


class _NoOpTracer:
    def start_as_current_span(self, *args, **kwargs):
        import contextlib

        return contextlib.nullcontext()

    def start_span(self, *args, **kwargs):
        return None
