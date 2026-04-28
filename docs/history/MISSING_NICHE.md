# Phase 0: Niche Analysis for mcp-conformance

**Date:** 2026-04-27
**Author:** mcp-conformance pre-flight investigation
**Verdict:** **STOP the framework. Ship the report directly.**

The proposed `mcp-conformance` design collides on two axes simultaneously:

1. **Name collision** with `github.com/modelcontextprotocol/conformance`, the official MCP
   project's conformance test framework (different scope — wire protocol — but same brand).
2. **Functional collision** with OpenTelemetry Weaver's `live-check` command, which already
   ships everything the prompt describes except an MCP-specific scenario exerciser.

The real gap that exists — a small MCP scenario harness that drives an instrumented server,
pipes the OTLP stream into Weaver, and publishes the resulting compliance report against the
four current implementations — is a **1-day project, not a 3-4-day Python package**. The
artifact that travels is the comparison report. The infrastructure is mostly already built.

---

## Finding 1: The name `conformance` is owned by the MCP project itself

**`github.com/modelcontextprotocol/conformance`**
- Official, maintained by the modelcontextprotocol org.
- 63 stars, 39 forks, latest release `v0.1.16` on 2026-03-27 (one month ago).
- TypeScript primarily.
- Scope: tests **MCP wire-protocol compliance** — initialization handshakes, tool invocation,
  capability negotiation, prompt handling, resource management. SEP-1730 SDK Tiering System.
- Provides the `tier-check` CLI.
- **Does not cover OTel semconv emission.** Different scope from the prompt.

The name overlap is the issue. A new `mcp-conformance` Python package on PyPI competes for
search traffic with the official MCP conformance tool, which has 17 releases and active
maintenance. Anyone Googling "mcp conformance" lands on the official one first.

A different name would solve this — but see Finding 2 before deciding to ship anything at
all.

---

## Finding 2: OTel Weaver already does the conformance scoring

**`open-telemetry/weaver`** is the official OTel tooling project. The command:

```
weaver registry live-check --registry <path or URL>
```

does the following, today, as a stable (not experimental) feature:

| Prompt's design for mcp-conformance | What Weaver `live-check` already does |
|---|---|
| In-process OTLP collector (HTTP + gRPC) | Yes — accepts OTLP via file, stdin, or live stream |
| Parse the official MCP semconv | Yes — points at `open-telemetry/semantic-conventions` registry directly; MCP semconv lives there |
| Score emissions against the semconv | Yes — produces compliance findings per signal, per attribute |
| Severity levels (REQUIRED_MISSING, etc.) | Yes — model compliance + custom Rego policies for additional invariants |
| Output JSON, YAML, structured report | Yes — JSON, YAML, JSONL, ANSI templates |
| Live streaming mode | Yes — default mode for OTLP/stdin input |
| Custom checks (attribute pattern, value range) | Yes — Rego policy engine, every attribute and signal passes through it |
| CI/CD integration | Yes — explicitly designed for this |

Weaver is written in Rust, ships as a binary, and is maintained by the OTel project itself.
Building a Python equivalent specifically for MCP would be re-implementing it for one
semconv subset. The MCP semconv is *already in the registry Weaver consumes by default*.

---

## Finding 3: The OTel MCP semconv is in "Development" status

**Real flux risk.** The semconv at https://opentelemetry.io/docs/specs/semconv/gen-ai/mcp/
is marked Development — meaning attribute names, span structure, and metric definitions
are not stable. Concretely this means:

- A package pinned to today's semconv may need to update on every OTel semconv release,
  which is monthly during a spec's Development phase.
- The four target implementations are emitting against *different snapshots* of an
  unstable spec. Some of their "non-conformance" today is genuinely the spec moving under
  them.
- A report published today is a snapshot, not a durable artifact. It needs a clearly
  visible version pin and a "valid as of" date.

This isn't a STOP signal by itself, but it does change the framing: this is a **moment-in-time
audit** of how implementations track an unstable spec, not a long-term certification.

---

## What's actually missing

Strip away the parts already shipped by Weaver and `modelcontextprotocol/conformance`, and
what's left is:

> **An MCP-specific scenario exerciser:** a script that connects to an MCP server via the
> official Python SDK, runs a fixed sequence of operations (tool call, error, session
> lifecycle, concurrent calls, streaming response), and outputs an OTLP stream that
> downstream tooling can consume.

That's it. Roughly 200-400 lines of Python. The exerciser pairs with `weaver live-check`
to produce a compliance report; pair with the runs against four implementations to produce a
comparison.

The report is the artifact. The exerciser is glue.

---

## Three viable paths forward

### Path A — Skip the package entirely. Ship the report.

1. Write a 250-line Python script `exercise.py` using the official MCP Python SDK that runs
   the six scenarios. Total time: half a day.
2. Stand up the four implementations in `examples/` with docker-compose (or just venvs).
   Total time: half a day.
3. For each implementation, run `exercise.py` with OTLP export pointed at a captured stream,
   then run `weaver registry live-check` against the captured stream. Total time: half a day.
4. Write the comparison report (the actual content) and a 1500-word writeup. Total time: a
   day.

Total: 2-3 days. Same artifact as the proposed v0.1.0. Doesn't compete with anything. The
writeup positions it correctly: "I used Weaver to audit the four MCP OTel instrumentations.
Here's what's conformant."

This is honest about what the work is (an audit), credits the existing tooling, and ships
the artifact that travels.

### Path B — Ship the exerciser as a thin package (`mcp-otel-exerciser` or similar).

A small package that exposes the scenario suite as a CLI:

```
mcp-otel-exerciser run --target <endpoint> --scenarios all > otlp.jsonl
weaver registry live-check --input otlp.jsonl
```

Different name. Stays small. Composes with Weaver rather than duplicating it. Could grow
adoption if MCP semconv stabilizes and others want to run conformance audits.

This is honest if there's confidence the scenarios themselves have lasting value beyond the
one-shot report. Risk: nobody has asked for this; the scenarios may just be one-time audit
fixtures.

### Path C — Proceed with the prompt as written.

Build the parallel scorer + collector + CLI in Python. Land a less-mature reimplementation of
Weaver, scoped to MCP. Pin against an unstable semconv. Compete on PyPI with the official
`modelcontextprotocol/conformance` for search traffic.

I do not recommend this.

---

## Recommendation

**Path A.** The report is the actual deliverable; the framework is overhead. A 2-3-day
shipped audit using Weaver as the engine produces the same headline artifact as a 3-4-day
Python package, with no name collision, no semconv reimplementation, and an honest framing.

If the user wants something pip-installable as the durable byproduct, **Path B** is fine, but
the package should be named for what it actually is (a scenario exerciser) rather than for
what it isn't (a conformance scorer).

**Path C** is the wrong call. The prompt's gating rule applies cleanly: "If a conformance
audit tool already exists with reasonable adoption, write MISSING_NICHE.md and STOP." Weaver
is that tool.

### Specific divergences from the prompt that I would not implement

- The "OTLP collector" component (Phase 3). Use Weaver, or `otelcol` in test mode, or the
  OTel SDK's `InMemorySpanExporter` for tests. Reimplementing OTLP receivers in Python is
  scope creep.
- The "Conformance scorer" component (Phase 5). Weaver does this. Rego policies are how OTel
  expects you to extend it.
- The "Semconv parser" component (Phase 2). The semconv repo provides YAML; Weaver consumes
  it natively. A Python re-parser is a maintenance liability.

The work that should happen in Path A:

- **Phase 0:** this document. Done.
- **Phase 1:** the 6 scenarios as a Python script. The MCP client wiring for each.
- **Phase 2:** docker-compose stacks for the four implementations.
- **Phase 3:** the run-and-collect harness (could be a 50-line shell script).
- **Phase 4:** Weaver invocation + report parsing.
- **Phase 5:** the comparison report (Markdown).
- **Phase 6:** the 1500-word writeup.

That's the ship. No PyPI package is required for any of it.

---

## Summary table for the prompt's gating rules

| Prompt's STOP condition | Triggered? |
|---|---|
| "If a conformance audit tool already exists with reasonable adoption" | **Yes** — Weaver `live-check`, official OTel project, stable. |
| "If the official semconv is in flux (e.g. major rev expected within days), surface that risk" | **Yes** — semconv is in "Development" status, will change. Surfaced. |

Both gates triggered. The honest call is to stop building the framework and ship the report.

---

*Phase 0 artifact per the project prompt. The prompt asked for a STOP if the niche is filled.
It is. Path A is the constructive alternative that produces the same headline artifact in
less time.*
