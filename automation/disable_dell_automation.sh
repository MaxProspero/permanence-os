#!/usr/bin/env bash
set -euo pipefail

MARKER_BEGIN="# >>> permanence-automation >>>"
MARKER_END="# <<< permanence-automation <<<"

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

echo "Removed permanence automation cron block."
