#!/usr/bin/env bash
# Cross-compiles tools/vx_ha_cli against the real, published mcMineyC/vx_puppet
# module and drops static linux/amd64 + linux/arm64 binaries into
# custom_components/veracross/bin/, where the integration expects them.
#
# Run this locally (or in CI) whenever vx_puppet gets a new release you want
# to pick up, then commit the resulting bin/ diff before tagging a new
# integration version.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOL_DIR="$REPO_ROOT/tools/vx_ha_cli"
OUT_DIR="$REPO_ROOT/custom_components/veracross/bin"

mkdir -p "$OUT_DIR"
cd "$TOOL_DIR"

echo "==> pulling latest vx_puppet"
go get github.com/mcMineyC/vx_puppet@latest
go mod tidy

for arch in amd64 arm64; do
  echo "==> building linux/$arch"
  CGO_ENABLED=0 GOOS=linux GOARCH="$arch" \
    go build -ldflags="-s -w" -o "$OUT_DIR/vx_ha_cli_linux_$arch" .
done

echo "==> done, binaries in $OUT_DIR:"
ls -la "$OUT_DIR"
