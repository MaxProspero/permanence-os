#!/bin/zsh
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$BASE_DIR/.venv/bin/python"

if [[ -x "$PYTHON_BIN" ]]; then
  exec "$PYTHON_BIN" "$BASE_DIR/cli.py" operator-surface "$@"
fi

exec /usr/bin/env python3 "$BASE_DIR/cli.py" operator-surface "$@"
