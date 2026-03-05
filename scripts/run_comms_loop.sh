#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$BASE_DIR/logs/automation"
mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/comms_loop_${STAMP}.log"

_python_has_anthropic() {
  local bin="$1"
  if [[ -z "$bin" || ! -x "$bin" ]]; then
    return 1
  fi
  "$bin" - <<'PY' >/dev/null 2>&1
import anthropic
PY
}

PYTHON_BIN=""
if [[ -x "$BASE_DIR/.venv/bin/python" ]] && _python_has_anthropic "$BASE_DIR/.venv/bin/python"; then
  PYTHON_BIN="$BASE_DIR/.venv/bin/python"
elif _python_has_anthropic "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"; then
  PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
elif command -v python3 >/dev/null 2>&1 && _python_has_anthropic "$(command -v python3)"; then
  PYTHON_BIN="$(command -v python3)"
else
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "[error] python3 not found in PATH" | tee -a "$LOG_FILE"
    exit 1
  fi
  echo "[warn] Selected Python interpreter may not support chat-agent model calls (anthropic package missing)." | tee -a "$LOG_FILE"
fi

if [[ -f "$BASE_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$BASE_DIR/.env"
  set +a
fi

COMMS_TELEGRAM_ENABLED="${PERMANENCE_COMMS_LOOP_TELEGRAM_ENABLED:-1}"
COMMS_DISCORD_RELAY_ENABLED="${PERMANENCE_COMMS_LOOP_DISCORD_RELAY_ENABLED:-1}"
COMMS_GLASSES_ENABLED="${PERMANENCE_COMMS_LOOP_GLASSES_ENABLED:-1}"
COMMS_RESEARCH_PROCESS_ENABLED="${PERMANENCE_COMMS_LOOP_RESEARCH_PROCESS_ENABLED:-1}"
COMMS_STATUS_ENABLED="${PERMANENCE_COMMS_LOOP_STATUS_ENABLED:-1}"
COMMS_STACK_STATUS_ENABLED="${PERMANENCE_COMMS_LOOP_COMMS_STATUS_ENABLED:-1}"
COMMS_PLATFORM_WATCH_ENABLED="${PERMANENCE_COMMS_LOOP_PLATFORM_WATCH_ENABLED:-1}"
COMMS_PLATFORM_WATCH_STRICT="${PERMANENCE_COMMS_LOOP_PLATFORM_WATCH_STRICT:-0}"
COMMS_DIGEST_ENABLED="${PERMANENCE_COMMS_LOOP_DIGEST_ENABLED:-0}"
COMMS_DIGEST_SEND="${PERMANENCE_COMMS_LOOP_DIGEST_SEND:-0}"
COMMS_DOCTOR_ENABLED="${PERMANENCE_COMMS_LOOP_DOCTOR_ENABLED:-0}"
COMMS_DOCTOR_ALLOW_WARNINGS="${PERMANENCE_COMMS_LOOP_DOCTOR_ALLOW_WARNINGS:-1}"
COMMS_ESCALATION_DIGEST_ENABLED="${PERMANENCE_COMMS_LOOP_ESCALATION_DIGEST_ENABLED:-0}"
COMMS_ESCALATION_DIGEST_SEND="${PERMANENCE_COMMS_LOOP_ESCALATION_DIGEST_SEND:-0}"

COMMS_TELEGRAM_LIMIT="${PERMANENCE_COMMS_LOOP_TELEGRAM_LIMIT:-25}"
COMMS_DISCORD_MAX_PER_FEED="${PERMANENCE_COMMS_LOOP_DISCORD_MAX_PER_FEED:-20}"
COMMS_GLASSES_MAX_FILES="${PERMANENCE_COMMS_LOOP_GLASSES_MAX_FILES:-30}"
COMMS_TELEGRAM_SKIP_MEDIA="${PERMANENCE_COMMS_LOOP_TELEGRAM_SKIP_MEDIA:-1}"
COMMS_STATUS_REQUIRE_ESCALATION_DIGEST="${PERMANENCE_COMMS_LOOP_COMMS_STATUS_REQUIRE_ESCALATION_DIGEST:-0}"
COMMS_STATUS_LOG_STALE_MINUTES="${PERMANENCE_COMMS_LOOP_COMMS_STATUS_LOG_STALE_MINUTES:-20}"
COMMS_STATUS_COMPONENT_STALE_MINUTES="${PERMANENCE_COMMS_LOOP_COMMS_STATUS_COMPONENT_STALE_MINUTES:-120}"
COMMS_STATUS_ESCALATION_DIGEST_STALE_MINUTES="${PERMANENCE_COMMS_LOOP_COMMS_STATUS_ESCALATION_DIGEST_STALE_MINUTES:-720}"
COMMS_STATUS_ESCALATION_HOURS="${PERMANENCE_COMMS_LOOP_COMMS_STATUS_ESCALATION_HOURS:-24}"
COMMS_STATUS_ESCALATION_WARN_COUNT="${PERMANENCE_COMMS_LOOP_COMMS_STATUS_ESCALATION_WARN_COUNT:-6}"
COMMS_STATUS_VOICE_QUEUE_WARN_COUNT="${PERMANENCE_COMMS_LOOP_COMMS_STATUS_VOICE_QUEUE_WARN_COUNT:-12}"

run_step() {
  local name="$1"
  shift
  echo "== ${name} ==" | tee -a "$LOG_FILE"
  if "$@" >>"$LOG_FILE" 2>&1; then
    echo "[ok] ${name}" | tee -a "$LOG_FILE"
    return 0
  fi
  local rc=$?
  echo "[warn] ${name} failed (status ${rc})" | tee -a "$LOG_FILE"
  return 0
}

echo "Comms loop started (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$LOG_FILE"
echo "Repo: $BASE_DIR" | tee -a "$LOG_FILE"

cd "$BASE_DIR"

if [[ "$COMMS_TELEGRAM_ENABLED" == "1" ]]; then
  TELEGRAM_ARGS=("$PYTHON_BIN" "cli.py" "telegram-control" "--action" "poll" "--limit" "$COMMS_TELEGRAM_LIMIT")
  if [[ "$COMMS_TELEGRAM_SKIP_MEDIA" == "1" ]]; then
    TELEGRAM_ARGS+=("--skip-media")
  fi
  run_step "telegram-control" "${TELEGRAM_ARGS[@]}"
else
  echo "[skip] telegram-control (PERMANENCE_COMMS_LOOP_TELEGRAM_ENABLED=0)" | tee -a "$LOG_FILE"
fi

if [[ "$COMMS_DISCORD_RELAY_ENABLED" == "1" ]]; then
  run_step "discord-telegram-relay" "$PYTHON_BIN" "cli.py" "discord-telegram-relay" "--action" "run" "--max-per-feed" "$COMMS_DISCORD_MAX_PER_FEED"
else
  echo "[skip] discord-telegram-relay (PERMANENCE_COMMS_LOOP_DISCORD_RELAY_ENABLED=0)" | tee -a "$LOG_FILE"
fi

if [[ "$COMMS_GLASSES_ENABLED" == "1" ]]; then
  run_step "glasses-autopilot" "$PYTHON_BIN" "cli.py" "glasses-autopilot" "--action" "run" "--max-files" "$COMMS_GLASSES_MAX_FILES"
else
  echo "[skip] glasses-autopilot (PERMANENCE_COMMS_LOOP_GLASSES_ENABLED=0)" | tee -a "$LOG_FILE"
fi

if [[ "$COMMS_RESEARCH_PROCESS_ENABLED" == "1" ]]; then
  run_step "research-inbox-process" "$PYTHON_BIN" "cli.py" "research-inbox" "--action" "process"
else
  echo "[skip] research-inbox-process (PERMANENCE_COMMS_LOOP_RESEARCH_PROCESS_ENABLED=0)" | tee -a "$LOG_FILE"
fi

if [[ "$COMMS_STATUS_ENABLED" == "1" ]]; then
  run_step "status-glance" "$PYTHON_BIN" "cli.py" "status-glance"
  run_step "integration-readiness" "$PYTHON_BIN" "cli.py" "integration-readiness"
  if [[ "$COMMS_PLATFORM_WATCH_ENABLED" == "1" ]]; then
    PLATFORM_WATCH_ARGS=("$PYTHON_BIN" "cli.py" "platform-change-watch")
    if [[ "$COMMS_PLATFORM_WATCH_STRICT" == "1" ]]; then
      PLATFORM_WATCH_ARGS+=("--strict")
    fi
    run_step "platform-change-watch" "${PLATFORM_WATCH_ARGS[@]}"
  else
    echo "[skip] platform-change-watch (PERMANENCE_COMMS_LOOP_PLATFORM_WATCH_ENABLED=0)" | tee -a "$LOG_FILE"
  fi
  if [[ "$COMMS_STACK_STATUS_ENABLED" == "1" ]]; then
    COMMS_STATUS_ARGS=(
      "$PYTHON_BIN" "cli.py" "comms-status"
      "--comms-log-stale-minutes" "$COMMS_STATUS_LOG_STALE_MINUTES"
      "--component-stale-minutes" "$COMMS_STATUS_COMPONENT_STALE_MINUTES"
      "--escalation-digest-stale-minutes" "$COMMS_STATUS_ESCALATION_DIGEST_STALE_MINUTES"
      "--escalation-hours" "$COMMS_STATUS_ESCALATION_HOURS"
      "--escalation-warn-count" "$COMMS_STATUS_ESCALATION_WARN_COUNT"
      "--voice-queue-warn-count" "$COMMS_STATUS_VOICE_QUEUE_WARN_COUNT"
    )
    if [[ "$COMMS_STATUS_REQUIRE_ESCALATION_DIGEST" == "1" ]]; then
      COMMS_STATUS_ARGS+=("--require-escalation-digest")
    fi
    run_step "comms-status" "${COMMS_STATUS_ARGS[@]}"
  else
    echo "[skip] comms-status (PERMANENCE_COMMS_LOOP_COMMS_STATUS_ENABLED=0)" | tee -a "$LOG_FILE"
  fi
else
  echo "[skip] status integration snapshots (PERMANENCE_COMMS_LOOP_STATUS_ENABLED=0)" | tee -a "$LOG_FILE"
fi

if [[ "$COMMS_DIGEST_ENABLED" == "1" ]]; then
  DIGEST_ARGS=("$PYTHON_BIN" "cli.py" "comms-digest")
  if [[ "$COMMS_DIGEST_SEND" == "1" ]]; then
    DIGEST_ARGS+=("--send")
  fi
  run_step "comms-digest" "${DIGEST_ARGS[@]}"
else
  echo "[skip] comms-digest (PERMANENCE_COMMS_LOOP_DIGEST_ENABLED=0)" | tee -a "$LOG_FILE"
fi

if [[ "$COMMS_DOCTOR_ENABLED" == "1" ]]; then
  DOCTOR_ARGS=("$PYTHON_BIN" "cli.py" "comms-doctor")
  if [[ "$COMMS_DOCTOR_ALLOW_WARNINGS" == "1" ]]; then
    DOCTOR_ARGS+=("--allow-warnings")
  fi
  run_step "comms-doctor" "${DOCTOR_ARGS[@]}"
else
  echo "[skip] comms-doctor (PERMANENCE_COMMS_LOOP_DOCTOR_ENABLED=0)" | tee -a "$LOG_FILE"
fi

if [[ "$COMMS_ESCALATION_DIGEST_ENABLED" == "1" ]]; then
  ESCALATION_ARGS=("$PYTHON_BIN" "cli.py" "comms-escalation-digest")
  if [[ "$COMMS_ESCALATION_DIGEST_SEND" == "1" ]]; then
    ESCALATION_ARGS+=("--send")
  fi
  run_step "comms-escalation-digest" "${ESCALATION_ARGS[@]}"
else
  echo "[skip] comms-escalation-digest (PERMANENCE_COMMS_LOOP_ESCALATION_DIGEST_ENABLED=0)" | tee -a "$LOG_FILE"
fi

LATEST_RELAY="$(ls -t "$BASE_DIR"/outputs/discord_telegram_relay_*.md 2>/dev/null | head -n 1 || true)"
if [[ -n "$LATEST_RELAY" ]]; then
  echo "Latest relay: $LATEST_RELAY" | tee -a "$LOG_FILE"
fi
LATEST_TELEGRAM="$(ls -t "$BASE_DIR"/outputs/telegram_control_*.md 2>/dev/null | head -n 1 || true)"
if [[ -n "$LATEST_TELEGRAM" ]]; then
  echo "Latest telegram-control: $LATEST_TELEGRAM" | tee -a "$LOG_FILE"
fi
LATEST_GLASSES="$(ls -t "$BASE_DIR"/outputs/glasses_autopilot_*.md 2>/dev/null | head -n 1 || true)"
if [[ -n "$LATEST_GLASSES" ]]; then
  echo "Latest glasses-autopilot: $LATEST_GLASSES" | tee -a "$LOG_FILE"
fi

echo "Comms loop completed (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
