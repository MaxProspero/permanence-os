#!/bin/zsh
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$BASE_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

LOG_DIR="$BASE_DIR/logs/automation"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/money_loop_${STAMP}.log"

GMAIL_INGEST_ENABLED="${PERMANENCE_MONEY_LOOP_GMAIL_INGEST:-1}"
GMAIL_MAX="${PERMANENCE_MONEY_LOOP_GMAIL_MAX:-100}"
GMAIL_QUERY="${PERMANENCE_MONEY_LOOP_GMAIL_QUERY:-newer_than:14d -category:social -category:promotions}"
GMAIL_CREDENTIALS="${PERMANENCE_GMAIL_CREDENTIALS:-$BASE_DIR/memory/working/google/credentials.json}"
GMAIL_TOKEN="${PERMANENCE_GMAIL_TOKEN:-$BASE_DIR/memory/working/google/token.json}"
TRIAGE_MAX_ITEMS="${PERMANENCE_MONEY_LOOP_TRIAGE_MAX_ITEMS:-40}"

run_step() {
  local name="$1"
  shift
  echo "== ${name} ==" | tee -a "$LOG_FILE"
  if "$@" >>"$LOG_FILE" 2>&1; then
    echo "[ok] ${name}" | tee -a "$LOG_FILE"
    return 0
  else
    local step_status=$?
    echo "[warn] ${name} failed (status ${step_status})" | tee -a "$LOG_FILE"
    return 0
  fi
}

echo "Money loop started (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$LOG_FILE"
echo "Repo: $BASE_DIR" | tee -a "$LOG_FILE"

cd "$BASE_DIR"

if [[ "$GMAIL_INGEST_ENABLED" == "1" ]]; then
  if [[ -f "$GMAIL_CREDENTIALS" && -f "$GMAIL_TOKEN" ]]; then
    if [[ -n "$GMAIL_QUERY" ]]; then
      run_step "gmail-ingest" "$PYTHON_BIN" cli.py gmail-ingest --max "$GMAIL_MAX" --query "$GMAIL_QUERY"
    else
      run_step "gmail-ingest" "$PYTHON_BIN" cli.py gmail-ingest --max "$GMAIL_MAX"
    fi
  elif [[ -f "$GMAIL_CREDENTIALS" ]]; then
    echo "[skip] gmail-ingest (missing token: $GMAIL_TOKEN; run manual gmail-ingest once to authorize)" | tee -a "$LOG_FILE"
  else
    echo "[skip] gmail-ingest (missing credentials: $GMAIL_CREDENTIALS)" | tee -a "$LOG_FILE"
  fi
else
  echo "[skip] gmail-ingest (disabled by PERMANENCE_MONEY_LOOP_GMAIL_INGEST=0)" | tee -a "$LOG_FILE"
fi

run_step "email-triage" "$PYTHON_BIN" cli.py email-triage --max-items "$TRIAGE_MAX_ITEMS"
run_step "social-summary" "$PYTHON_BIN" cli.py social-summary
run_step "health-summary" "$PYTHON_BIN" cli.py health-summary
run_step "briefing" "$PYTHON_BIN" cli.py briefing
run_step "dashboard" "$PYTHON_BIN" cli.py dashboard
run_step "status-glance" "$PYTHON_BIN" cli.py status-glance
run_step "revenue-action-queue" "$PYTHON_BIN" scripts/revenue_action_queue.py

LATEST_QUEUE="$(ls -t "$BASE_DIR"/outputs/revenue_action_queue_*.md 2>/dev/null | head -n 1 || true)"
if [[ -n "$LATEST_QUEUE" ]]; then
  echo "Latest revenue queue: $LATEST_QUEUE" | tee -a "$LOG_FILE"
fi
echo "Money loop completed (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE"
