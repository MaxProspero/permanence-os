#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_PATH/logs/automation"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/run_${TIMESTAMP}.log"

mkdir -p "$LOG_DIR"

echo "=== Briefing Run Started: $(date) ===" >> "$LOG_FILE"

cd "$REPO_PATH"
export PYTHONPATH="$REPO_PATH:${PYTHONPATH:-}"

if [ -f "$REPO_PATH/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$REPO_PATH/.env"
  set +a
fi

# If the configured storage root is not writable in this launch context, fall back.
if [[ -n "${PERMANENCE_STORAGE_ROOT:-}" ]]; then
  TARGET_ROOT="$PERMANENCE_STORAGE_ROOT"
  PROBE_FILE="$TARGET_ROOT/outputs/briefings/.permanence_probe"
  if ! mkdir -p "$TARGET_ROOT/outputs/briefings" "$TARGET_ROOT/outputs/digests" >> "$LOG_FILE" 2>&1 \
    || ! ( : > "$PROBE_FILE" ) >> "$LOG_FILE" 2>&1; then
    FALLBACK_ROOT="$REPO_PATH/permanence_storage"
    mkdir -p "$FALLBACK_ROOT"
    export PERMANENCE_STORAGE_ROOT="$FALLBACK_ROOT"
    echo "[WARN] Storage root not writable in automation context. Falling back to $FALLBACK_ROOT" >> "$LOG_FILE"
  else
    rm -f "$PROBE_FILE" >> "$LOG_FILE" 2>&1 || true
  fi
fi

# Do not exit early; capture every status for reliability accounting.
set +e
python cli.py briefing >> "$LOG_FILE" 2>&1
BRIEFING_STATUS=$?

python cli.py sources-digest >> "$LOG_FILE" 2>&1
DIGEST_STATUS=$?

NOTEBOOKLM_STATUS=0
CURRENT_HOUR="$(date +%H)"
NOTEBOOKLM_SYNC_SLOT="${PERMANENCE_NOTEBOOKLM_SYNC_SLOT:-19}"
if [[ "${PERMANENCE_NOTEBOOKLM_SYNC:-0}" == "1" ]]; then
  if [[ "$NOTEBOOKLM_SYNC_SLOT" == "all" ]] || [[ "$CURRENT_HOUR" -eq "$NOTEBOOKLM_SYNC_SLOT" ]]; then
    python cli.py notebooklm-sync >> "$LOG_FILE" 2>&1 || NOTEBOOKLM_STATUS=$?
  fi
fi

ARI_STATUS=0
ARI_SLOT="${PERMANENCE_ARI_SLOT:-19}"
if [[ "${PERMANENCE_ARI_ENABLED:-0}" == "1" ]]; then
  if [[ "$ARI_SLOT" == "all" ]] || [[ "$CURRENT_HOUR" -eq "$ARI_SLOT" ]]; then
    python cli.py ari-reception --action summary >> "$LOG_FILE" 2>&1 || ARI_STATUS=$?
  fi
fi

python automation/healthcheck.py >> "$LOG_FILE" 2>&1
HEALTH_STATUS=$?

python cli.py automation-report --days 1 >> "$LOG_FILE" 2>&1
REPORT_STATUS=$?

DAILY_GATE_STATUS=2
STREAK_STATUS=0
if [[ "$CURRENT_HOUR" -ge 19 ]]; then
  python cli.py reliability-gate --days 1 --include-today >> "$LOG_FILE" 2>&1
  DAILY_GATE_STATUS=$?
  python cli.py reliability-streak --update --status "$DAILY_GATE_STATUS" --date "$(date +%F)" >> "$LOG_FILE" 2>&1 || STREAK_STATUS=$?
fi

WEEKLY_PHASE_GATE_STATUS=2
PHASE_GATE_DOW="${PERMANENCE_PHASE_GATE_DOW:-7}"  # 1=Mon ... 7=Sun
CURRENT_DOW="$(date +%u)"
if [[ "$CURRENT_HOUR" -ge 19 && "$CURRENT_DOW" -eq "$PHASE_GATE_DOW" ]]; then
  python cli.py phase-gate --days 7 >> "$LOG_FILE" 2>&1
  WEEKLY_PHASE_GATE_STATUS=$?
fi
set -e

echo "=== Briefing Run Completed: $(date) ===" >> "$LOG_FILE"
echo "Briefing Status: $BRIEFING_STATUS | Digest Status: $DIGEST_STATUS | NotebookLM Status: $NOTEBOOKLM_STATUS" >> "$LOG_FILE"
echo "Ari Status: $ARI_STATUS" >> "$LOG_FILE"
echo "Health Status: $HEALTH_STATUS | Report Status: $REPORT_STATUS" >> "$LOG_FILE"
if [[ "$DAILY_GATE_STATUS" -ne 2 ]]; then
  echo "Daily Gate Status: $DAILY_GATE_STATUS | Streak Status: $STREAK_STATUS" >> "$LOG_FILE"
fi
if [[ "$WEEKLY_PHASE_GATE_STATUS" -ne 2 ]]; then
  echo "Weekly Phase Gate Status: $WEEKLY_PHASE_GATE_STATUS" >> "$LOG_FILE"
fi

GLANCE_STATUS=0
python cli.py status-glance >> "$LOG_FILE" 2>&1 || GLANCE_STATUS=$?
echo "Glance Status: $GLANCE_STATUS" >> "$LOG_FILE"

if [ $BRIEFING_STATUS -ne 0 ] || [ $DIGEST_STATUS -ne 0 ]; then
  exit 1
fi
