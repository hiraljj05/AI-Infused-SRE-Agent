from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing(*, endpoint: str | None, service_name: str, attrs: str) -> None:
    resource_attrs: dict[str, str] = {"service.name": service_name}
    for kv in attrs.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            resource_attrs[k.strip()] = v.strip()
    provider = TracerProvider(resource=Resource.create(resource_attrs))
    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def tracer(name: str = "sre_agent") -> trace.Tracer:
    return trace.get_tracer(name)
