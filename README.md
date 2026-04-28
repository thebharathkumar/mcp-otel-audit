# mcp-otel-audit

> Public audit of MCP OpenTelemetry instrumentations against the official OTel
> semantic conventions for MCP.

**Status: Phase 0 (pre-flight) — partial.** STOP gate 1 (Weaver scores MCP semconv) is
cleared. STOP gate 2 (four targets installable) is blocked on local disk space, not on
packaging. No code or report yet — the work that produces those starts in Phase 1.

The plan in one paragraph: build a small reproducible scenario harness that exercises
four MCP server implementations — Traceloop's `opentelemetry-instrumentation-mcp`,
FastMCP's native instrumentation, Pydantic Logfire, and Splunk's
`splunk-otel-instrumentation-fastmcp` — each running the **same three tools**. Capture
raw OTLP from each. Score the captures against OpenTelemetry semantic-conventions
**v1.40.0** using OTel Weaver's `live-check`. Publish a neutral comparison report.

OTel Weaver is the scoring engine. We don't reimplement it.

## Where to start

1. **`MISSING_NICHE.md`** — three rounds of niche analysis (`mcp-eval`, `mcp-otel`,
   `mcp-conformance`) and why this scope was the one to ship.
2. **`PHASE0.md`** — current pre-flight state, evidence, blockers.
3. **`RESUME_PROMPT.md`** — self-contained prompt to resume this build in a fresh
   Claude Code session.

## Pin

- OpenTelemetry semantic-conventions **`v1.40.0`** (released 2026-02-19).
- OTel Weaver **`v0.23.0`**.
- MCP Python SDK version will be recorded at capture time.

## License

Not yet licensed. Apache-2.0 will be added with the Phase 1 skeleton.
