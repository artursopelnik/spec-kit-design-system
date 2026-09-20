#!/usr/bin/env bash
# Build a throwaway spec-kit project wired to the Acme fixture design system.
#
#   ./examples/setup-demo.sh /tmp/demo
#
# Then walk WALKTHROUGH.md inside it.

set -euo pipefail
TARGET="${1:-/tmp/designsys-demo}"
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
cp "$HERE/acme-design-system/rules.yml" node_modules/@acme/design-system/spec-kit-rules.yml

cat > .specify/extensions/designsys/designsys-config.yml <<'YAML'
adapter: static-json
source: "node_modules/@acme/design-system/inventory.json"
design_system_version: "2.1.0"
rules:
  baseline: true
  house_rules: "node_modules/@acme/design-system/spec-kit-rules.yml"
YAML

echo "demo ready at $TARGET"
