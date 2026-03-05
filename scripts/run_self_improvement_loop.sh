#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$BASE_DIR/logs/automation"
mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/self_improvement_loop_${STAMP}.log"

if [[ -f "$BASE_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$BASE_DIR/.env"
  set +a
fi

PYTHON_BIN="$(command -v python3)"
SEND_TELEGRAM="${PERMANENCE_SELF_IMPROVEMENT_AUTO_SEND:-1}"

echo "Self-improvement loop started (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$LOG_FILE"
echo "Repo: $BASE_DIR" | tee -a "$LOG_FILE"
echo "Python: $PYTHON_BIN" | tee -a "$LOG_FILE"

cd "$BASE_DIR"

ARGS=(
  "$PYTHON_BIN" "cli.py" "self-improvement"
  "--action" "pitch"
)

if [[ "$SEND_TELEGRAM" == "1" ]]; then
  ARGS+=("--send-telegram")
fi

if "${ARGS[@]}" >>"$LOG_FILE" 2>&1; then
  echo "[ok] self-improvement pitch run" | tee -a "$LOG_FILE"
else
  rc=$?
  echo "[warn] self-improvement pitch failed (status $rc)" | tee -a "$LOG_FILE"
fi

LATEST_REPORT="$(ls -t "$BASE_DIR"/outputs/self_improvement_*.md 2>/dev/null | head -n 1 || true)"
if [[ -n "$LATEST_REPORT" ]]; then
  echo "Latest self-improvement report: $LATEST_REPORT" | tee -a "$LOG_FILE"
fi

echo "Self-improvement loop completed (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
