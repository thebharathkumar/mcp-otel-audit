#!/usr/bin/env bash
# Score one target's captured OTLP JSON against semantic-conventions@v1.40.0
# using OTel Weaver. Weaver's --input-source <file> mode expects its own flat
# sample format, not OTLP/JSON, so we replay our captured OTLP/JSONL through
# Weaver's OTLP/gRPC listener instead.
#
# Usage: scripts/score.sh <target>
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <target>" >&2; exit 2
fi
target="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

# Locate the platform-appropriate Weaver binary.
WEAVER=""
for d in "$ROOT/.tools"/weaver-*; do
  if [[ -x "$d/weaver" ]]; then WEAVER="$d/weaver"; break; fi
done
if [[ -z "$WEAVER" ]]; then
  echo "no Weaver binary found in .tools/. Run scripts/bootstrap.sh first." >&2
  exit 1
fi

CAPTURE="$ROOT/captures/${target}.json"
OUT="$ROOT/captures/${target}.weaver.json"

if [[ ! -s "$CAPTURE" ]]; then
  echo "missing capture: $CAPTURE. Run scripts/capture.sh $target first." >&2
  exit 1
fi

# Use a non-default port so we don't collide with anything else local.
WPORT=14317
ADMIN_PORT=14320
WLOG="$(mktemp)"

echo "[$target] starting weaver $($WEAVER --version | awk '{print $2}') on :$WPORT"
"$WEAVER" registry live-check \
  --registry 'https://github.com/open-telemetry/semantic-conventions.git@v1.40.0[model]' \
  --input-source otlp \
  --otlp-grpc-port "$WPORT" \
  --admin-port "$ADMIN_PORT" \
  --inactivity-timeout 300 \
  --format json \
  --no-stream true \
  > "$OUT" 2> "$WLOG" &
WPID=$!

cleanup() {
  if kill -0 "$WPID" 2>/dev/null; then
    curl -X POST "http://127.0.0.1:${ADMIN_PORT}/stop" >/dev/null 2>&1 || true
    sleep 1
    kill -TERM "$WPID" 2>/dev/null || true
  fi
  rm -f "$WLOG"
}
trap cleanup EXIT

# Wait until weaver opens its gRPC port (registry resolve takes a few seconds).
for i in $(seq 1 60); do
  if (echo > "/dev/tcp/127.0.0.1/${WPORT}") 2>/dev/null; then
    echo "[$target] weaver listening after ${i}s"
    break
  fi
  sleep 1
  if [[ "$i" == "60" ]]; then
    echo "[$target] weaver failed to listen. log:"; cat "$WLOG"; exit 1
  fi
done

echo "[$target] replaying $CAPTURE"
uv run --no-project --python 3.12 \
  --with 'opentelemetry-proto>=1.30,<2' --with 'grpcio>=1.60' --with 'protobuf' \
  python "$ROOT/scripts/otlp_replay.py" "$CAPTURE" "127.0.0.1:${WPORT}"

# Drain delay: weaver's OTLP receiver buffers briefly.
sleep 2

echo "[$target] stopping weaver"
curl -sS -X POST "http://127.0.0.1:${ADMIN_PORT}/stop" >/dev/null 2>&1 || true
wait "$WPID" 2>/dev/null || true

if [[ ! -s "$OUT" ]]; then
  echo "[$target] empty weaver output. log:"; cat "$WLOG"; exit 1
fi

# Quick sanity print
python3 -c "
import json, sys
j = json.load(open('$OUT'))
s = j.get('statistics', {})
print(f\"  total_entities: {s.get('total_entities')}\")
print(f\"  total_advisories: {s.get('total_advisories')}\")
print(f\"  advice_type_counts: {s.get('advice_type_counts')}\")
"
echo "[$target] wrote $OUT"
