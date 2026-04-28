# Resumption prompt — paste this into a fresh agent session

You are an autonomous coding agent. You are continuing a paused build of **mcp-otel-audit**:
a public audit report comparing four MCP OpenTelemetry instrumentations against the official
OpenTelemetry semantic conventions for MCP, with a small reproducible scenario harness as
the substrate that makes the report credible.

The artifact people will read is `REPORT.md` and a blog post draft. The scenario harness
exists to make the report reproducible. **This is NOT a pip-installable Python package.**

## Resume from where the prior session stopped

Working dir: `/Users/bharathkumarr/Desktop/eval`. Two artifacts already exist on disk and
contain the full prior context. **Read them first, in order:**

1. `MISSING_NICHE.md` — three rounds of niche analysis (`mcp-eval`, `mcp-otel`,
   `mcp-conformance`) that landed on this scope. Last round's conclusion: do not build a
   Python package; ship a report using OTel Weaver as the scoring engine.
2. `PHASE0.md` — pre-flight report with what's been verified and what's blocking.

After reading those, you'll know:
- Phase 0 STOP gate 1 (Weaver scores MCP semconv) is **CLEARED** with v1.40.0.
- Phase 0 STOP gate 2 (4 targets installable) is **PARTIAL**: Traceloop installed clean,
  FastMCP failed on `cryptography` extraction due to disk-full, Logfire and Splunk not
  attempted.
- Two environmental blockers existed at pause: disk full (137 Mi free) and Docker daemon
  not running.

## First thing to do every resumption: re-check the blockers

Run, in order, and confirm both pass before doing anything else:

```bash
df -h /System/Volumes/Data | tail -1                  # need >5 GiB free
docker info >/dev/null 2>&1 && echo OK || echo "DOCKER NOT RUNNING"
ls /Users/bharathkumarr/Desktop/eval/.tools/weaver-aarch64-apple-darwin/weaver  # binary still there?
ls /Users/bharathkumarr/Desktop/eval/.tools/semconv-mcp-v1.40.0/model/mcp/      # 4 yaml files
~/.local/bin/uv --version                             # uv installed
```

If disk is still tight or Docker is still down, **stop and report**. Do not work around
either by shrinking scope or skipping targets.

If both pass, finish the rest of Phase 0:

```bash
# Verify the remaining three targets install
export PATH="$HOME/.local/bin:$PATH"
cd /tmp && uv venv --python 3.12 .venv-fastmcp && source .venv-fastmcp/bin/activate \
  && uv pip install fastmcp && python -c "import fastmcp; print(fastmcp.__version__)"
cd /tmp && uv venv --python 3.12 .venv-logfire && source .venv-logfire/bin/activate \
  && uv pip install logfire && python -c "import logfire; print(logfire.__version__)"
cd /tmp && uv venv --python 3.12 .venv-splunk && source .venv-splunk/bin/activate \
  && uv pip install splunk-otel-instrumentation-fastmcp \
  && python -c "import splunk_otel_instrumentation_fastmcp"  # adjust import name to actual
```

If two or more fail for non-environmental reasons, **stop and surface** — propose
substitutes or a smaller comparison set per the original prompt's gating rule.

## What to build (Phases 1-6)

The repo will live at `/Users/bharathkumarr/Desktop/eval/mcp-otel-audit/`. Project name:
**mcp-otel-audit** (do not use `mcp-conformance` — that collides with the official
`modelcontextprotocol/conformance` repo).

### Phase 1: skeleton
- `mcp-otel-audit/` with `README.md` (placeholder pointing to `reports/REPORT.md`),
  `LICENSE` (Apache-2.0), `.gitignore`
- `scripts/scenarios.py` (Phase 3)
- `targets/{traceloop,fastmcp,logfire,splunk}/` (Phase 2)
- `captures/` (Phase 4)
- `reports/REPORT.md` (Phase 5)
- `docs/blog/auditing-mcp-otel.md` (Phase 6)
- `Makefile` with `make capture-all`, `make score-all`, `make report`

### Phase 2: four target stacks
For each of `traceloop`, `fastmcp`, `logfire`, `splunk`, build a docker-compose stack:
- minimal MCP server with the **same three tools across all four**: `echo(text: str)`,
  `fetch_mock_data(key: str)`, `calculate(op: str, a: float, b: float)`
- only variable across stacks is the instrumentation
- OTel Collector configured with `file` exporter dumping OTLP JSON to a known path
- exposes the MCP server on a known port (pick non-conflicting ports per stack)
- per-stack `README.md` documenting how to start it

Tool implementations must be byte-identical across stacks. Anything different is the
instrumentation, full stop.

### Phase 3: scenario exerciser
`scripts/scenarios.py` — Python script using the official `mcp` Python SDK as client. Six
scenarios in fixed order:
1. `tool_call_success` — call `echo("hello")`, assert response
2. `tool_call_with_error` — call `calculate("div", 1, 0)`, capture error
3. `tool_call_with_invalid_args` — call `echo({})` or similar malformed payload
4. `session_lifecycle` — open session, list tools, close cleanly
5. `multiple_concurrent_calls` — 5 parallel `echo` calls via asyncio.gather
6. `streaming_response` — if supported by impl, call streaming tool; otherwise log
   "not supported" (do NOT skip — that IS data)

Deterministic. Reproducible. Exit code reflects whether all scenarios completed. Test
end-to-end against the `traceloop` target before Phase 4.

### Phase 4: capture
For each target: `docker-compose up`, run `scripts/scenarios.py` against it, graceful
shutdown, copy capture file to `captures/<target>.json`. Sanity-check each capture
non-empty. Document any implementation that failed any scenario — the data is the data.

### Phase 5: score with Weaver, write REPORT.md
For each capture, run:
```bash
~/.local/bin/uv run --no-project /Users/bharathkumarr/Desktop/eval/.tools/weaver-aarch64-apple-darwin/weaver \
  registry live-check \
  --registry 'https://github.com/open-telemetry/semantic-conventions.git@v1.40.0[model]' \
  --input-source captures/<target>.json --input-format json \
  --format json --output captures/<target>.weaver.json
```

Write `reports/REPORT.md` with:
- Methodology (semconv v1.40.0 pin, Weaver v0.23.0, scenario list, MCP SDK version, OS,
  date 2026-04-XX)
- Headline comparison table: rows = implementations, columns = (REQUIRED_PRESENT,
  RECOMMENDED_PRESENT, NAME_MATCH, VALUE_VALID, METRIC_COVERAGE), cells = pass percentages
- Per-implementation section: what passed, what failed, specific examples
- Severity summary: counts of REQUIRED_MISSING / RECOMMENDED_MISSING / NAME_MISMATCH per
  target
- Honest caveats: semconv is Development status; captures are point-in-time; scenarios
  limited
- Reproduction instructions

### Phase 6: blog post draft
`docs/blog/auditing-mcp-otel.md`, 1500-2500 words. Structure: hook → why → methodology →
results → what this means for users / implementors → what's wanted next from OTel WG →
reproducibility. Run a humanizer pass: zero em dashes, no rule-of-three padding, no
significance inflation, no "delve" / "leverage" / "robust" cliches, varied sentence length.
Save as draft; posting is manual.

## Hard constraints (compact)

- Python 3.12+, `uv` for environments. No new global pip installs.
- **Use Weaver for scoring. Do not reimplement.** Use Weaver for OTLP collection too if
  feasible (`weaver registry live-check` listening on 4317), or use OTel Collector's `file`
  exporter — never both.
- Pin `semantic-conventions@v1.40.0`. Document in code, README, and report.
- Same three tools, same schemas, same behavior across all four target stacks. Anything
  else is the instrumentation under test.
- Raw OTLP captures committed to repo. Anyone with Docker + uv must be able to re-run.
- Repo name is `mcp-otel-audit`, not `mcp-conformance` or `mcp-otel` (both collide).
- Neutral language in the report. No editorial slag. The numbers carry the message.
- Do not modify the target instrumentations to make them score better. Audit is a
  snapshot.
- Do not skip scenarios that one impl doesn't support. Document the gap.
- Do not pin to an unreleased semconv (no draft PRs). v1.40.0 only.

## Reporting protocol

After each phase:
- What was built (1-2 sentences)
- Tests / smoke checks passing or failing
- Anything that diverged from this prompt with rationale
- Next phase

Begin by reading `MISSING_NICHE.md` and `PHASE0.md`. Then run the blocker re-check above.
Then complete Phase 0 (remaining three installs). Then Phase 1.
