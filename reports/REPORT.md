# MCP OpenTelemetry Instrumentation Audit

**Date of capture:** 2026-04-28 (UTC)
**Specification pin:** OpenTelemetry semantic-conventions [`v1.40.0`](https://github.com/open-telemetry/semantic-conventions/releases/tag/v1.40.0) (released 2026-02-19), MCP groups (`stability: development`).
**Scoring engine:** [OTel Weaver](https://github.com/open-telemetry/weaver) `v0.23.0` (`registry live-check`).
**Client SDK:** `mcp` `1.27.0` (Python).
**Capture host:** Ubuntu 24.04, x86_64, Python 3.12.11.

---

## 1. What this report is

A snapshot of how four MCP OpenTelemetry instrumentations emit telemetry today, scored against the OTel MCP semantic conventions. The same MCP server (three tools: `echo`, `fetch_mock_data`, `calculate`) is exercised by the same six-scenario sequence in each stack. The only thing that varies between captures is the instrumentation under test.

The full reproduction is in this repo. Each capture is committed under `captures/<target>.json` (raw OTLP) and `captures/<target>.weaver.json` (Weaver scoring output).

| Target | Package | Resolved version |
| --- | --- | --- |
| Traceloop | `opentelemetry-instrumentation-mcp` | `0.60.0` |
| FastMCP native | `fastmcp` (built-in `fastmcp.telemetry`) | `3.2.4` |
| Pydantic Logfire | `logfire` (`logfire.instrument_mcp`) | `4.32.1` |
| Splunk | `splunk-otel-instrumentation-fastmcp` | `0.1.1` |

Tool function bodies are byte-identical across stacks (`targets/_shared/tool_funcs.py`). The frameworks differ (the official `mcp` Python SDK underlies Traceloop and Logfire; jlowin's `fastmcp` underlies FastMCP native and Splunk), but the user-observable behavior of the three tools does not.

---

## 2. Headline comparison

For each row, **REQUIRED_PRESENT** is the share of spans that carry the only required MCP attribute (`mcp.method.name`); **RECOMMENDED_PRESENT** is the count of recommended MCP-related attributes observed at least once across all spans, out of 10 listed in the semconv (`mcp.session.id`, `server.address`, `server.port`, `client.address`, `client.port`, `network.transport`, `network.protocol.name`, `network.protocol.version`, `jsonrpc.protocol.version`, `gen_ai.operation.name`); **NAME_MATCH** is whether server-span names follow the semconv format `{mcp.method.name} {target}`; **KIND_MATCH** is whether server spans use `SpanKind.SERVER`; **METRIC_COVERAGE** is the share of the four MCP semconv histograms emitted (`mcp.client.operation.duration`, `mcp.server.operation.duration`, `mcp.client.session.duration`, `mcp.server.session.duration`).

| Implementation | REQUIRED_PRESENT | RECOMMENDED_PRESENT | NAME_MATCH | KIND_MATCH | METRIC_COVERAGE |
| --- | --- | --- | --- | --- | --- |
| Traceloop `0.60.0` | 0/20 (0%) | 0/10 | No | No (INTERNAL) | 0/4 |
| FastMCP native `3.2.4` | 8/8 (100%) | 1/10 (`mcp.session.id`) | Yes | Yes (SERVER) | 0/4 |
| Logfire `4.32.1` | 0/15 (0%) | 0/10 | No | No (INTERNAL) | 0/4 |
| Splunk `0.1.1` | 8/8 (100%) | 1/10 (`mcp.session.id`) | Yes | Yes (SERVER) | 0/4 |

### Severity breakdown (from Weaver `live-check`)

The Weaver scoring engine assigns a severity level (`violation`, `improvement`, `information`) to each finding. Counts shown are total findings across all sampled spans, metrics, and resources in each capture.

| Implementation | violations | improvements | information | total findings |
| --- | --- | --- | --- | --- |
| Traceloop | 40 | 106 | 40 | 186 |
| FastMCP native | 56 | 169 | 8 | 233 |
| Logfire | 120 | 68 | 0 | 188 |
| Splunk | 56 | 40 | 8 | 104 |

A `violation` is something the spec explicitly forbids or contradicts (e.g., a deprecated attribute, a type mismatch, an attribute the spec marks as required but is absent on a span where it must appear). An `improvement` is something the spec recommends but the spec itself is in `development` status. An `information` finding is a non-blocking note (e.g., extending a semconv namespace, undefined enum variant). See `captures/<target>.weaver.json` for the per-finding payload.

A high `improvement` count is partly an artifact of the MCP semconv being in Development: every attribute it defines is `stability: development`, and Weaver flags each occurrence as `not_stable`. This applies uniformly across targets and is mostly noise from a comparison standpoint.

---

## 3. Per-implementation findings

### 3.1 Traceloop `opentelemetry-instrumentation-mcp` 0.60.0

**Span emission:** 20 spans, all named `ResponseStreamWriter`, scope `opentelemetry.instrumentation.mcp.instrumentation`, kind `INTERNAL`. The span name corresponds to an internal class in the `mcp` Python SDK; it does not encode the JSON-RPC method or the target tool. The semconv span name format `{mcp.method.name} {target}` is not produced.

**Attributes:** Two attributes per span: `mcp.request.id` and `mcp.response.value`. Neither is defined in the semconv. Both occupy the `mcp.*` namespace, which Weaver flags 40 times each as `extends_namespace` (information) and `missing_attribute` (violation, "does not exist in the registry"):

```
[violation] ResponseStreamWriter: Attribute 'mcp.response.value' does not exist in the registry.
[violation] ResponseStreamWriter: Attribute 'mcp.request.id' does not exist in the registry.
```

The single attribute the semconv marks as **required** for MCP spans, `mcp.method.name`, is not emitted. None of the recommended attributes (`mcp.session.id`, `server.address`, `gen_ai.operation.name`, etc.) are emitted. (The method name is recoverable by parsing the JSON inside `mcp.response.value`, but it is not surfaced as a structured attribute, so any backend that queries on `mcp.method.name` directly will see nothing.)

**Span kind:** All spans are `INTERNAL`. The semconv specifies `SpanKind.SERVER` for `span.mcp.server` and `SpanKind.CLIENT` for `span.mcp.client`.

**Metrics:** Five metric series are emitted, all OpenTelemetry SDK self-telemetry (`otel.sdk.processor.span.queue.size`, `otel.sdk.span.live`, etc.). None of the four MCP semconv histograms are emitted.

### 3.2 FastMCP native (`fastmcp.telemetry`) 3.2.4

**Span emission:** 8 spans, kind `SERVER`, scope `fastmcp`. Span names are `tools/call echo` and `tools/call calculate`, matching the semconv `{mcp.method.name} {target}` format.

**Attributes** (per span):

```
mcp.method.name      = tools/call         # required by semconv ✓
mcp.session.id       = <session>          # recommended by semconv ✓
rpc.system           = mcp                # deprecated (renamed → rpc.system.name); not in enum
rpc.service          = mcp-audit-fastmcp  # deprecated by RPC semconv
rpc.method           = tools/call         # release_candidate stability
```

The required `mcp.method.name` is present on 8/8 spans. Of the ten MCP-related recommended attributes, only `mcp.session.id` is emitted (1/10).

The `rpc.system` value `mcp` is not part of the documented `rpc.system` enum (Weaver: `Enum attribute 'rpc.system' has value 'mcp' which is not documented.`). The MCP semconv defers to `rpc.system.name` for system identification. `rpc.system` and `rpc.service` are flagged as deprecated.

**Type checking:** The `exception.escaped` attribute is recorded as a string ("False") on 4 spans where the spec types it as boolean.

**Metrics:** Five OpenTelemetry SDK self-telemetry series. None of the four MCP semconv histograms.

### 3.3 Pydantic Logfire (`logfire.instrument_mcp`) 4.32.1

**Span emission:** 15 spans, kind `INTERNAL`, scope `logfire.mcp`. Span names: `MCP server handle request: tools/call` and `MCP server handle request: tools/list`. Descriptive, but not the `{mcp.method.name} {target}` format.

**Attributes:** Eight per span:

```
request, response                # raw payloads (no namespace)
logfire.json_schema, logfire.msg, logfire.msg_template, logfire.span_type
code.filepath, code.lineno       # both deprecated (renamed)
```

None of the eight attributes are MCP semconv attributes. `request` and `response` lack a namespace and trigger 30 × `missing_namespace` (improvement). `code.filepath` (renamed to `code.file.path`) and `code.lineno` (renamed to `code.line.number`) trigger 30 × `deprecated` (violation).

The required `mcp.method.name` is not emitted on any span. None of the recommended attributes are emitted. Like Traceloop, the method name is reachable by parsing the `request` payload (which is a JSON-RPC envelope including `"method": "tools/call"`), but it is not exposed as a structured attribute, so it is invisible to any tooling that queries on `mcp.method.name`.

**Span kind:** `INTERNAL` on all 15 spans.

**Metrics:** No metrics in this configuration. Note: the `logfire.configure()` call in `targets/logfire/server.py` includes `additional_metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())]`, but no metric records (including OpenTelemetry SDK self-telemetry) reached the collector. The `logfire.instrument_mcp` surface is documented as a span-only instrumentation, so the absence of MCP semconv metrics is expected.

### 3.4 Splunk `splunk-otel-instrumentation-fastmcp` 0.1.1

**Span emission:** 8 spans, kind `SERVER`, scope `fastmcp`. Span names are `tools/call echo` and `tools/call calculate`. The captured spans are **structurally identical to FastMCP native**: same scope, same names, same kinds, same attribute keys. A side-by-side fingerprint of `captures/fastmcp.json` and `captures/splunk.json` returns identical sets of `(scope, span name, kind, attribute keys)` tuples.

**Mechanism (verified by reading the package source under `opentelemetry/instrumentation/fastmcp/`):** the package does not emit on its own tracer scope. `FastMCPInstrumentor()._instrument()` registers `wrapt` post-import hooks that wrap `FastMCP.__init__` and `ToolManager.call_tool`, then routes through `opentelemetry.util.genai.handler.TelemetryHandler` (the singleton from `splunk-otel-util-genai`). In this default configuration, no spans from that handler appear in the capture: every span in `captures/splunk.json` has scope `fastmcp` (the FastMCP framework's own tracer name), not `opentelemetry.util.genai.handler` (which is what the genai handler uses). The four `fastmcp.*` attributes (`fastmcp.server.name`, `fastmcp.component.key`, `fastmcp.component.type`, `fastmcp.provider.type`) are emitted by FastMCP itself in `fastmcp/server/telemetry.py`, not by the Splunk instrumentor.

**Attributes** (emitted by FastMCP, present whether or not the Splunk instrumentor is installed):

```
mcp.method.name, mcp.session.id, rpc.system, rpc.service, rpc.method
fastmcp.server.name, fastmcp.component.key, fastmcp.component.type, fastmcp.provider.type
```

The MCP semconv shape is the same as FastMCP native: required `mcp.method.name` on 8/8 spans, `mcp.session.id` as the only recommended attribute, deprecated `rpc.system` / `rpc.service`, undefined `rpc.system` enum value `mcp`, type mismatch on `exception.escaped`. The four `fastmcp.*`-namespaced attributes (32 × `missing_attribute`) are also produced by FastMCP itself, not by Splunk.

**Metrics:** Zero metric records of any kind, including OpenTelemetry SDK self-telemetry. The FastMCP native capture contains 40 SDK self-telemetry data points emitted by the same SDK setup, so the metric pipeline works in the absence of the Splunk instrumentor. The capture does not establish whether the Splunk instrumentor's initialization interferes with the MeterProvider configured in `targets/splunk/server.py`, or whether some other interaction silences the SDK self-telemetry, but the empirical effect is that the Splunk-instrumented capture has no metric records at all.

**Net observation:** in this default configuration, installing `splunk-otel-instrumentation-fastmcp` 0.1.1 on top of FastMCP 3.2.4 does not produce any observable telemetry above what FastMCP itself already emits, and removes the SDK self-telemetry metrics that FastMCP otherwise produces. A different env-var configuration (the package documents `OTEL_INSTRUMENTATION_GENAI_ENABLE` and `OTEL_INSTRUMENTATION_GENAI_EMITTERS`) may activate the genai-handler emission path; this audit captures only the default.

---

## 4. Cross-cutting observations

**The MCP `mcp.client.*` and `mcp.server.*` duration / session histograms are not emitted by any of the four implementations.** The semconv's metric layer is unrepresented in this audit's captures. A user wanting MCP-specific RED-style metrics (rate, errors, duration) from any of the four targets does not get them out of the box today. (Each target's collector configures both a traces pipeline and a metrics pipeline with file export, and the file exporter is verified to write both: the Traceloop and FastMCP captures contain OTel SDK self-telemetry metric records, so the receive-and-write path is working. The four named MCP histograms simply never appear in any of the four captures. A literal grep across all four `captures/<target>.json` files for any of the four metric names returns zero matches.)

**Two of the four (Traceloop, Logfire) emit zero MCP semconv attributes on their spans.** Their spans carry information about MCP operations, but in shapes that downstream OTel-aware tooling (which expects `mcp.method.name`, `mcp.session.id`, etc.) won't recognize.

**The two FastMCP-based stacks (FastMCP native, Splunk) carry an identical span shape**: kind SERVER, name `{mcp.method.name} {target}`, scope `fastmcp`, with the same nine attribute keys including `mcp.method.name`, `mcp.session.id`, deprecated `rpc.*`, and four `fastmcp.*`-namespaced attributes that are not in the registry. All nine attributes are emitted by FastMCP itself; the Splunk instrumentor does not produce any additional observable telemetry on top in default configuration. The Splunk capture differs from the FastMCP capture only in metrics (none vs. 40 SDK self-telemetry records).

**Every capture contains some attributes flagged as deprecated.** `rpc.system` (now `rpc.system.name`) appears in both FastMCP-based stacks, 40 violations total. Logfire emits `code.filepath` / `code.lineno`, 60 violations total. These are renames in OTel semconv, not removals; straightforward to fix in a future release.

**The `exception.escaped` attribute is emitted as a string on `tools/call` spans in both FastMCP-based stacks, where the spec types it as boolean.** This is a single line change in either FastMCP itself or in whatever path records exception status.

---

## 5. Caveats

- **The MCP semconv is in `Development` status.** Attribute names and span shapes will move. A capture that scores poorly today may score well next month, or vice versa. Re-running this audit at a later semconv pin will produce different numbers; that is the design.
- **Captures are point-in-time.** PyPI may resolve different versions of any of these four packages tomorrow. The exact resolved versions for this run are recorded in each `captures/<target>.meta.json`.
- **Scenarios are limited.** Six scenarios exercising three tools cover only `tools/call`, `tools/list`, and `initialize`. The semconv lists ~26 MCP method names; this audit captures behavior on a small subset. Streaming progress notifications and resource / prompt operations are not exercised.
- **The frameworks differ.** Traceloop and Logfire instrument the official `mcp` Python SDK; FastMCP native and Splunk instrument jlowin's `fastmcp`. The two underlying frameworks differ in how they internally name and dispatch spans. A future audit may want to score each framework's emissions separately from the instrumentation layer that wraps them.
- **No instrumentation was modified to score better.** The captures reflect what each package emits with default configuration plus a standard OTLP/gRPC exporter wired up to a local collector. The `targets/<name>/server.py` files document the exact setup used.

---

## 6. Reproducing this report

Requires Docker, [`uv`](https://docs.astral.sh/uv/), and Python 3.12.

```bash
git clone https://github.com/thebharathkumar/mcp-otel-audit
cd mcp-otel-audit

./scripts/bootstrap.sh     # fetches the Weaver binary into .tools/
make capture-all           # builds 4 stacks, runs scenarios, writes raw OTLP to captures/
make score-all             # runs Weaver live-check on each capture
```

The raw captures and Weaver outputs in this repo are the ones this report is built from. To produce a different snapshot, delete `captures/*.json captures/*.weaver.json` and re-run `make`.

To pin to a different semconv version, change the `SEMCONV_REGISTRY` line in the `Makefile` and the URL in `scripts/score.sh`. See `PINS.md` for the full pin set used here.

---

## 7. Findings index

For each target, the per-finding output is in `captures/<target>.weaver.json`. The fields under each `samples[*].all_advice[]` array describe individual findings with `id`, `level`, `message`, `signal_name`, and `context`. Useful queries:

```bash
# every violation across all targets
jq -r '.. | objects | select(.level == "violation") | "\(.signal_name)\t\(.id)\t\(.message)"' \
  captures/*.weaver.json | sort -u

# missing-attribute findings only
jq -r '.. | objects | select(.id == "missing_attribute") | .message' \
  captures/<target>.weaver.json | sort -u
```

---

## 8. Postscript: maintainer feedback (2026-04-28)

Posted in the OpenTelemetry community Slack on the day this audit was published. Marcelo Trylesinski, who maintains Pydantic Logfire and is also a maintainer of the official `mcp` Python SDK, offered two pieces of context that adjust the framing of this snapshot:

1. **Logfire's MCP instrumentation predates the OTel MCP semantic conventions.** The Logfire telemetry shape captured in `captures/logfire.json` was designed and shipped before the spec existed. The divergence from semconv `v1.40.0` is historical, not a refusal to track the spec, and the per-implementation finding in section 3.3 should be read with that in mind.

2. **`mcp` v2 will ship native OpenTelemetry support.** The official `mcp` Python SDK is merging native OTel emission, and the four packages audited here are expected to become obsolete once v2 ships. This audit therefore documents a snapshot of a transition state rather than a steady state. A follow-up snapshot against `mcp` v2 should produce materially different numbers; the harness in this repo is set up to be re-run on demand.

The findings in sections 2-5 still describe what each package emits today, which is what a user installing one of them right now will observe. The methodology, captures, and Weaver scoring are unchanged.
