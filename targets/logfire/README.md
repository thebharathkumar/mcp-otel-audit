# Target: Pydantic Logfire (`logfire.instrument_mcp`)

Logfire is normally backed by the Pydantic-hosted service. For this audit we
disable that (`send_to_logfire=False`) and add a standard OTLP/gRPC span
processor pointing at the local collector. The instrumentation surface
(`logfire.instrument_mcp()`) is what we are auditing, not the backend.

## Run standalone

```bash
docker compose up --build
# MCP streamable-HTTP endpoint: http://localhost:18003/mcp/
```

## Pinned

- `logfire==4.32.1`
- `mcp>=1.0`
