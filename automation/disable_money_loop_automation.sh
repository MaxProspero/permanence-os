#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

if [[ "$OSTYPE" == darwin* ]]; then
  PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.money_loop.plist"
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  echo "Money loop launchd automation removed."
  exit 0
fi

MARKER_BEGIN="# >>> permanence-money-loop >>>"
MARKER_END="# <<< permanence-money-loop <<<"

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

echo "Money loop cron automation block removed."
echo "Repo: $REPO_PATH"
