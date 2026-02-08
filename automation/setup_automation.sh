#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_PATH/logs/automation"

mkdir -p "$LOG_DIR"

if [[ "$OSTYPE" != darwin* ]]; then
  echo "setup_automation.sh configures macOS launchd only."
  echo "Use automation/setup_dell_automation.sh on Linux."
  exit 1
fi

PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.briefing.plist"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.permanence.briefing</string>
    <key>ProgramArguments</key>
    <array>
        <string>$REPO_PATH/automation/run_briefing.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>0</integer></dict>
    </array>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/briefing.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/briefing.error.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

echo "Automation configured."
echo "Logs: $LOG_DIR"
python "$REPO_PATH/cli.py" automation-verify || true
