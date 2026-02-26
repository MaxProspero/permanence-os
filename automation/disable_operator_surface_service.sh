#!/usr/bin/env bash
set -euo pipefail

if [[ "$OSTYPE" == darwin* ]]; then
  PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.operator_surface.plist"
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  echo "Operator surface launchd service disabled."
  exit 0
fi

MARKER_BEGIN="# >>> permanence-operator-surface >>>"
MARKER_END="# <<< permanence-operator-surface <<<"
CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
NEW_CRON="$(printf "%s\n" "$CURRENT_CRON" | awk -v b="$MARKER_BEGIN" -v e="$MARKER_END" '
  $0 == b {inblk=1; next}
  $0 == e {inblk=0; next}
  !inblk {print}
')"

if [[ -n "$NEW_CRON" ]]; then
  printf "%s\n" "$NEW_CRON" | crontab -
else
  crontab -r 2>/dev/null || true
fi

echo "Operator surface reboot service disabled."
