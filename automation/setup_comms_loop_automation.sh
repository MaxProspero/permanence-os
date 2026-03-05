#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG_DIR="$REPO_PATH/logs/automation"
mkdir -p "$LOG_DIR"

if [[ ! -d "$REPO_PATH" ]]; then
  echo "Repo path not found: $REPO_PATH"
  exit 1
fi

if [[ "$OSTYPE" == darwin* ]]; then
  PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.comms_loop.plist"
  cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.permanence.comms_loop</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO_PATH/scripts/run_comms_loop.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>300</integer>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/comms_loop.launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/comms_loop.launchd.error.log</string>
</dict>
</plist>
EOF

  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl load "$PLIST_PATH"
  echo "Comms loop launchd automation configured."
  echo "Plist: $PLIST_PATH"
  echo "Logs: $LOG_DIR"
  exit 0
fi

MARKER_BEGIN="# >>> permanence-comms-loop >>>"
MARKER_END="# <<< permanence-comms-loop <<<"
RUN_CMD="cd \"$REPO_PATH\" && /usr/bin/env bash scripts/run_comms_loop.sh >> \"$LOG_DIR/cron_comms_loop.log\" 2>&1"
CRON_BLOCK="$MARKER_BEGIN
*/5 * * * * $RUN_CMD
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
echo "Comms loop cron automation configured."
echo "Repo: $REPO_PATH"
echo "Logs: $LOG_DIR"
