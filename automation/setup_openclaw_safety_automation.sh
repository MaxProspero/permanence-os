#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_PATH/logs/automation"

mkdir -p "$LOG_DIR"

if [[ "$OSTYPE" != darwin* ]]; then
  echo "setup_openclaw_safety_automation.sh configures macOS launchd only."
  exit 1
fi

PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.openclaw-safety.plist"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.permanence.openclaw-safety</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd "$REPO_PATH" && python3 scripts/openclaw_safety_audit.py --action run</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/openclaw_safety_audit.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/openclaw_safety_audit.error.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

echo "OpenClaw safety audit automation configured (weekly Sunday 03:00)."
echo "Logs: $LOG_DIR"
