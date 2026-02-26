#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG_DIR="$REPO_PATH/logs/automation"
mkdir -p "$LOG_DIR"

if [[ ! -d "$REPO_PATH" ]]; then
  echo "Repo path not found: $REPO_PATH"
  exit 1
fi

echo "Configuring money-loop schedule..."
bash "$REPO_PATH/automation/setup_money_loop_automation.sh" "$REPO_PATH"

if [[ "$OSTYPE" == darwin* ]]; then
  PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.revenue_ops_maintenance.plist"
  cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.permanence.revenue_ops_maintenance</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO_PATH/automation/run_revenue_ops_maintenance.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>20</integer>
    <key>Minute</key><integer>30</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/revenue_ops_maintenance.launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/revenue_ops_maintenance.launchd.error.log</string>
</dict>
</plist>
EOF

  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl load "$PLIST_PATH"
  echo "Revenue ops maintenance launchd automation configured."
  echo "Plist: $PLIST_PATH"
  echo "Logs: $LOG_DIR"
  exit 0
fi

MARKER_BEGIN="# >>> permanence-revenue-maintenance >>>"
MARKER_END="# <<< permanence-revenue-maintenance <<<"
RUN_CMD="cd \"$REPO_PATH\" && /usr/bin/env bash automation/run_revenue_ops_maintenance.sh >> \"$LOG_DIR/cron_revenue_ops_maintenance.log\" 2>&1"
CRON_BLOCK="$MARKER_BEGIN
30 20 * * * $RUN_CMD
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
echo "Revenue ops maintenance cron automation configured."
echo "Repo: $REPO_PATH"
echo "Logs: $LOG_DIR"
