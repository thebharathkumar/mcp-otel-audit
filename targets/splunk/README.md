# Target: Splunk `splunk-otel-instrumentation-fastmcp`

`FastMCPInstrumentor().instrument()` patches the `fastmcp` (jlowin) library
at runtime. The package does not declare `opentelemetry-sdk` as a hard
dependency, so we install it explicitly in `requirements.txt` to make the
SDK available.

## Run standalone

```bash
docker compose up --build
# MCP streamable-HTTP endpoint: http://localhost:18004/mcp/
```

## Pinned

- `splunk-otel-instrumentation-fastmcp==0.1.1`
- `fastmcp==3.2.4`
