#!/usr/bin/env bash
# Read and write the design decision ledger.
#
# Usage:
#   ds-ledger.sh --json lookup "date range selection"
#   ds-ledger.sh --json lookup "period filter" --threshold 0.25
#   ds-ledger.sh --json record <file.json>    # or '-' to read stdin
#   ds-ledger.sh --json list
#
# The ledger lives at .specify/memory/design-decisions.yml and is committed with
# the repository. It is the answer to "did we already decide this?", which is a
# question every feature otherwise re-asks the design system from scratch.

set -euo pipefail
# shellcheck source=designsys-common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/designsys-common.sh"

args=()
for arg in "$@"; do
    [[ "$arg" == "--json" ]] && continue
    args+=("$arg")
done

if [[ ${#args[@]} -eq 0 ]]; then
    echo "[designsys] usage: ds-ledger.sh --json <lookup|record|list> [value]" >&2
    exit 1
fi

designsys_run ledger "${args[@]}"
