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
  PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.comms_digest.plist"
  cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.permanence.comms_digest</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>$REPO_PATH/cli.py</string>
    <string>comms-digest</string>
    <string>--send</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>21</integer>
    <key>Minute</key><integer>5</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/comms_digest.launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/comms_digest.launchd.error.log</string>
</dict>
</plist>
EOF

  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl load "$PLIST_PATH"
  echo "Comms digest launchd automation configured."
  echo "Plist: $PLIST_PATH"
  echo "Logs: $LOG_DIR"
  exit 0
fi

MARKER_BEGIN="# >>> permanence-comms-digest >>>"
MARKER_END="# <<< permanence-comms-digest <<<"
RUN_CMD="cd \"$REPO_PATH\" && /usr/bin/env python3 cli.py comms-digest --send >> \"$LOG_DIR/cron_comms_digest.log\" 2>&1"
CRON_BLOCK="$MARKER_BEGIN
5 21 * * * $RUN_CMD
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
echo "Comms digest cron automation configured."
echo "Repo: $REPO_PATH"
echo "Logs: $LOG_DIR"
