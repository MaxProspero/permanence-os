#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG_DIR="$REPO_PATH/logs/automation"
MARKER_BEGIN="# >>> permanence-automation >>>"
MARKER_END="# <<< permanence-automation <<<"

if [[ ! -d "$REPO_PATH" ]]; then
  echo "Repo path not found: $REPO_PATH"
  exit 1
fi

mkdir -p "$LOG_DIR"

if [[ "$OSTYPE" == darwin* ]]; then
  echo "Detected macOS. Use automation/setup_automation.sh instead."
  exit 1
fi

RUN_CMD="cd \"$REPO_PATH\" && /usr/bin/env bash automation/run_briefing.sh >> \"$LOG_DIR/cron.log\" 2>&1"
CRON_BLOCK="$MARKER_BEGIN
0 7 * * * $RUN_CMD
0 12 * * * $RUN_CMD
0 19 * * * $RUN_CMD
$MARKER_END"

CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
CLEAN_CRON="$(printf "%s\n" "$CURRENT_CRON" | awk -v b="$MARKER_BEGIN" -v e="$MARKER_END" '
  $0 == b {inblk=1; next}
  $0 == e {inblk=0; next}
  !inblk {print}
')"

if [[ -n "$CLEAN_CRON" ]]; then
  NEW_CRON="$CLEAN_CRON
$CRON_BLOCK"
else
  NEW_CRON="$CRON_BLOCK"
fi

printf "%s\n" "$NEW_CRON" | crontab -

echo "Dell cron automation configured."
echo "Repo: $REPO_PATH"
echo "Logs: $LOG_DIR"
echo
echo "Installed cron block:"
crontab -l | awk -v b="$MARKER_BEGIN" -v e="$MARKER_END" '
  $0 == b {show=1}
  show {print}
  $0 == e {show=0}
'
