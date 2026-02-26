#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

if [[ "$OSTYPE" == darwin* ]]; then
  PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.revenue_ops_maintenance.plist"
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  echo "Revenue ops maintenance launchd automation disabled."
  exit 0
fi

MARKER_BEGIN="# >>> permanence-revenue-maintenance >>>"
MARKER_END="# <<< permanence-revenue-maintenance <<<"
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

echo "Revenue ops maintenance cron automation disabled."
echo "Repo: $REPO_PATH"
