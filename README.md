# mcp-otel-audit

Public audit of MCP OpenTelemetry instrumentations against the official OTel
semantic conventions for MCP (`semantic-conventions@v1.40.0`).

The artifact is the report:

- **[`reports/REPORT.md`](reports/REPORT.md)**: comparison of four MCP instrumentations.
- **[`docs/blog/auditing-mcp-otel.md`](docs/blog/auditing-mcp-otel.md)**: narrative writeup.

Everything else in this repo exists to make those two documents reproducible.

## What this is

Four MCP server stacks, each running the same three tools (`echo`,
`fetch_mock_data`, `calculate`), each instrumented by a different OTel package:

| Target | Package |
| --- | --- |
| Traceloop | `opentelemetry-instrumentation-mcp` |
| FastMCP native | `fastmcp` (built-in `fastmcp.telemetry`) |
| Pydantic Logfire | `logfire` |
| Splunk | `splunk-otel-instrumentation-fastmcp` |

Each stack pipes OTLP into an OTel Collector with the file exporter, which
dumps raw OTLP JSON into `captures/<target>.json`. We score those captures
with `weaver registry live-check` against
`open-telemetry/semantic-conventions@v1.40.0`. See **[`PINS.md`](PINS.md)**
for the full version pin set.

OTel Weaver is the scoring engine. We do not reimplement it.

## Reproducing

Requires Docker, [`uv`](https://docs.astral.sh/uv/), and Python 3.12.

```bash
# One-time setup: download the Weaver binary into .tools/
./scripts/bootstrap.sh

# Run all four stacks, capture OTLP, score with Weaver
make capture-all
make score-all

# Inspect captures/<target>.weaver.json to write the report
make report-summary
```

Each target lives under `targets/<name>/` with its own `docker-compose.yml`
and `README.md` for running it standalone.

## Layout

```
.
├── PINS.md                          # version pins
├── reports/REPORT.md                # the audit report
├── docs/blog/auditing-mcp-otel.md   # the writeup
├── scripts/
│   ├── scenarios.py                 # exercises the six scenarios
│   ├── bootstrap.sh                 # fetches Weaver binary
│   ├── capture.sh                   # docker-up + scenarios + capture
│   ├── score.sh                     # weaver live-check on captures
│   └── report_summary.py            # tabulates Weaver output
├── targets/
│   ├── _shared/tool_funcs.py        # tool bodies, identical across stacks
│   ├── traceloop/
│   ├── fastmcp/
│   ├── logfire/
│   └── splunk/
├── captures/                        # raw OTLP + Weaver score JSON, committed
└── .tools/                          # Weaver binary (gitignored)
```

## Status

Built 2026-04-28. The MCP semconv is in Development status; instrumentations
emit against moving snapshots of the spec; this report is a point-in-time
audit, not a certification.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
