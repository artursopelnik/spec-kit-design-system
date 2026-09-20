#!/usr/bin/env bash
# Emit gate prerequisites as one JSON object: feature paths, resolved config,
# the active adapter, which capabilities it maps, and whether the spec looks
# user-facing.
#
# Usage: check-design-gate.sh [--json]

set -euo pipefail
# shellcheck source=designsys-common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/designsys-common.sh"

designsys_run gate "$@"
