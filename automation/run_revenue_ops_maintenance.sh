#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_PATH/logs/automation"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/revenue_ops_maintenance_${STAMP}.log"

PYTHON_BIN="$REPO_PATH/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

run_step() {
  local name="$1"
  shift
  echo "== ${name} ==" | tee -a "$LOG_FILE"
  if "$@" >>"$LOG_FILE" 2>&1; then
    echo "[ok] ${name}" | tee -a "$LOG_FILE"
  else
    local step_status=$?
    echo "[warn] ${name} failed (status ${step_status})" | tee -a "$LOG_FILE"
  fi
}

echo "Revenue ops maintenance started (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$LOG_FILE"
cd "$REPO_PATH"
run_step "integration-readiness" "$PYTHON_BIN" cli.py integration-readiness
run_step "revenue-eval" "$PYTHON_BIN" cli.py revenue-eval
run_step "revenue-weekly-summary" "$PYTHON_BIN" cli.py revenue-weekly-summary
run_step "revenue-backup" "$PYTHON_BIN" cli.py revenue-backup
echo "Revenue ops maintenance completed (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE"
