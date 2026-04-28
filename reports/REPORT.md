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

**Span emission:** 8 spans, kind `SERVER`, scope `fastmcp`. Span names are identical to FastMCP native (`tools/call echo`, `tools/call calculate`). The Splunk instrumentor does not introduce a separate scope; it extends FastMCP's native telemetry rather than replacing it.

**Attributes** (per span):

```
mcp.method.name, mcp.session.id, rpc.system, rpc.service, rpc.method   # same as FastMCP native
fastmcp.server.name, fastmcp.component.key, fastmcp.component.type,
fastmcp.provider.type                                                 # added by Splunk
```

The four `fastmcp.*` attributes are not in the registry (32 × `missing_attribute`, violation). The five MCP / RPC attributes inherit FastMCP native's profile: required `mcp.method.name` present on 8/8 spans, `mcp.session.id` as the only recommended attribute, deprecated `rpc.system` / `rpc.service`, undefined `rpc.system` enum value `mcp`, type mismatch on `exception.escaped`.

**Metrics:** No metrics in this configuration. The Splunk package does not declare `opentelemetry-sdk` as a hard dependency (we install it explicitly), and the instrumentor does not emit MCP semconv histograms. As with Logfire, OpenTelemetry SDK self-telemetry was also absent in this capture, suggesting the Splunk instrumentor's setup interferes with the MeterProvider configuration in `targets/splunk/server.py`.

---

## 4. Cross-cutting observations

**The MCP `mcp.client.*` and `mcp.server.*` duration / session histograms are not emitted by any of the four implementations.** The semconv's metric layer is unrepresented in this audit's captures. A user wanting MCP-specific RED-style metrics (rate, errors, duration) from any of the four targets does not get them out of the box today. (Each target's collector configures both a traces pipeline and a metrics pipeline with file export, and the file exporter is verified to write both: the Traceloop and FastMCP captures contain OTel SDK self-telemetry metric records, so the receive-and-write path is working. The four named MCP histograms simply never appear in any of the four captures. A literal grep across all four `captures/<target>.json` files for any of the four metric names returns zero matches.)

**Two of the four (Traceloop, Logfire) emit zero MCP semconv attributes on their spans.** Their spans carry information about MCP operations, but in shapes that downstream OTel-aware tooling (which expects `mcp.method.name`, `mcp.session.id`, etc.) won't recognize.

**The two FastMCP-based stacks (FastMCP native, Splunk) carry the same MCP semconv span shape**: kind SERVER, name `{mcp.method.name} {target}`, with `mcp.method.name` and `mcp.session.id` set. Splunk additionally adds four `fastmcp.*`-namespaced attributes that are not in the registry.

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
