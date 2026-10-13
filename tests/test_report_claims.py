"""Recompute REPORT.md's headline table from the committed raw captures.

These tests fail if the published numbers and the evidence in captures/ ever
disagree. Standard library plus pytest; no Docker, no network.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CAPTURES = ROOT / "captures"

REQUIRED_ATTR = "mcp.method.name"
MCP_HISTOGRAMS = {
    "mcp.client.operation.duration",
    "mcp.server.operation.duration",
    "mcp.client.session.duration",
    "mcp.server.session.duration",
}
SPAN_KIND_INTERNAL, SPAN_KIND_SERVER = 1, 2

# target: (spans, spans carrying mcp.method.name, span kind) from REPORT.md section 2
EXPECTED = {
    "traceloop": (20, 0, SPAN_KIND_INTERNAL),
    "fastmcp": (8, 8, SPAN_KIND_SERVER),
    "logfire": (15, 0, SPAN_KIND_INTERNAL),
    "splunk": (8, 8, SPAN_KIND_SERVER),
}


def load(target: str) -> tuple[list[dict], set[str]]:
    """Return (spans, metric names) from an OTLP file-exporter capture (one JSON object per line)."""
    spans: list[dict] = []
    metrics: set[str] = set()
    for line in (CAPTURES / f"{target}.json").read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        for rs in obj.get("resourceSpans", []):
            for ss in rs.get("scopeSpans", []):
                spans.extend(ss.get("spans", []))
        for rm in obj.get("resourceMetrics", []):
            for sm in rm.get("scopeMetrics", []):
                metrics.update(m["name"] for m in sm.get("metrics", []))
    return spans, metrics


@pytest.mark.parametrize("target", sorted(EXPECTED))
def test_required_attribute_coverage_matches_report(target):
    spans, _ = load(target)
    n_spans, n_required, _ = EXPECTED[target]
    with_required = sum(
        1 for s in spans if any(a["key"] == REQUIRED_ATTR for a in s.get("attributes", []))
    )
    assert (len(spans), with_required) == (n_spans, n_required)


@pytest.mark.parametrize("target", sorted(EXPECTED))
def test_span_kind_matches_report(target):
    spans, _ = load(target)
    assert {s.get("kind") for s in spans} == {EXPECTED[target][2]}


@pytest.mark.parametrize("target", sorted(EXPECTED))
def test_no_target_emits_the_mcp_histograms(target):
    _, metrics = load(target)
    assert not (metrics & MCP_HISTOGRAMS)


def test_splunk_capture_has_no_metric_records():
    """Report section 3.4: the Splunk capture contains zero metric records of any kind."""
    _, metrics = load("splunk")
    assert metrics == set()
