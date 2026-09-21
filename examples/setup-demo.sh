#!/usr/bin/env bash
# Build a throwaway spec-kit project wired to a design system.
#
#   ./examples/setup-demo.sh /tmp/demo
#   ./examples/setup-demo.sh /tmp/demo --system shadcn
#   ./examples/setup-demo.sh /tmp/demo --system mui --case toolbar-mobile
#
# The default is the Acme fixture, built so the ladder has to work rather than
# short-circuit; walk it with examples/README.md. `--system` swaps in one of the
# benchmark inventories (shadcn, radix, mui), which are trimmed snapshots of
# real design systems. `--case` adds that benchmark case's RFC and the code it
# talks about, so there is something real to run the workflow on.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT="$(dirname "$HERE")"

TARGET="/tmp/design-demo"
SYSTEM="acme"
CASE=""

positional=0
while [ $# -gt 0 ]; do
  case "$1" in
    --system) SYSTEM="$2"; shift 2 ;;
    --case)   CASE="$2"; shift 2 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *)
      if [ "$positional" -eq 0 ]; then TARGET="$1"; positional=1; shift
      else echo "unexpected argument: $1" >&2; exit 2; fi ;;
  esac
done

if [ "$SYSTEM" != "acme" ] && [ ! -d "$EXT/benchmarks/systems/$SYSTEM" ]; then
  echo "no such system: $SYSTEM (have: acme, $(ls "$EXT/benchmarks/systems" | tr '\n' ' '))" >&2
  exit 2
fi
if [ -n "$CASE" ] && [ ! -d "$EXT/benchmarks/cases/$CASE" ]; then
  echo "no such case: $CASE (have: $(ls "$EXT/benchmarks/cases" | tr '\n' ' '))" >&2
  exit 2
fi

rm -rf "$TARGET"
specify init "$TARGET" --integration claude --non-interactive --ignore-agent-tools >/dev/null
cd "$TARGET"

specify extension add --dev "$EXT" >/dev/null
specify preset add --dev "$EXT/preset" >/dev/null

if [ "$SYSTEM" = "acme" ]; then
  # The fixture stands in for a design system package installed from npm.
  mkdir -p node_modules/@acme/design-system
  cp "$HERE/acme-design-system/inventory.json" node_modules/@acme/design-system/
  cp "$HERE/acme-design-system/principles.yml" node_modules/@acme/design-system/principles.yml

  cat > .specify/extensions/design/design-config.yml <<'YAML'
adapter: static-json
source: "node_modules/@acme/design-system/inventory.json"
design_system_version: "2.1.0"
principles:
  # Acme publishes its own, so the extension's default set is never read.
  source: "node_modules/@acme/design-system/principles.yml"
YAML
else
  SRC="$EXT/benchmarks/systems/$SYSTEM"
  ADAPTER="$(python3 -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1]))['adapter'])" "$SRC/system.yml")"
  mkdir -p .design-system
  cp "$SRC/inventory.json" .design-system/inventory.json
  printf 'adapter: %s\nsource: ".design-system/inventory.json"\n' "$ADAPTER" \
    > .specify/extensions/design/design-config.yml
  if [ -f "$SRC/principles.yml" ]; then
    cp "$SRC/principles.yml" .design-system/principles.yml
    printf 'principles:\n  source: ".design-system/principles.yml"\n' \
      >> .specify/extensions/design/design-config.yml
  fi
fi

if [ -n "$CASE" ]; then
  cp "$EXT/benchmarks/cases/$CASE/rfc.md" rfc.md
  if [ -d "$EXT/benchmarks/cases/$CASE/seed" ]; then
    cp -R "$EXT/benchmarks/cases/$CASE/seed/." .
  fi
fi

echo "demo ready at $TARGET (system: $SYSTEM${CASE:+, case: $CASE})"
if [ -n "$CASE" ]; then
  echo "run it with: /speckit.design.run rfc.md"
fi
