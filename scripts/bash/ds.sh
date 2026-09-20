#!/usr/bin/env bash
# One entry point for everything this extension can be asked.
#
#   ds.sh gate                                   prerequisites + resolved config
#   ds.sh workflow status                        where the run is, and what is next
#   ds.sh rfc <path|->                           normalize an RFC
#   ds.sh context <phase> [--applies-to k,k]     focused context for one phase
#                 [--component Name] [--query q]
#   ds.sh guidelines [--applies-to k,k]          the guidelines in force
#   ds.sh query <capability> [args...]           ask the design system anything
#   ds.sh ledger lookup|record|list [value]      prior design decisions
#
# Always emits one JSON object. An unmapped or unreachable capability comes back
# as {"available": false, "reason": "..."} rather than a non-zero exit, so
# callers can degrade deliberately instead of crashing.
#
# The logic lives in scripts/python/design.py; this file only finds a usable
# interpreter and forwards. Callers without bash can invoke the module directly:
#   python3 .specify/extensions/design/scripts/python/design.py <same args>

set -euo pipefail

# Windows commonly resolves `python3` to a Microsoft Store App Execution Alias
# that exits 49 without running anything, so probe before committing to it —
# this mirrors the guard in spec-kit's own scripts/bash/common.sh.
design_python() {
    local candidate
    for candidate in python3 python py; do
        if command -v "$candidate" >/dev/null 2>&1 &&
            "$candidate" -c 'import sys; raise SystemExit(sys.version_info.major != 3)' >/dev/null 2>&1; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    return 1
}

if ! PY=$(design_python); then
    echo "[design] No working Python 3 interpreter found. This extension needs one to read its YAML configuration." >&2
    exit 1
fi

ENTRY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../python/design.py"
if [[ ! -f "$ENTRY" ]]; then
    echo "[design] Missing $ENTRY" >&2
    exit 1
fi

# --json is accepted anywhere and dropped: the output is always JSON. Commands
# pass it out of spec-kit convention.
args=()
for arg in "$@"; do
    [[ "$arg" == "--json" ]] && continue
    args+=("$arg")
done

if [[ ${#args[@]} -eq 0 ]]; then
    sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
    exit 1
fi

exec "$PY" "$ENTRY" "${args[@]}"
