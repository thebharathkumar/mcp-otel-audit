"""MCP server instrumented with Pydantic Logfire's `logfire.instrument_mcp`.

Logfire is normally backed by the Pydantic-hosted service. We disable that
(`send_to_logfire=False`) and route through the standard OTel SDK to our
local collector instead, which is what `instrument_mcp` writes spans to.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/app/_shared")
from tool_funcs import calculate as _calc, echo as _echo, fetch_mock_data as _fetch

from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace.export import BatchSpanProcessor

import logfire

logfire.configure(
    service_name=os.environ.get("OTEL_SERVICE_NAME", "mcp-logfire"),
    send_to_logfire=False,
    console=False,
    additional_span_processors=[BatchSpanProcessor(OTLPSpanExporter())],
    additional_metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=1000)],
)
logfire.instrument_mcp()

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mcp-audit-logfire", host="0.0.0.0", port=8000)


@mcp.tool()
def echo(text: str) -> str:
    return _echo(text)


@mcp.tool()
def fetch_mock_data(key: str) -> str:
    return _fetch(key)


@mcp.tool()
def calculate(op: str, a: float, b: float) -> float:
    return _calc(op, a, b)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
