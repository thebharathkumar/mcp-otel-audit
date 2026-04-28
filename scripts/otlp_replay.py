"""Replay an OTLP/JSON capture (one ExportXxxServiceRequest per line)
into an OTLP/gRPC receiver. Used to feed `captures/<target>.json` into a
running `weaver registry live-check` so Weaver can score it.

Why a separate replay step instead of feeding Weaver during capture:
the audit demands a raw OTLP archive (`captures/<target>.json`) that
anyone can re-score later against a different semconv pin. Capturing once
to a file and replaying offline makes that archive the source of truth.

Usage:
    python scripts/otlp_replay.py captures/traceloop.json 127.0.0.1:14317
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import grpc
from google.protobuf.json_format import Parse
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2, metrics_service_pb2_grpc
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2, trace_service_pb2_grpc


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: otlp_replay.py <jsonl-file> <host:port>", file=sys.stderr)
        return 2

    inp = Path(sys.argv[1])
    target = sys.argv[2]
    if not inp.exists() or not inp.stat().st_size:
        print(f"input missing or empty: {inp}", file=sys.stderr)
        return 1

    ch = grpc.insecure_channel(target)
    trace_stub = trace_service_pb2_grpc.TraceServiceStub(ch)
    metric_stub = metrics_service_pb2_grpc.MetricsServiceStub(ch)

    n_traces = n_metrics = n_unknown = 0
    for line in inp.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        j = json.loads(line)
        if "resourceSpans" in j:
            req = trace_service_pb2.ExportTraceServiceRequest()
            Parse(line, req)
            trace_stub.Export(req, timeout=10)
            n_traces += 1
        elif "resourceMetrics" in j:
            req = metrics_service_pb2.ExportMetricsServiceRequest()
            Parse(line, req)
            metric_stub.Export(req, timeout=10)
            n_metrics += 1
        else:
            n_unknown += 1

    print(f"replayed traces={n_traces} metrics={n_metrics} unknown={n_unknown} -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
