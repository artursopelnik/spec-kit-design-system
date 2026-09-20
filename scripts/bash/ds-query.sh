#!/usr/bin/env bash
# Ask the design system a question through the configured adapter.
#
# Usage:
#   ds-query.sh --json search "date range selection"
#   ds-query.sh --json component "DatePicker"
#   ds-query.sh --json pattern "filter bar"
#   ds-query.sh --json tokens [theme]
#   ds-query.sh --json extend "DatePicker"
#   ds-query.sh --json report_gap "<title>" "<body>"
#   ds-query.sh --json describe
#
# Always emits JSON. An unmapped or unreachable capability comes back as
# {"available": false, "reason": "..."} rather than a non-zero exit, so callers
# can degrade deliberately instead of crashing.

set -euo pipefail
# shellcheck source=designsys-common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/designsys-common.sh"

args=()
for arg in "$@"; do
    [[ "$arg" == "--json" ]] && continue
    args+=("$arg")
done

if [[ ${#args[@]} -eq 0 ]]; then
    echo "[designsys] usage: ds-query.sh --json <capability> [args...]" >&2
    exit 1
fi

designsys_run query "${args[@]}"
