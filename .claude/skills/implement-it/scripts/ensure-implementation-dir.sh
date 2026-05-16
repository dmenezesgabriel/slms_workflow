# implement-it/scripts/ensure-implementation-dir.sh
#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage: scripts/ensure-implementation-dir.sh [DIR]

Ensure an implementation summary directory exists.

Arguments:
  DIR   Directory to create. Defaults to: implementation

Examples:
  scripts/ensure-implementation-dir.sh
  scripts/ensure-implementation-dir.sh implementation
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

IMPLEMENTATION_DIR="${1:-implementation}"

mkdir -p "$IMPLEMENTATION_DIR"
echo "ready: $IMPLEMENTATION_DIR"
