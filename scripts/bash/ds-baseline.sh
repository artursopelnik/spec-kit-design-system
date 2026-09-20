#!/usr/bin/env bash
# Requirements that hold for every design system, which specs omit because they
# are too obvious to write down.
#
# Usage:
#   ds-baseline.sh --json
#   ds-baseline.sh --json --applies-to interactive,layout
#   ds-baseline.sh --json --dimension accessibility
#
# `--applies-to` filters to what the feature actually involves, so a static text
# block does not carry twenty rules about interactive states. Rules marked
# `applies_to: any` are always returned.
#
# Nothing here carries a value from your design system. Colors, breakpoints and
# spacing come from the CLI via ds-query.sh.

set -euo pipefail
# shellcheck source=designsys-common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/designsys-common.sh"

args=()
for arg in "$@"; do
    [[ "$arg" == "--json" ]] && continue
    args+=("$arg")
done

designsys_run baseline "${args[@]}"
