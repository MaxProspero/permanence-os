#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG_DIR="$REPO_PATH/logs/automation"
mkdir -p "$LOG_DIR"

if [[ "$OSTYPE" == darwin* ]]; then
  PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.completion_loop.plist"
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  echo "Completion loop launchd automation disabled."
  echo "Removed: $PLIST_PATH"
  exit 0
fi

MARKER_BEGIN="# >>> permanence-completion-loop >>>"
MARKER_END="# <<< permanence-completion-loop <<<"

CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
if [[ -z "$CURRENT_CRON" ]]; then
  echo "No crontab entries found."
  exit 0
fi

CLEAN_CRON="$(printf "%s\n" "$CURRENT_CRON" | awk -v b="$MARKER_BEGIN" -v e="$MARKER_END" '
  $0 == b {inblk=1; next}
  $0 == e {inblk=0; next}
  !inblk {print}
')"

if [[ -n "$CLEAN_CRON" ]]; then
  printf "%s\n" "$CLEAN_CRON" | crontab -
else
  crontab -r || true
fi

echo "Completion loop cron automation disabled."
echo "Logs: $LOG_DIR"
