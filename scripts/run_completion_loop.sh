#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$BASE_DIR/logs/automation"
mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/completion_loop_${STAMP}.log"

PYTHON_BIN="python3"
if [[ -x "$BASE_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$BASE_DIR/.venv/bin/python"
fi

if [[ -f "$BASE_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$BASE_DIR/.env"
  set +a
fi

COMPLETION_TARGET="${PERMANENCE_OPHTXN_COMPLETION_TARGET:-95}"
COMPLETION_STRICT="${PERMANENCE_OPHTXN_COMPLETION_STRICT:-0}"
RUN_GOVERNED_LEARNING="${PERMANENCE_COMPLETION_LOOP_RUN_GOVERNED_LEARNING:-1}"
GOVERNED_APPROVER="${PERMANENCE_COMPLETION_LOOP_APPROVER:-automation}"
GOVERNED_NOTE="${PERMANENCE_COMPLETION_LOOP_APPROVAL_NOTE:-scheduled completion loop}"

run_step() {
  local name="$1"
  shift
  echo "== ${name} ==" | tee -a "$LOG_FILE"
  if "$@" >>"$LOG_FILE" 2>&1; then
    echo "[ok] ${name}" | tee -a "$LOG_FILE"
  else
    local rc=$?
    echo "[warn] ${name} failed (status ${rc})" | tee -a "$LOG_FILE"
  fi
}

echo "Completion loop started (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$LOG_FILE"
echo "Repo: $BASE_DIR" | tee -a "$LOG_FILE"
echo "Python: $PYTHON_BIN" | tee -a "$LOG_FILE"

cd "$BASE_DIR"

if [[ "$RUN_GOVERNED_LEARNING" == "1" ]]; then
  run_step \
    "governed-learning" \
    "$PYTHON_BIN" cli.py governed-learning --action run --approved-by "$GOVERNED_APPROVER" --approval-note "$GOVERNED_NOTE"
else
  echo "[skip] governed-learning (PERMANENCE_COMPLETION_LOOP_RUN_GOVERNED_LEARNING=0)" | tee -a "$LOG_FILE"
fi

COMPLETION_ARGS=("$PYTHON_BIN" "cli.py" "ophtxn-completion" "--target" "$COMPLETION_TARGET")
if [[ "$COMPLETION_STRICT" == "1" ]]; then
  COMPLETION_ARGS+=("--strict")
fi
run_step "ophtxn-completion" "${COMPLETION_ARGS[@]}"

LATEST_COMPLETION="$(ls -t "$BASE_DIR"/outputs/ophtxn_completion_*.md 2>/dev/null | head -n 1 || true)"
if [[ -n "$LATEST_COMPLETION" ]]; then
  echo "Latest completion report: $LATEST_COMPLETION" | tee -a "$LOG_FILE"
fi

echo "Completion loop completed (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
