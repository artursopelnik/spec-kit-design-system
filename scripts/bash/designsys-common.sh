#!/usr/bin/env bash
# Shared shim resolution for the designsys extension.
#
# The logic lives in scripts/python/designsys.py so that capability dispatch and
# ledger matching cannot drift between runtimes. These scripts only locate a
# usable interpreter and forward arguments.

set -euo pipefail

designsys_script_dir() {
    cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

# Windows commonly resolves `python3` to a Microsoft Store App Execution Alias
# that exits 49 without running anything, so probe before committing to it —
# this mirrors the guard in spec-kit's own scripts/bash/common.sh.
designsys_python() {
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

designsys_run() {
    local py entry
    if ! py=$(designsys_python); then
        echo "[designsys] No working Python 3 interpreter found. The design system extension needs one to read its YAML configuration." >&2
        return 1
    fi
    entry="$(designsys_script_dir)/../python/designsys.py"
    if [[ ! -f "$entry" ]]; then
        echo "[designsys] Missing $entry" >&2
        return 1
    fi
    "$py" "$entry" "$@"
}
