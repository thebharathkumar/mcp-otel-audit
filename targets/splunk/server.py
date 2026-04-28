"""MCP server instrumented with splunk-otel-instrumentation-fastmcp.

The package ships `opentelemetry.instrumentation.fastmcp.FastMCPInstrumentor`,
which patches the `fastmcp` (jlowin) library at runtime. The package does not
declare `opentelemetry-sdk` as a hard dep so we install it explicitly.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/app/_shared")
from tool_funcs import calculate as _calc, echo as _echo, fetch_mock_data as _fetch

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

resource = Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "mcp-splunk")})

trace_provider = TracerProvider(resource=resource)
trace_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(trace_provider)

metrics.set_meter_provider(
    MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=1000)],
    )
)

from opentelemetry.instrumentation.fastmcp import FastMCPInstrumentor

FastMCPInstrumentor().instrument()

from fastmcp import FastMCP

mcp = FastMCP("mcp-audit-splunk")


@mcp.tool
def echo(text: str) -> str:
    return _echo(text)


@mcp.tool
def fetch_mock_data(key: str) -> str:
    return _fetch(key)


@mcp.tool
def calculate(op: str, a: float, b: float) -> float:
    return _calc(op, a, b)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp/")
