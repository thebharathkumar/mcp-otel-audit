# Target: Traceloop `opentelemetry-instrumentation-mcp`

Auto-instruments the official `mcp` Python SDK by monkey-patching at runtime.

## Run standalone

```bash
docker compose up --build
# MCP streamable-HTTP endpoint: http://localhost:18001/mcp/
# Capture appears in: ./capture-out/otlp.json
```

Stop with `docker compose down -v`. The file exporter flushes on graceful shutdown.

## What we wired up

- `McpInstrumentor().instrument()` is called before importing `mcp`.
- OTel SDK is configured with the OTLP/gRPC exporter pointing at the collector.
- Service name: `mcp-traceloop` (resource attribute).

## Pinned

- `opentelemetry-instrumentation-mcp==0.60.0`
- `mcp>=1.0` (whatever PyPI resolves on build day)

The point of this stack is to capture exactly what Traceloop emits today.
We do not modify the instrumentation.
