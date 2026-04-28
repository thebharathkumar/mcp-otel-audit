#!/usr/bin/env bash
# Bring up one target's docker-compose stack, run the scenarios against it,
# stop the stack, and copy the captured OTLP JSON to captures/<target>.json.
#
# Usage: scripts/capture.sh <target>
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <target>" >&2; exit 2
fi
target="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$ROOT/targets/$target"

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "no such target: $target" >&2; exit 1
fi

# Per-target port (host-side) is encoded in the docker-compose file.
# Inside the network, the MCP server always listens on 8000.
case "$target" in
  traceloop) HOST_PORT=18001 ;;
  fastmcp)   HOST_PORT=18002 ;;
  logfire)   HOST_PORT=18003 ;;
  splunk)    HOST_PORT=18004 ;;
  *) echo "unknown port for target $target" >&2; exit 1 ;;
esac

cd "$TARGET_DIR"
rm -rf capture-out
mkdir -p capture-out
chmod 0777 capture-out  # the otelcol-contrib container runs as a non-root user

echo "[$target] docker compose up --build"
docker compose up -d --build

cleanup() {
  echo "[$target] docker compose down"
  ( cd "$TARGET_DIR" && docker compose down -v >/dev/null 2>&1 || true )
}
trap cleanup EXIT

# Wait for the MCP streamable-HTTP endpoint to actually answer HTTP, not
# just TCP-accept. The transport manager warms up after Uvicorn binds, so a
# bare nc-style port check will return success before the session handler
# is ready and the first scenario fails with a TaskGroup error.
echo "[$target] waiting for MCP server on localhost:$HOST_PORT"
for i in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' -m 2 \
            -X POST "http://localhost:$HOST_PORT/mcp/" \
            -H 'Content-Type: application/json' \
            -H 'Accept: application/json, text/event-stream' \
            --data '{"jsonrpc":"2.0","id":1,"method":"ping"}' 2>/dev/null || true)"
  # Any real HTTP status means the streamable-http handler is up. 000 = connection refused.
  if [[ "$code" != "000" && -n "$code" ]]; then
    echo "[$target] server up (HTTP $code)"
    sleep 1   # tiny grace period for full async init
    break
  fi
  sleep 1
  if [[ "$i" == "60" ]]; then
    echo "[$target] server did not come up in 60s. logs:"
    docker compose logs --tail=80
    exit 1
  fi
done

cd "$ROOT"
echo "[$target] running scenarios"
uv run --no-project --python 3.12 \
  --with 'mcp>=1.0' \
  python scripts/scenarios.py \
    --target "$target" \
    --endpoint "http://localhost:${HOST_PORT}/mcp/" \
    --meta-out "captures/${target}.meta.json"

echo "[$target] flushing collector"
sleep 10

# Stop the stack gracefully so the file exporter flushes.
( cd "$TARGET_DIR" && docker compose stop >/dev/null 2>&1 || true )
sleep 2

if [[ ! -s "$TARGET_DIR/capture-out/otlp.json" ]]; then
  echo "[$target] empty capture file. collector did not write. Logs:"
  ( cd "$TARGET_DIR" && docker compose logs --tail=100 otel-collector )
  exit 1
fi

cp "$TARGET_DIR/capture-out/otlp.json" "$ROOT/captures/${target}.json"
echo "[$target] captured $(wc -l < "$ROOT/captures/${target}.json") OTLP records to captures/${target}.json"
