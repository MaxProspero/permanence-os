#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$BASE_DIR/logs/automation"
mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/telegram_chat_loop_${STAMP}.log"

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
  PYTHON_BIN="$(command -v python3)"
fi

if [[ -f "$BASE_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$BASE_DIR/.env"
  set +a
fi

TELEGRAM_CHAT_LIMIT="${PERMANENCE_TELEGRAM_CHAT_LOOP_LIMIT:-20}"
TELEGRAM_CHAT_SKIP_MEDIA="${PERMANENCE_TELEGRAM_CHAT_LOOP_SKIP_MEDIA:-1}"
TELEGRAM_CHAT_ENABLE_COMMANDS="${PERMANENCE_TELEGRAM_CHAT_LOOP_ENABLE_COMMANDS:-1}"
TELEGRAM_CHAT_AGENT="${PERMANENCE_TELEGRAM_CHAT_LOOP_CHAT_AGENT:-${PERMANENCE_TELEGRAM_CONTROL_CHAT_AGENT_ENABLED:-0}}"
TELEGRAM_CHAT_MAX_REPLIES="${PERMANENCE_TELEGRAM_CHAT_LOOP_MAX_REPLIES:-8}"
TELEGRAM_CHAT_MAX_COMMANDS="${PERMANENCE_TELEGRAM_CHAT_LOOP_MAX_COMMANDS:-5}"
TELEGRAM_CHAT_SCOPE="${PERMANENCE_TELEGRAM_CHAT_LOOP_CHAT_IDS:-${PERMANENCE_TELEGRAM_CONTROL_TARGET_CHAT_IDS:-${PERMANENCE_TELEGRAM_CHAT_IDS:-${PERMANENCE_TELEGRAM_CHAT_ID:-}}}}"
TELEGRAM_CHAT_BRAIN_SYNC="${PERMANENCE_TELEGRAM_CHAT_LOOP_BRAIN_SYNC:-1}"
TELEGRAM_CHAT_BRAIN_SYNC_MIN_AGE="${PERMANENCE_TELEGRAM_CHAT_LOOP_BRAIN_SYNC_MIN_AGE_SECONDS:-900}"
BRAIN_VAULT_PATH="${PERMANENCE_OPHTXN_BRAIN_PATH:-$BASE_DIR/memory/working/ophtxn_brain_vault.json}"

_file_mtime_epoch() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    return 1
  fi
  if stat -f %m "$path" >/dev/null 2>&1; then
    stat -f %m "$path"
    return 0
  fi
  if stat -c %Y "$path" >/dev/null 2>&1; then
    stat -c %Y "$path"
    return 0
  fi
  return 1
}

echo "Telegram chat loop started (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$LOG_FILE"
echo "Repo: $BASE_DIR" | tee -a "$LOG_FILE"
echo "Python: $PYTHON_BIN" | tee -a "$LOG_FILE"

cd "$BASE_DIR"

if [[ "$TELEGRAM_CHAT_BRAIN_SYNC" == "1" ]]; then
  NEED_BRAIN_SYNC="1"
  NOW_EPOCH="$(date +%s)"
  VAULT_MTIME="$(_file_mtime_epoch "$BRAIN_VAULT_PATH" || true)"
  if [[ -n "$VAULT_MTIME" ]]; then
    VAULT_AGE=$((NOW_EPOCH - VAULT_MTIME))
    if [[ "$VAULT_AGE" -lt "$TELEGRAM_CHAT_BRAIN_SYNC_MIN_AGE" ]]; then
      NEED_BRAIN_SYNC="0"
      echo "[skip] ophtxn-brain sync (age ${VAULT_AGE}s < threshold ${TELEGRAM_CHAT_BRAIN_SYNC_MIN_AGE}s)" | tee -a "$LOG_FILE"
    fi
  fi
  if [[ "$NEED_BRAIN_SYNC" == "1" ]]; then
    if "$PYTHON_BIN" "cli.py" "ophtxn-brain" "--action" "sync" >>"$LOG_FILE" 2>&1; then
      echo "[ok] ophtxn-brain sync" | tee -a "$LOG_FILE"
    else
      rc=$?
      echo "[warn] ophtxn-brain sync failed (status $rc)" | tee -a "$LOG_FILE"
    fi
  fi
fi

ARGS=(
  "$PYTHON_BIN" "cli.py" "telegram-control"
  "--action" "poll"
  "--limit" "$TELEGRAM_CHAT_LIMIT"
  "--max-chat-replies" "$TELEGRAM_CHAT_MAX_REPLIES"
  "--max-commands" "$TELEGRAM_CHAT_MAX_COMMANDS"
)
if [[ -n "$TELEGRAM_CHAT_SCOPE" ]]; then
  ARGS+=("--chat-id=$TELEGRAM_CHAT_SCOPE")
fi

if [[ "$TELEGRAM_CHAT_SKIP_MEDIA" == "1" ]]; then
  ARGS+=("--skip-media")
fi
if [[ "$TELEGRAM_CHAT_ENABLE_COMMANDS" == "1" ]]; then
  ARGS+=("--enable-commands")
fi
if [[ "$TELEGRAM_CHAT_AGENT" == "1" ]]; then
  ARGS+=("--chat-agent")
fi

if "${ARGS[@]}" >>"$LOG_FILE" 2>&1; then
  echo "[ok] telegram-control poll" | tee -a "$LOG_FILE"
else
  rc=$?
  echo "[warn] telegram-control poll failed (status $rc)" | tee -a "$LOG_FILE"
fi

LATEST_TELEGRAM="$(ls -t "$BASE_DIR"/outputs/telegram_control_*.md 2>/dev/null | head -n 1 || true)"
if [[ -n "$LATEST_TELEGRAM" ]]; then
  echo "Latest telegram-control: $LATEST_TELEGRAM" | tee -a "$LOG_FILE"
fi

echo "Telegram chat loop completed (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
