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

PYTHON_BIN=""
if [[ -x "$REPO_PATH/.venv/bin/python" ]]; then
  PYTHON_BIN="$REPO_PATH/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "[ERROR] No python interpreter found (checked .venv/bin/python, python, python3)." >> "$LOG_FILE"
  exit 127
fi

normalize_int() {
  local raw="$1"
  if [[ ! "$raw" =~ ^[0-9]+$ ]]; then
    return 1
  fi
  echo "$((10#$raw))"
}

# If the configured storage root is not writable in this launch context, fall back.
if [[ -n "${PERMANENCE_STORAGE_ROOT:-}" ]]; then
  TARGET_ROOT="$PERMANENCE_STORAGE_ROOT"
  PROBE_FILE="$TARGET_ROOT/outputs/briefings/.permanence_probe"
  TARGET_READY=1
  if [[ -e "$TARGET_ROOT" ]] && [[ ! -w "$TARGET_ROOT" ]]; then
    TARGET_READY=0
  fi
  if [[ ! -e "$TARGET_ROOT" ]]; then
    TARGET_PARENT="$(dirname "$TARGET_ROOT")"
    if [[ ! -w "$TARGET_PARENT" ]]; then
      TARGET_READY=0
    fi
  fi

  if [[ "$TARGET_READY" -eq 1 ]] \
    && mkdir -p "$TARGET_ROOT/outputs/briefings" "$TARGET_ROOT/outputs/digests" >> "$LOG_FILE" 2>&1 \
    && ( : > "$PROBE_FILE" ) >> "$LOG_FILE" 2>&1; then
    rm -f "$PROBE_FILE" >> "$LOG_FILE" 2>&1 || true
  else
    FALLBACK_ROOT="$REPO_PATH/permanence_storage"
    mkdir -p "$FALLBACK_ROOT"
    export PERMANENCE_STORAGE_ROOT="$FALLBACK_ROOT"
    echo "[WARN] Storage root not writable in automation context. Falling back to $FALLBACK_ROOT" >> "$LOG_FILE"
  fi
fi

# Do not exit early; capture every status for reliability accounting.
set +e
"$PYTHON_BIN" cli.py briefing >> "$LOG_FILE" 2>&1
BRIEFING_STATUS=$?

"$PYTHON_BIN" cli.py sources-digest >> "$LOG_FILE" 2>&1
DIGEST_STATUS=$?

NOTEBOOKLM_STATUS=0
CURRENT_HOUR="$(normalize_int "$(date +%H)" || echo -1)"
NOTEBOOKLM_SYNC_SLOT="${PERMANENCE_NOTEBOOKLM_SYNC_SLOT:-19}"
if [[ "${PERMANENCE_NOTEBOOKLM_SYNC:-0}" == "1" ]]; then
  NOTEBOOKLM_SLOT_MATCH=0
  if [[ "$NOTEBOOKLM_SYNC_SLOT" == "all" ]]; then
    NOTEBOOKLM_SLOT_MATCH=1
  else
    NOTEBOOKLM_SLOT_NUM="$(normalize_int "$NOTEBOOKLM_SYNC_SLOT" || echo -1)"
    if [[ "$NOTEBOOKLM_SLOT_NUM" -ge 0 ]] && [[ "$CURRENT_HOUR" -eq "$NOTEBOOKLM_SLOT_NUM" ]]; then
      NOTEBOOKLM_SLOT_MATCH=1
    fi
  fi
  if [[ "$NOTEBOOKLM_SLOT_MATCH" -eq 1 ]]; then
    "$PYTHON_BIN" cli.py notebooklm-sync >> "$LOG_FILE" 2>&1 || NOTEBOOKLM_STATUS=$?
  fi
fi

RECEPTIONIST_NAME="${PERMANENCE_RECEPTIONIST_NAME:-Ari}"
RECEPTIONIST_STATUS=0
RECEPTIONIST_SLOT="${PERMANENCE_RECEPTIONIST_SLOT:-${PERMANENCE_ARI_SLOT:-19}}"
RECEPTIONIST_ENABLED="${PERMANENCE_RECEPTIONIST_ENABLED:-${PERMANENCE_ARI_ENABLED:-0}}"
RECEPTIONIST_COMMAND="${PERMANENCE_RECEPTIONIST_COMMAND:-ari-reception}"
if [[ "$RECEPTIONIST_ENABLED" == "1" ]]; then
  RECEPTIONIST_SLOT_MATCH=0
  if [[ "$RECEPTIONIST_SLOT" == "all" ]]; then
    RECEPTIONIST_SLOT_MATCH=1
  else
    RECEPTIONIST_SLOT_NUM="$(normalize_int "$RECEPTIONIST_SLOT" || echo -1)"
    if [[ "$RECEPTIONIST_SLOT_NUM" -ge 0 ]] && [[ "$CURRENT_HOUR" -eq "$RECEPTIONIST_SLOT_NUM" ]]; then
      RECEPTIONIST_SLOT_MATCH=1
    fi
  fi
  if [[ "$RECEPTIONIST_SLOT_MATCH" -eq 1 ]]; then
    case "$RECEPTIONIST_COMMAND" in
      ari-reception|sandra-reception)
        "$PYTHON_BIN" cli.py "$RECEPTIONIST_COMMAND" --action summary >> "$LOG_FILE" 2>&1 || RECEPTIONIST_STATUS=$?
        ;;
      *)
        echo "[WARN] Unsupported receptionist command '$RECEPTIONIST_COMMAND'; falling back to ari-reception." >> "$LOG_FILE"
        "$PYTHON_BIN" cli.py ari-reception --action summary >> "$LOG_FILE" 2>&1 || RECEPTIONIST_STATUS=$?
        ;;
    esac
  fi
fi

"$PYTHON_BIN" automation/healthcheck.py >> "$LOG_FILE" 2>&1
HEALTH_STATUS=$?

"$PYTHON_BIN" cli.py automation-report --days 1 >> "$LOG_FILE" 2>&1
REPORT_STATUS=$?

CHRONICLE_CAPTURE_STATUS=0
CHRONICLE_REPORT_STATUS=0
CHRONICLE_PUBLISH_STATUS=0
if [[ "${PERMANENCE_CHRONICLE_AUTOPUBLISH:-1}" == "1" ]]; then
  "$PYTHON_BIN" cli.py chronicle-capture \
    --note "automation briefing run $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --tag automation \
    --tag briefing >> "$LOG_FILE" 2>&1 || CHRONICLE_CAPTURE_STATUS=$?

  "$PYTHON_BIN" cli.py chronicle-report --days "${PERMANENCE_CHRONICLE_DAYS:-365}" >> "$LOG_FILE" 2>&1 || CHRONICLE_REPORT_STATUS=$?

  if [[ -n "${PERMANENCE_CHRONICLE_DRIVE_DIR:-}" ]]; then
    "$PYTHON_BIN" cli.py chronicle-publish --docx --drive-dir "$PERMANENCE_CHRONICLE_DRIVE_DIR" >> "$LOG_FILE" 2>&1 || CHRONICLE_PUBLISH_STATUS=$?
    if [[ "$CHRONICLE_PUBLISH_STATUS" -ne 0 ]]; then
      echo "[WARN] Chronicle Drive publish failed (status $CHRONICLE_PUBLISH_STATUS). Retrying local publish only." >> "$LOG_FILE"
      CHRONICLE_PUBLISH_STATUS=0
      env -u PERMANENCE_CHRONICLE_DRIVE_DIR "$PYTHON_BIN" cli.py chronicle-publish --docx >> "$LOG_FILE" 2>&1 || CHRONICLE_PUBLISH_STATUS=$?
    fi
  else
    "$PYTHON_BIN" cli.py chronicle-publish --docx >> "$LOG_FILE" 2>&1 || CHRONICLE_PUBLISH_STATUS=$?
  fi
fi

DAILY_GATE_STATUS=2
STREAK_STATUS=0
if [[ "$CURRENT_HOUR" -ge 19 ]]; then
  "$PYTHON_BIN" cli.py reliability-gate --days 1 --include-today >> "$LOG_FILE" 2>&1
  DAILY_GATE_STATUS=$?
  "$PYTHON_BIN" cli.py reliability-streak --update --status "$DAILY_GATE_STATUS" --date "$(date +%F)" >> "$LOG_FILE" 2>&1 || STREAK_STATUS=$?
fi

WEEKLY_PHASE_GATE_STATUS=2
PHASE_GATE_DOW="${PERMANENCE_PHASE_GATE_DOW:-7}"  # 1=Mon ... 7=Sun
CURRENT_DOW="$(date +%u)"
if [[ "$CURRENT_HOUR" -ge 19 && "$CURRENT_DOW" -eq "$PHASE_GATE_DOW" ]]; then
  "$PYTHON_BIN" cli.py phase-gate --days 7 >> "$LOG_FILE" 2>&1
  WEEKLY_PHASE_GATE_STATUS=$?
fi

PROMOTION_DAILY_STATUS=2
PROMOTION_DAILY_ENABLED="${PERMANENCE_PROMOTION_DAILY_ENABLED:-1}"
PROMOTION_DAILY_SLOT="${PERMANENCE_PROMOTION_DAILY_SLOT:-19}"
PROMOTION_DAILY_STRICT="${PERMANENCE_PROMOTION_DAILY_STRICT:-0}"
PROMOTION_DAILY_SINCE_HOURS="${PERMANENCE_PROMOTION_DAILY_SINCE_HOURS:-24}"
PROMOTION_DAILY_MAX_ADD="${PERMANENCE_PROMOTION_DAILY_MAX_ADD:-5}"
if [[ "$PROMOTION_DAILY_ENABLED" == "1" ]]; then
  PROMOTION_DAILY_SLOT_MATCH=0
  if [[ "$PROMOTION_DAILY_SLOT" == "all" ]]; then
    PROMOTION_DAILY_SLOT_MATCH=1
  else
    PROMOTION_DAILY_SLOT_NUM="$(normalize_int "$PROMOTION_DAILY_SLOT" || echo -1)"
    if [[ "$PROMOTION_DAILY_SLOT_NUM" -ge 0 ]] && [[ "$CURRENT_HOUR" -eq "$PROMOTION_DAILY_SLOT_NUM" ]]; then
      PROMOTION_DAILY_SLOT_MATCH=1
    fi
  fi
  if [[ "$PROMOTION_DAILY_SLOT_MATCH" -eq 1 ]]; then
    PROMOTION_DAILY_CMD=(
      "$PYTHON_BIN" cli.py promotion-daily
      --since-hours "$PROMOTION_DAILY_SINCE_HOURS"
      --max-add "$PROMOTION_DAILY_MAX_ADD"
    )
    if [[ "$PROMOTION_DAILY_STRICT" == "1" ]]; then
      PROMOTION_DAILY_CMD+=(--strict-gates)
    fi
    "${PROMOTION_DAILY_CMD[@]}" >> "$LOG_FILE" 2>&1 || PROMOTION_DAILY_STATUS=$?
  fi
fi
set -e

echo "=== Briefing Run Completed: $(date) ===" >> "$LOG_FILE"
echo "Briefing Status: $BRIEFING_STATUS | Digest Status: $DIGEST_STATUS | NotebookLM Status: $NOTEBOOKLM_STATUS" >> "$LOG_FILE"
echo "${RECEPTIONIST_NAME} Status: $RECEPTIONIST_STATUS" >> "$LOG_FILE"
echo "Health Status: $HEALTH_STATUS | Report Status: $REPORT_STATUS" >> "$LOG_FILE"
if [[ "${PERMANENCE_CHRONICLE_AUTOPUBLISH:-1}" == "1" ]]; then
  echo "Chronicle Capture: $CHRONICLE_CAPTURE_STATUS | Chronicle Report: $CHRONICLE_REPORT_STATUS | Chronicle Publish: $CHRONICLE_PUBLISH_STATUS" >> "$LOG_FILE"
fi
if [[ "$DAILY_GATE_STATUS" -ne 2 ]]; then
  echo "Daily Gate Status: $DAILY_GATE_STATUS | Streak Status: $STREAK_STATUS" >> "$LOG_FILE"
fi
if [[ "$WEEKLY_PHASE_GATE_STATUS" -ne 2 ]]; then
  echo "Weekly Phase Gate Status: $WEEKLY_PHASE_GATE_STATUS" >> "$LOG_FILE"
fi
if [[ "$PROMOTION_DAILY_STATUS" -ne 2 ]]; then
  echo "Promotion Daily Status: $PROMOTION_DAILY_STATUS" >> "$LOG_FILE"
fi

GLANCE_STATUS=0
"$PYTHON_BIN" cli.py status-glance >> "$LOG_FILE" 2>&1 || GLANCE_STATUS=$?
echo "Glance Status: $GLANCE_STATUS" >> "$LOG_FILE"

V04_SNAPSHOT_STATUS=0
"$PYTHON_BIN" cli.py v04-snapshot >> "$LOG_FILE" 2>&1 || V04_SNAPSHOT_STATUS=$?
echo "V04 Snapshot Status: $V04_SNAPSHOT_STATUS" >> "$LOG_FILE"

if [ $BRIEFING_STATUS -ne 0 ] || [ $DIGEST_STATUS -ne 0 ] || [ $CHRONICLE_CAPTURE_STATUS -ne 0 ] || [ $CHRONICLE_REPORT_STATUS -ne 0 ] || [ $CHRONICLE_PUBLISH_STATUS -ne 0 ] || { [ $PROMOTION_DAILY_STATUS -ne 0 ] && [ $PROMOTION_DAILY_STATUS -ne 2 ]; }; then
  exit 1
fi
