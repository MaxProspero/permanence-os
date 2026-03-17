#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_PATH/logs/automation"

mkdir -p "$LOG_DIR"

if [[ "$OSTYPE" != darwin* ]]; then
  echo "setup_revenue_intelligence_automation.sh configures macOS launchd only."
  exit 1
fi

PLIST_PATH="$HOME/Library/LaunchAgents/com.permanence.revenue-intelligence.plist"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.permanence.revenue-intelligence</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd "$REPO_PATH" && python3 scripts/x_bookmark_ingest.py --action pull; python3 scripts/x_bookmark_analyzer.py --action analyze; python3 scripts/idea_intake.py --action process --queue-approvals; python3 scripts/opportunity_ranker.py; python3 scripts/revenue_intelligence.py --action run</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/revenue_intelligence.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/revenue_intelligence.error.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

echo "Revenue intelligence automation configured (weekly Monday 09:00)."
echo "Logs: $LOG_DIR"
