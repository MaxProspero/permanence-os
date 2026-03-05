#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG_DIR="$REPO_PATH/logs/automation"

if [[ "$OSTYPE" == darwin* ]]; then
  PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.self_improvement_loop.plist"
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  if [[ -f "$PLIST_PATH" ]]; then
    rm -f "$PLIST_PATH"
  fi
  echo "Self-improvement launchd automation disabled."
  echo "Plist removed: $PLIST_PATH"
  exit 0
fi

MARKER_BEGIN="# >>> permanence-self-improvement-loop >>>"
MARKER_END="# <<< permanence-self-improvement-loop <<<"
CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
NEW_CRON="$(printf "%s\n" "$CURRENT_CRON" | awk -v b="$MARKER_BEGIN" -v e="$MARKER_END" '
  $0 == b {inblk=1; next}
  $0 == e {inblk=0; next}
  !inblk {print}
')"

if [[ -n "$NEW_CRON" ]]; then
  printf "%s\n" "$NEW_CRON" | crontab -
else
  crontab -r >/dev/null 2>&1 || true
fi

echo "Self-improvement cron automation disabled."
echo "Logs retained in: $LOG_DIR"
