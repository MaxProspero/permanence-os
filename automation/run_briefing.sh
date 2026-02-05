#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="/Users/paytonhicks/Documents/Permanence OS/permanence-os"
LOG_DIR="$REPO_PATH/logs/automation"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/run_${TIMESTAMP}.log"

mkdir -p "$LOG_DIR"

echo "=== Briefing Run Started: $(date) ===" >> "$LOG_FILE"

cd "$REPO_PATH"

python cli.py briefing >> "$LOG_FILE" 2>&1
BRIEFING_STATUS=$?

python cli.py sources-digest >> "$LOG_FILE" 2>&1
DIGEST_STATUS=$?

python automation/healthcheck.py >> "$LOG_FILE" 2>&1

echo "=== Briefing Run Completed: $(date) ===" >> "$LOG_FILE"
echo "Briefing Status: $BRIEFING_STATUS | Digest Status: $DIGEST_STATUS" >> "$LOG_FILE"

if [ $BRIEFING_STATUS -ne 0 ] || [ $DIGEST_STATUS -ne 0 ]; then
  exit 1
fi
