"""
PERMANENCE OS — DASHBOARD API
Local backend server. Connects the web dashboard to your agent system.
Run this locally: python dashboard_api.py
Then access: http://localhost:8000 or via your domain tunnel.

Security model:
  - Local only by default (127.0.0.1)
  - No external authentication in v0 (you own the machine)
  - All write actions (approve/reject) are logged with provenance
  - Read-only by default; mutation endpoints require explicit confirmation

Canon Alignment:
  - "No autonomy without audit" — every API call logged
  - "Human authority is final" — approval endpoints are the human's voice
  - "Logs are append-only" — all actions written to log, never overwritten
"""

from flask import Flask, jsonify, request, abort, send_from_directory
try:
    from flask_cors import CORS
except ModuleNotFoundError:
    CORS = None
import json
import os
import datetime
import hashlib
import glob
from typing import Optional

app = Flask(__name__)
if CORS is not None:
    CORS(app, origins=["http://localhost:3000", "http://localhost:5173", "https://permanencesystems.com"])

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.environ.get("PERMANENCE_BASE_DIR", APP_DIR)
PATHS = {
    "canon":    os.path.join(BASE_DIR, "canon"),
    "logs":     os.path.join(BASE_DIR, "logs"),
    "outputs":  os.path.join(BASE_DIR, "outputs"),
    "episodic": os.path.join(BASE_DIR, "memory", "episodic"),
    "horizon":  os.path.join(BASE_DIR, "outputs", "horizon"),
    "briefings":os.path.join(BASE_DIR, "outputs", "briefings"),
    "approvals":os.path.join(BASE_DIR, "memory", "approvals.json"),
    "api_log":  os.path.join(BASE_DIR, "logs", "dashboard_api.log"),
}

API_VERSION = "0.1.0"
DASHBOARD_FILE = "dashboard_index.html"
DASHBOARD_HOST = os.environ.get("PERMANENCE_DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.environ.get("PERMANENCE_DASHBOARD_PORT", "8000"))


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def utc_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def timestamp_to_utc_iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat().replace("+00:00", "Z")


# ─────────────────────────────────────────────
# AUDIT LOGGING
# ─────────────────────────────────────────────

def log_api_call(method: str, endpoint: str, payload: Optional[dict] = None, result: str = "OK"):
    """Every API call logged. Append-only."""
    entry = {
        "timestamp": utc_iso(),
        "method": method,
        "endpoint": endpoint,
        "payload": payload,
        "result": result,
    }
    os.makedirs(os.path.dirname(PATHS["api_log"]), exist_ok=True)
    with open(PATHS["api_log"], "a") as f:
        f.write(json.dumps(entry) + "\n")


# ─────────────────────────────────────────────
# SYSTEM STATUS
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def dashboard_home():
    """Serve dashboard UI from the same origin as the API."""
    dashboard_path = os.path.join(APP_DIR, DASHBOARD_FILE)
    if not os.path.exists(dashboard_path):
        abort(404, description=f"{DASHBOARD_FILE} not found next to dashboard_api.py")
    return send_from_directory(APP_DIR, DASHBOARD_FILE)

@app.route("/api/status", methods=["GET"])
def system_status():
    """
    Returns overall system health snapshot.
    Dashboard home screen reads from this.
    """
    log_api_call("GET", "/api/status")

    canon_version = _read_canon_version()
    pending_approvals = _count_pending_approvals()
    last_briefing = _get_last_briefing_time()
    test_stats = _get_test_stats()
    horizon_reports = _count_horizon_reports()

    return jsonify({
        "system": "Permanence OS",
        "api_version": API_VERSION,
        "timestamp": utc_iso(),
        "canon": {
            "version": canon_version,
            "path": PATHS["canon"],
            "status": "LOCKED",
        },
        "agents": {
            "polemarch": _agent_status("polemarch"),
            "researcher": _agent_status("researcher"),
            "planner": _agent_status("planner"),
            "executor": _agent_status("executor"),
            "reviewer": _agent_status("reviewer"),
            "horizon": _agent_status("horizon"),
        },
        "queue": {
            "pending_approvals": pending_approvals,
            "requires_attention": pending_approvals > 0,
        },
        "briefing": {
            "last_generated": last_briefing,
        },
        "tests": test_stats,
        "horizon": {
            "reports_generated": horizon_reports,
        },
    })


# ─────────────────────────────────────────────
# APPROVAL QUEUE (The Human's Command Center)
# ─────────────────────────────────────────────

@app.route("/api/approvals", methods=["GET"])
def get_approvals():
    """
    Returns all items awaiting human decision.
    This is the most important endpoint in the system.
    Every HIGH risk action lands here before execution.
    """
    log_api_call("GET", "/api/approvals")

    approvals = _load_approvals()
    pending = [a for a in approvals if a.get("status") == "PENDING_HUMAN_REVIEW"]

    return jsonify({
        "total_pending": len(pending),
        "approvals": pending,
        "timestamp": utc_iso(),
    })


@app.route("/api/approvals/<approval_id>/approve", methods=["POST"])
def approve_item(approval_id: str):
    """
    Human approves a pending action.
    This is the most consequential write endpoint in the system.
    Logs the decision with timestamp and any notes provided.
    """
    payload = request.get_json() or {}
    notes = payload.get("notes", "")

    log_api_call("POST", f"/api/approvals/{approval_id}/approve", payload)

    result = _update_approval_status(approval_id, "APPROVED", notes)
    if not result:
        log_api_call("POST", f"/api/approvals/{approval_id}/approve", payload, "NOT_FOUND")
        abort(404, description="Approval not found")

    return jsonify({
        "approval_id": approval_id,
        "status": "APPROVED",
        "decided_at": utc_iso(),
        "notes": notes,
        "message": "Decision logged. Polemarch will route for execution.",
    })


@app.route("/api/approvals/<approval_id>/reject", methods=["POST"])
def reject_item(approval_id: str):
    """
    Human rejects a pending action.
    Rejection reason is required — not optional.
    Rejected items stay in archive; never deleted.
    """
    payload = request.get_json() or {}
    reason = payload.get("reason", "")

    if not reason:
        log_api_call("POST", f"/api/approvals/{approval_id}/reject", payload, "MISSING_REASON")
        abort(400, description="Rejection reason is required.")

    log_api_call("POST", f"/api/approvals/{approval_id}/reject", payload)

    result = _update_approval_status(approval_id, "REJECTED", reason)
    if not result:
        log_api_call("POST", f"/api/approvals/{approval_id}/reject", payload, "NOT_FOUND")
        abort(404, description="Approval not found")

    return jsonify({
        "approval_id": approval_id,
        "status": "REJECTED",
        "decided_at": utc_iso(),
        "reason": reason,
        "message": "Decision logged. Item archived.",
    })


# ─────────────────────────────────────────────
# BRIEFINGS
# ─────────────────────────────────────────────

@app.route("/api/briefings", methods=["GET"])
def get_briefings():
    """Returns list of available briefings, newest first."""
    log_api_call("GET", "/api/briefings")

    briefings = _list_briefings()
    return jsonify({
        "count": len(briefings),
        "briefings": briefings,
    })


@app.route("/api/briefings/latest", methods=["GET"])
def get_latest_briefing():
    """Returns the most recent briefing content."""
    log_api_call("GET", "/api/briefings/latest")

    briefing = _load_latest_briefing()
    if not briefing:
        return jsonify({"error": "No briefings found"}), 404

    return jsonify(briefing)


# ─────────────────────────────────────────────
# HORIZON REPORTS
# ─────────────────────────────────────────────

@app.route("/api/horizon", methods=["GET"])
def get_horizon_reports():
    """Returns list of Horizon Agent elevation reports."""
    log_api_call("GET", "/api/horizon")

    reports = _list_horizon_reports()
    return jsonify({
        "count": len(reports),
        "reports": reports,
    })


@app.route("/api/horizon/latest", methods=["GET"])
def get_latest_horizon():
    """Returns the most recent Horizon Agent report."""
    log_api_call("GET", "/api/horizon/latest")

    report = _load_latest_horizon_report()
    if not report:
        return jsonify({"error": "No horizon reports found"}), 404

    return jsonify(report)


# ─────────────────────────────────────────────
# CANON VIEWER (Read-Only)
# ─────────────────────────────────────────────

@app.route("/api/canon", methods=["GET"])
def get_canon():
    """
    Returns Canon content for display.
    READ ONLY. The Canon cannot be modified through this API.
    Modifications require ceremony and direct file edit by human.
    """
    log_api_call("GET", "/api/canon")

    canon_files = _load_canon_files()
    return jsonify({
        "version": _read_canon_version(),
        "files": canon_files,
        "status": "READ_ONLY",
        "note": "Canon modifications require human ceremony. This API cannot write to Canon.",
    })


# ─────────────────────────────────────────────
# EPISODIC MEMORY
# ─────────────────────────────────────────────

@app.route("/api/memory/episodic", methods=["GET"])
def get_episodic_memory():
    """Returns recent episodic memory entries — the system's journal."""
    log_api_call("GET", "/api/memory/episodic")

    limit = request.args.get("limit", 20, type=int)
    entries = _load_episodic_memory(limit)

    return jsonify({
        "count": len(entries),
        "entries": entries,
    })


# ─────────────────────────────────────────────
# AUDIT LOGS
# ─────────────────────────────────────────────

@app.route("/api/logs", methods=["GET"])
def get_logs():
    """Returns recent audit log entries. Tail of the append-only log."""
    log_api_call("GET", "/api/logs")

    agent = request.args.get("agent", None)
    limit = request.args.get("limit", 50, type=int)
    entries = _load_log_entries(agent, limit)

    return jsonify({
        "count": len(entries),
        "entries": entries,
        "filter": {"agent": agent, "limit": limit},
    })


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────

def _read_canon_version() -> str:
    changelog = os.path.join(PATHS["canon"], "CHANGELOG.md")
    if os.path.exists(changelog):
        with open(changelog) as f:
            first_line = f.readline().strip()
            return first_line or "v0.1.0"
    return "v0.1.0"


def _count_pending_approvals() -> int:
    approvals = _load_approvals()
    return sum(1 for a in approvals if a.get("status") == "PENDING_HUMAN_REVIEW")


def _get_last_briefing_time() -> Optional[str]:
    files = sorted(glob.glob(os.path.join(PATHS["briefings"], "*.json")), reverse=True)
    if not files:
        return None
    return timestamp_to_utc_iso(os.path.getmtime(files[0]))


def _get_test_stats() -> dict:
    stats_path = os.path.join(BASE_DIR, "outputs", "test_stats.json")
    if os.path.exists(stats_path):
        with open(stats_path) as f:
            return json.load(f)
    return {"passing": 0, "failing": 0, "last_run": None}


def _count_horizon_reports() -> int:
    return len(glob.glob(os.path.join(PATHS["horizon"], "*.json")))


def _agent_status(agent_name: str) -> dict:
    """Check if an agent has logged activity recently."""
    log_file = os.path.join(PATHS["logs"], f"{agent_name}_agent.log")
    if not os.path.exists(log_file):
        return {"status": "NOT_YET_RUN", "last_active": None}

    last_active = timestamp_to_utc_iso(os.path.getmtime(log_file))
    return {"status": "ACTIVE", "last_active": last_active}


def _load_approvals() -> list:
    if not os.path.exists(PATHS["approvals"]):
        return []
    with open(PATHS["approvals"]) as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("approvals"), list):
                return data["approvals"]
            return []
        except json.JSONDecodeError:
            return []


def _update_approval_status(approval_id: str, status: str, notes: str) -> bool:
    approvals = _load_approvals()
    found = False
    for a in approvals:
        if a.get("id") == approval_id or a.get("approval_id") == approval_id or a.get("proposal_id") == approval_id:
            a["status"] = status
            a["decided_at"] = utc_iso()
            a["decision_notes"] = notes
            a["decision_hash"] = hashlib.sha256(
                f"{approval_id}{status}{notes}{utc_iso()}".encode()
            ).hexdigest()[:16]
            found = True
            break

    if found:
        os.makedirs(os.path.dirname(PATHS["approvals"]), exist_ok=True)
        with open(PATHS["approvals"], "w") as f:
            json.dump(approvals, f, indent=2)

    return found


def _list_briefings() -> list:
    files = sorted(glob.glob(os.path.join(PATHS["briefings"], "*.json")), reverse=True)
    result = []
    for f in files[:10]:
        result.append({
            "filename": os.path.basename(f),
            "generated_at": timestamp_to_utc_iso(os.path.getmtime(f)),
            "path": f,
        })
    return result


def _load_latest_briefing() -> Optional[dict]:
    files = sorted(glob.glob(os.path.join(PATHS["briefings"], "*.json")), reverse=True)
    if not files:
        return None
    with open(files[0]) as f:
        return json.load(f)


def _list_horizon_reports() -> list:
    files = sorted(glob.glob(os.path.join(PATHS["horizon"], "*.json")), reverse=True)
    result = []
    for f in files[:10]:
        with open(f) as fp:
            data = json.load(fp)
        result.append({
            "report_id": data.get("report_id"),
            "generated_at": data.get("generated_at"),
            "proposals": len(data.get("proposals", [])),
            "findings": data.get("findings_count", 0),
        })
    return result


def _load_latest_horizon_report() -> Optional[dict]:
    files = sorted(glob.glob(os.path.join(PATHS["horizon"], "*.json")), reverse=True)
    if not files:
        return None
    with open(files[0]) as f:
        return json.load(f)


def _load_canon_files() -> dict:
    result = {}
    if not os.path.exists(PATHS["canon"]):
        return result
    for fname in os.listdir(PATHS["canon"]):
        if fname.endswith(".yaml") or fname.endswith(".md"):
            fpath = os.path.join(PATHS["canon"], fname)
            with open(fpath) as f:
                result[fname] = f.read()
    return result


def _load_episodic_memory(limit: int) -> list:
    entries = []
    pattern = os.path.join(PATHS["episodic"], "*.json")
    files = sorted(glob.glob(pattern), reverse=True)[:limit]
    for f in files:
        with open(f) as fp:
            entries.append(json.load(fp))
    return entries


def _load_log_entries(agent: Optional[str], limit: int) -> list:
    if agent:
        log_file = os.path.join(PATHS["logs"], f"{agent}_agent.log")
        files = [log_file] if os.path.exists(log_file) else []
    else:
        files = glob.glob(os.path.join(PATHS["logs"], "*.log"))

    entries = []
    for f in files:
        with open(f) as fp:
            lines = fp.readlines()
        entries.extend([l.strip() for l in lines[-limit:]])

    return entries[-limit:]


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("PERMANENCE OS — DASHBOARD API")
    print(f"Version: {API_VERSION}")
    print(f"Running on: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    print("Scope: LOCAL ONLY (no external exposure)")
    print("=" * 60)

    app.run(
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        debug=False,  # Never True in production
    )
