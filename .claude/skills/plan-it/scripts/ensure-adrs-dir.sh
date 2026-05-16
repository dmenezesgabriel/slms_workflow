#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage: scripts/ensure-adrs-dir.sh [DIR]

Ensure an ADR directory exists.

Arguments:
  DIR   Directory to create. Defaults to: docs/adrs

Examples:
  scripts/ensure-adrs-dir.sh
  scripts/ensure-adrs-dir.sh docs/adrs
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

ADRS_DIR="${1:-docs/adrs}"

mkdir -p "$ADRS_DIR"
echo "ready: $ADRS_DIR"
