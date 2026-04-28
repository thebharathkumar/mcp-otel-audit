# Target: FastMCP native (`fastmcp.telemetry`)

FastMCP emits OpenTelemetry spans through its built-in `fastmcp.telemetry`
helpers. There is no separate instrumentor package. As long as a tracer
provider is configured before the server starts, FastMCP's internal calls
to `get_tracer()` will produce real spans.

## Run standalone

```bash
docker compose up --build
# MCP streamable-HTTP endpoint: http://localhost:18002/mcp/
```

## Pinned

- `fastmcp==3.2.4`
