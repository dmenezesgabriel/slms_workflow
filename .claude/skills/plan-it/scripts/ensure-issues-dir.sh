#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage: scripts/ensure-issues-dir.sh [DIR]

Ensure an issues directory exists.

Arguments:
  DIR   Directory to create. Defaults to: issues

Examples:
  scripts/ensure-issues-dir.sh
  scripts/ensure-issues-dir.sh issues
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

ISSUES_DIR="${1:-issues}"

mkdir -p "$ISSUES_DIR"
echo "ready: $ISSUES_DIR"