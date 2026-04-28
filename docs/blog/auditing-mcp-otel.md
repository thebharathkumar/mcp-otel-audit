# Auditing MCP OpenTelemetry instrumentations

*Draft. Posting is manual.*

If you instrument an MCP server today, you have four reasonable options. Pick any one and you get OpenTelemetry traces. Pick a different one and you get traces too. The traces will look almost nothing alike.

That's the headline finding from a small audit I ran this week. Same MCP server, same three tools, same client scenario sequence, four different OpenTelemetry instrumentations. The shape of the telemetry varies enormously. Span names, span kinds, attribute namespaces, attribute presence, metric coverage. Most of the divergence sits below what a typical user notices until the day they swap one instrumentation for another and watch their dashboards go quiet.

This post is the writeup. The data and the reproducible harness are at [github.com/thebharathkumar/mcp-otel-audit](https://github.com/thebharathkumar/mcp-otel-audit).

## Why this matters now

The Model Context Protocol added official OpenTelemetry semantic conventions in early 2026. As of the v1.40.0 semconv release on 2026-02-19, the MCP groups define one required attribute (`mcp.method.name`), a list of recommended attributes (`mcp.session.id`, `gen_ai.operation.name`, the standard `network.*` and `server.*` fields), and four histogram metrics (operation duration and session duration on each side of the wire). The spec itself is in Development status, so the names and shapes are not frozen, but the core schema is published and instrumentation packages claim to emit against it.

Four packages currently do, or claim to:

* `opentelemetry-instrumentation-mcp` from Traceloop
* `fastmcp`'s built-in `fastmcp.telemetry`
* `logfire.instrument_mcp` from Pydantic
* `splunk-otel-instrumentation-fastmcp` from Splunk

These four cover most of the Python instrumentation surface that an MCP server author would reach for today. There may be others I missed; if so, point me at them and I'll add a column.

The question is the boring one: do they emit what the spec says? Until you check, you can't really plan around the data. Dashboards, alerts, sampling rules, error budgets. They all need a stable schema underneath. The point of this audit is to look.

## How the audit works

The repo has a small docker-compose stack per implementation. Each stack runs the same MCP server with the same three tools (`echo`, `fetch_mock_data`, `calculate`). The tool function bodies are byte-identical across all four stacks (`targets/_shared/tool_funcs.py`). The only thing that differs is the framework and the instrumentation layer.

Each stack pipes OTLP/gRPC into an OpenTelemetry Collector with the file exporter, which dumps the raw OTLP messages to `captures/<target>.json`. A six-scenario client script (the official `mcp` Python SDK 1.27.0) drives each server: a successful tool call, a deliberate division-by-zero error, a malformed-args call, a session lifecycle (initialize, list tools, close), five concurrent calls in parallel, and a streaming-response check that records "not exercised" because the audit's three tools don't issue progress notifications.

After capture, the raw OTLP file is replayed through OTel Weaver's `registry live-check` listener, scored against `semantic-conventions@v1.40.0`, and the score JSON is written next to the capture. Weaver does the actual conformance scoring. I didn't reimplement any of it.

That last point matters more than it sounds. The first version of this project had a "build a Python conformance scorer" phase. Halfway through, it became obvious that Weaver already does this, that it ships as a Rust binary the OTel project supports, and that a Python reimplementation would be a parallel less-mature copy of someone else's work. So the project shrank to glue: a scenario script, a docker-compose stack, a replay tool. The actual scoring is an off-the-shelf invocation. There was nothing missing in the toolchain. There was a missing audit.

## What the captures show

Numbers first. The five-column comparison from the report:

| Implementation | REQUIRED_PRESENT | RECOMMENDED_PRESENT | NAME_MATCH | KIND_MATCH | METRIC_COVERAGE |
| --- | --- | --- | --- | --- | --- |
| Traceloop 0.60.0 | 0/20 | 0/10 | No | No | 0/4 |
| FastMCP native 3.2.4 | 8/8 | 1/10 | Yes | Yes | 0/4 |
| Logfire 4.32.1 | 0/15 | 0/10 | No | No | 0/4 |
| Splunk 0.1.1 | 8/8 | 1/10 | Yes | Yes | 0/4 |

These specific numbers are a snapshot. The MCP semconv is in Development status and is still moving, the four packages release on their own cadences, and re-running the audit a month from now will produce different cells. The point of committing the raw OTLP captures and the harness to the repo is so anyone can re-score against a newer semconv pin or re-capture against newer package versions and see what changed.

REQUIRED_PRESENT is the share of spans that carry `mcp.method.name`, the only attribute the MCP semconv currently marks as required. Two of the four implementations don't emit it. RECOMMENDED_PRESENT counts the recommended MCP-related attributes observed across each capture; only `mcp.session.id` shows up, and only on the two FastMCP-based stacks. NAME_MATCH is whether server-side spans use the documented `{mcp.method.name} {target}` naming convention. KIND_MATCH is whether they use `SpanKind.SERVER`. METRIC_COVERAGE is the fraction of the four MCP semconv histograms emitted.

That last column is uniform: none of the four emit any of them. Not the operation-duration histograms, not the session-duration histograms. If you want MCP-specific RED metrics from any of these four packages today, you don't get them out of the box.

A second uniformity: every capture contains some attributes that are deprecated in the current semconv. The two FastMCP stacks emit `rpc.system="mcp"` (Weaver flags this 40 times: deprecated, renamed to `rpc.system.name`, and the value `mcp` is not in the documented enum). Logfire emits `code.filepath` and `code.lineno`, both renamed to dotted forms (`code.file.path`, `code.line.number`). These are easy fixes. They're also a fair index of how recently each instrumentation has tracked the moving spec.

Now the per-implementation breakdown.

**Traceloop.** Twenty spans, all named `ResponseStreamWriter`. That string is an internal class name in the official `mcp` Python SDK, not a JSON-RPC method, not a tool name. Each span carries two attributes: `mcp.request.id` and `mcp.response.value`. Neither is in the MCP semconv. They occupy the `mcp.*` namespace, so Weaver flags them: 40 times as `extends_namespace` (a non-blocking note) and 40 times as `missing_attribute` (a violation, "does not exist in the registry"). The spans are kind INTERNAL where the semconv specifies SERVER. The required `mcp.method.name` is absent.

**FastMCP native.** Eight spans named `tools/call echo` and `tools/call calculate`. SERVER kind. The MCP semconv shape is broadly there: `mcp.method.name`, `mcp.session.id`, plus a set of `rpc.*` attributes. The `rpc.system` value is `mcp`, which the documented enum doesn't include. The `exception.escaped` attribute on the four error-path spans is a string ("False") where the spec types it as boolean. Of the ten recommended MCP attributes, only `mcp.session.id` appears.

**Logfire.** Fifteen spans named like `MCP server handle request: tools/call`. Descriptive, not the semconv format. Span kind INTERNAL. Attributes are Logfire-flavored: `request`, `response`, `logfire.msg`, `logfire.json_schema`, `code.filepath`, `code.lineno`. Zero MCP semconv attributes. The two unprefixed names (`request`, `response`) trigger 30 `missing_namespace` improvements. The two `code.*` attributes trigger 30 `deprecated` violations.

**Splunk.** Eight spans, structurally identical to the FastMCP native capture: same scope (`fastmcp`), same span names, same kinds, same nine attribute keys. A side-by-side fingerprint of the two captures returns the same `(scope, name, kind, attribute keys)` tuples. Reading `splunk-otel-instrumentation-fastmcp`'s source confirms what the captures show: the package wraps FastMCP via `wrapt` post-import hooks and routes through a separate `opentelemetry.util.genai.handler` singleton, and in the default configuration that handler did not emit any spans into the capture. The four `fastmcp.*`-namespaced attributes (`fastmcp.server.name`, `fastmcp.component.key`, `fastmcp.component.type`, `fastmcp.provider.type`) come from FastMCP itself, not from Splunk. The Splunk capture's only material difference from the FastMCP native capture is the absence of metric records, including the OTel SDK self-telemetry that FastMCP otherwise produces. A different env-var setup (`OTEL_INSTRUMENTATION_GENAI_ENABLE`, `OTEL_INSTRUMENTATION_GENAI_EMITTERS`) may activate Splunk's emission path; this audit covers the default.

Two clusters fall out of this. Traceloop and Logfire produce spans whose attributes don't sit in the MCP semconv vocabulary at all (the JSON-RPC method is recoverable from a payload string, but it isn't surfaced as `mcp.method.name`). FastMCP native and Splunk produce spans that match the semconv on the required attribute, the span name shape, and the span kind, with both sharing the same FastMCP-derived attribute set. The cluster split reflects the underlying frameworks: Traceloop and Logfire instrument the official `mcp` SDK; FastMCP native and Splunk instrument jlowin's `fastmcp`. The instrumentation layers don't seem to be normalizing the underlying frameworks toward a common semconv shape. They're emitting whatever was convenient, plus or minus some attempts to follow the spec.

## What this means for users

If you've already wired one of these into a pipeline, you have a working trace flow. The traces are useful internally even if they don't match the semconv. You can build dashboards. They'll be implementation-specific, which is fine until you swap.

If you're picking one today, two facts to keep in front of you:

* Half of the four don't emit `mcp.method.name`. That's the one attribute the semconv calls required, and downstream OTel-aware tooling (a backend that does method-level breakdowns, a sampler that routes on method, a Rego policy that asserts the attribute exists) will silently degrade against captures that lack it.
* None of the four emit MCP-semconv metrics. If you want operation-duration histograms keyed by `mcp.method.name`, you'll need to either compute them yourself from spans or wait. There's nothing that emits them today.

If your goal is portability across instrumentations, the picture is harder than it should be. The four don't agree on span names, on span kinds, on which attributes carry the MCP method, or on whether to use the `mcp.*` namespace at all. A query that works against one capture won't work against another, and the divergence is structural rather than cosmetic.

## What this means for implementors

The semconv is in Development status. Some of the divergence is unavoidable in this state. Some of it isn't.

The cheapest fixes are the deprecated-attribute warnings. `rpc.system` to `rpc.system.name`. `code.filepath` to `code.file.path`. `code.lineno` to `code.line.number`. Each is a one-line change. Weaver has been flagging these for some semconv releases; whoever rebases on a recent semconv will see them.

The `exception.escaped` type is a similar case. The attribute spec wants a boolean, two of the four packages emit a string. One change at the recording site fixes both packages, since they share the same underlying FastMCP attribute writer.

The `mcp.method.name` absence on Traceloop and Logfire is a deeper question. Both packages emit semantic information about the MCP operation; they just don't put it in the attribute the semconv demands. Adding it shouldn't be hard, but it requires a deliberate decision about which span shape is the public one. If `mcp.request.id` and `mcp.response.value` are stable Traceloop attributes that downstream Traceloop tooling relies on, dropping them is a breaking change. Adding `mcp.method.name` alongside them isn't.

The metrics absence is structural. None of the four packages I tested emits the MCP histograms, and that's not because the spec is unclear. The spec defines them. None of these four have wired them up yet. A reference implementation, even a simple one, would help.

## What's wanted from the OTel MCP working group

A few suggestions, offered as a user not a maintainer:

A conformance test fixture. Even a small one. The `mcp-otel-audit` repo's scenario harness is a stand-in; it would be more useful if the scenarios came from the spec authors and got versioned with the spec. Implementations could run it themselves before each release. Many of the divergences this audit found would not survive a self-test.

A model implementation that emits the metrics. The four histograms are well specified but currently unimplemented across the ecosystem. Even a pure-Python reference that wraps the official `mcp` SDK and emits the histograms would give downstream packages something to copy from.

Graduation of the core attribute set out of Development. Most of the spec's "improvement" findings against today's captures are `not_stable` notes, which is the spec telling Weaver "yes I know, I'm still moving." That's the right call right now. It's also the bit that, if it doesn't change in a few releases, will keep instrumentation maintainers cautious about wiring up against attributes whose names might still move.

## Reproducing the audit

The repo at [github.com/thebharathkumar/mcp-otel-audit](https://github.com/thebharathkumar/mcp-otel-audit) has the full pipeline. With Docker, `uv`, and Python 3.12 installed:

```bash
git clone https://github.com/thebharathkumar/mcp-otel-audit
cd mcp-otel-audit
./scripts/bootstrap.sh    # fetches the Weaver binary
make capture-all          # builds the 4 stacks, runs the scenarios, captures OTLP
make score-all            # runs Weaver live-check
```

The raw OTLP captures and Weaver score outputs that this writeup is built from are committed to the repo under `captures/`. They will go stale: PyPI will resolve newer versions of the four packages tomorrow than it did on 2026-04-28. The point of committing them is that anyone can re-score the same captures against a different semconv pin and see what changes. The point of having the harness is that anyone can re-capture against today's package versions and see what changes.

If you find that something here is wrong, or that an instrumentation has improved since this snapshot, please open an issue. The neutral framing of the report is intentional, but neutrality is also fragile when the data underneath is moving.
