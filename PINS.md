# Pins

Versions used for the audit. Captures and the report are valid for these pins.
Re-running the audit against different pins is a different audit.

## Specification

- **OpenTelemetry semantic-conventions:** `v1.40.0` (released 2026-02-19)
- MCP semconv groups (`stability: development`):
  - `mcp.method.name`, `mcp.session.id`, `mcp.resource.uri`, `mcp.protocol.version`
  - `mcp.client.operation.duration`, `mcp.server.operation.duration`
  - `mcp.client.session.duration`, `mcp.server.session.duration`
  - spans `span.mcp.client`, `span.mcp.server`

## Tooling

- **OTel Weaver:** `0.23.0`
- **OpenTelemetry Collector Contrib:** `0.115.1` (file exporter, OTLP receiver)
- **MCP Python SDK** (the official `mcp` package, used by the scenario client): version recorded at capture time in each `captures/<target>.meta.json`.

## Targets under audit

The four target instrumentations, captured at the versions resolved on the
capture date. Versions are recorded per-capture in `captures/<target>.meta.json`.

| Target | Package | Resolved at preflight (2026-04-28) |
| --- | --- | --- |
| Traceloop | `opentelemetry-instrumentation-mcp` | `0.60.0` |
| FastMCP native | `fastmcp` | `3.2.4` |
| Pydantic Logfire | `logfire` | `4.32.1` |
| Splunk | `splunk-otel-instrumentation-fastmcp` | `0.1.1` |

## Environment

- Python: `3.12.x`
- Capture host: x86_64 Linux (Ubuntu 24.04 in CI / sandbox; macOS arm64 also supported by the Makefile if a darwin Weaver binary is fetched into `.tools/`).

## What is *not* pinned

- The instrumentation versions are intentionally **floated** to whatever PyPI
  resolves on the capture date. The audit is a snapshot of what each
  instrumentation emits today, not a long-term certification.
- Re-running on a different day will resolve newer versions and produce
  different numbers. That is the point.
