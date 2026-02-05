#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="/Users/paytonhicks/Documents/Permanence OS/permanence-os"
LOG_DIR="$REPO_PATH/logs/automation"

mkdir -p "$LOG_DIR"

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
