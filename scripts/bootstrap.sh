#!/usr/bin/env bash
# Fetch the OTel Weaver binary into .tools/.
# Pinned to v0.23.0 per PINS.md. Re-running this will skip if the binary is present.
set -euo pipefail

WEAVER_VERSION="v0.23.0"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/.tools"
mkdir -p "$TOOLS"

uname_s="$(uname -s)"
uname_m="$(uname -m)"

case "$uname_s-$uname_m" in
  Linux-x86_64)   asset="weaver-x86_64-unknown-linux-gnu" ;;
  Linux-aarch64)  asset="weaver-aarch64-unknown-linux-gnu" ;;
  Darwin-x86_64)  asset="weaver-x86_64-apple-darwin" ;;
  Darwin-arm64)   asset="weaver-aarch64-apple-darwin" ;;
  *) echo "Unsupported platform: $uname_s-$uname_m" >&2; exit 1 ;;
esac

if [[ -x "$TOOLS/$asset/weaver" ]]; then
  echo "weaver already present at .tools/$asset/weaver"
  "$TOOLS/$asset/weaver" --version
  exit 0
fi

url="https://github.com/open-telemetry/weaver/releases/download/${WEAVER_VERSION}/${asset}.tar.xz"
echo "fetching $url"
curl -LsSf -o "$TOOLS/${asset}.tar.xz" "$url"
tar -xf "$TOOLS/${asset}.tar.xz" -C "$TOOLS"
rm "$TOOLS/${asset}.tar.xz"
"$TOOLS/$asset/weaver" --version
