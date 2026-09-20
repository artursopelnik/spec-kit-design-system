#!/usr/bin/env bash
# Build a throwaway spec-kit project wired to the Acme fixture design system.
#
#   ./examples/setup-demo.sh /tmp/demo
#
# Then walk examples/README.md against it.

set -euo pipefail
TARGET="${1:-/tmp/design-demo}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT="$(dirname "$HERE")"

rm -rf "$TARGET"
specify init "$TARGET" --integration claude --non-interactive --ignore-agent-tools >/dev/null
cd "$TARGET"

specify extension add --dev "$EXT" >/dev/null
specify preset add --dev "$EXT/preset" >/dev/null

# The fixture stands in for a design system package installed from npm.
mkdir -p node_modules/@acme/design-system
cp "$HERE/acme-design-system/inventory.json" node_modules/@acme/design-system/
cp "$HERE/acme-design-system/guidelines.yml" node_modules/@acme/design-system/guidelines.yml

cat > .specify/extensions/design/design-config.yml <<'YAML'
adapter: static-json
source: "node_modules/@acme/design-system/inventory.json"
design_system_version: "2.1.0"
guidelines:
  # Acme publishes its own, so the extension's default set is never read.
  source: "node_modules/@acme/design-system/guidelines.yml"
YAML

echo "demo ready at $TARGET"
