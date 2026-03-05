#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
HOOK_PATH="$REPO_PATH/.git/hooks/pre-push"

if [[ -f "$HOOK_PATH" ]] && grep -q "cli.py secret-scan" "$HOOK_PATH"; then
  rm -f "$HOOK_PATH"
  echo "Secret scan pre-push hook removed."
  exit 0
fi

echo "No managed secret scan pre-push hook found."
