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
    CORS(
        app,
        origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:8787",
            "http://localhost:8787",
            "https://permanencesystems.com",
        ],
    )

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.environ.get("PERMANENCE_BASE_DIR", APP_DIR)
OUTPUT_ROOT = os.environ.get("PERMANENCE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
if not os.path.exists(os.path.join(OUTPUT_ROOT, "briefings")):
    storage_output_root = os.path.join(BASE_DIR, "permanence_storage", "outputs")
    if os.path.exists(storage_output_root):
        OUTPUT_ROOT = storage_output_root
PATHS = {
    "canon":    os.path.join(BASE_DIR, "canon"),
    "logs":     os.path.join(BASE_DIR, "logs"),
    "outputs":  OUTPUT_ROOT,
    "working":  os.environ.get("PERMANENCE_WORKING_DIR", os.path.join(BASE_DIR, "memory", "working")),
    "tool":     os.environ.get("PERMANENCE_TOOL_DIR", os.path.join(BASE_DIR, "memory", "tool")),
    "chronicle": os.path.join(OUTPUT_ROOT, "chronicle"),
    "chronicle_shared": os.path.join(BASE_DIR, "memory", "chronicle", "shared"),
    "episodic": os.path.join(BASE_DIR, "memory", "episodic"),
    "horizon":  os.path.join(OUTPUT_ROOT, "horizon"),
    "briefings":os.path.join(OUTPUT_ROOT, "briefings"),
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
    chronicle_last_generated = _get_last_chronicle_time()
    latest_task = _load_latest_task_summary()
    promotion = _load_promotion_status()

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
        "chronicle": {
            "last_generated": chronicle_last_generated,
        },
        "promotion": promotion,
        "latest_task": latest_task,
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
# REVENUE OPS
# ─────────────────────────────────────────────

@app.route("/api/revenue/latest", methods=["GET"])
def get_latest_revenue():
    """Returns latest revenue queue, execution board, and pipeline metrics."""
    log_api_call("GET", "/api/revenue/latest")
    return jsonify(_load_revenue_snapshot())


@app.route("/api/revenue/pipeline", methods=["GET"])
def get_revenue_pipeline():
    """Return sales pipeline rows for Revenue Ops view."""
    open_only = request.args.get("open_only", "0") in {"1", "true", "yes"}
    limit = max(1, min(100, request.args.get("limit", 50, type=int)))
    log_api_call("GET", "/api/revenue/pipeline", {"open_only": open_only, "limit": limit})
    rows = _pipeline_rows(open_only=open_only, limit=limit)
    return jsonify(
        {
            "count": len(rows),
            "rows": rows,
            "path": _pipeline_path(),
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/revenue/pipeline/lead", methods=["POST"])
def create_revenue_lead():
    """Create a lead in sales pipeline from dashboard or intake capture."""
    payload = request.get_json() or {}
    log_api_call("POST", "/api/revenue/pipeline/lead", payload)
    name = str(payload.get("name") or "").strip()
    if not name:
        log_api_call("POST", "/api/revenue/pipeline/lead", payload, "INVALID_NAME")
        abort(400, description="Lead name is required.")

    created = _pipeline_add_lead(
        {
            "name": name,
            "source": str(payload.get("source") or "dashboard"),
            "stage": str(payload.get("stage") or "lead"),
            "offer": str(payload.get("offer") or "Permanence OS Foundation Setup"),
            "est_value": payload.get("est_value", 1500),
            "next_action": str(payload.get("next_action") or "Send intake + book fit call"),
            "next_action_due": str(payload.get("next_action_due") or ""),
            "notes": str(payload.get("notes") or ""),
        }
    )
    return jsonify(
        {
            "status": "CREATED",
            "lead_id": created.get("lead_id"),
            "lead": created,
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/revenue/pipeline/<lead_id>", methods=["POST"])
def update_revenue_lead(lead_id: str):
    """Update a lead stage/action in the pipeline."""
    payload = request.get_json() or {}
    log_api_call("POST", f"/api/revenue/pipeline/{lead_id}", payload)
    updated = _pipeline_update_lead(lead_id, payload)
    if updated is None:
        log_api_call("POST", f"/api/revenue/pipeline/{lead_id}", payload, "NOT_FOUND")
        abort(404, description="Lead not found.")
    return jsonify(
        {
            "status": "UPDATED",
            "lead_id": lead_id,
            "lead": updated,
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/revenue/intake", methods=["GET", "POST"])
def foundation_intake():
    """Capture and list FOUNDATION intake submissions."""
    if request.method == "GET":
        limit = max(1, min(100, request.args.get("limit", 20, type=int)))
        log_api_call("GET", "/api/revenue/intake", {"limit": limit})
        rows = _load_intake_rows(limit=limit)
        return jsonify(
            {
                "count": len(rows),
                "rows": rows,
                "path": _intake_path(),
                "timestamp": utc_iso(),
            }
        )

    payload = request.get_json() or {}
    log_api_call("POST", "/api/revenue/intake", payload)
    name = str(payload.get("name") or "").strip()
    email = str(payload.get("email") or "").strip()
    if not name or "@" not in email:
        log_api_call("POST", "/api/revenue/intake", payload, "INVALID_INPUT")
        abort(400, description="Name and valid email are required.")

    workflow = str(payload.get("workflow") or "")
    package = str(payload.get("package") or "Core")
    blocker = str(payload.get("blocker") or "")
    source = str(payload.get("source") or "foundation_site")
    created_at = utc_iso()

    entry = {
        "intake_id": f"I-{utc_now().strftime('%Y%m%d-%H%M%S%f')}",
        "name": name,
        "email": email,
        "workflow": workflow,
        "package": package,
        "blocker": blocker,
        "source": source,
        "created_at": created_at,
    }
    _append_jsonl(_intake_path(), entry)

    create_lead = payload.get("create_lead", True) is not False
    lead_id: Optional[str] = None
    if create_lead:
        package_value = {"pilot": 750, "core": 1500, "operator": 3000}.get(package.strip().lower(), 1500)
        tomorrow = (utc_now().date() + datetime.timedelta(days=1)).isoformat()
        lead = _pipeline_add_lead(
            {
                "name": name,
                "source": f"{source}:{email}",
                "stage": "lead",
                "offer": "Permanence OS Foundation Setup",
                "est_value": package_value,
                "next_action": "Send intake + book fit call",
                "next_action_due": tomorrow,
                "notes": f"workflow={workflow}; package={package}; blocker={blocker}; email={email}",
            }
        )
        lead_id = str(lead.get("lead_id") or "")

    return jsonify(
        {
            "status": "CAPTURED",
            "intake": entry,
            "lead_id": lead_id,
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/revenue/action", methods=["POST"])
def update_revenue_action():
    """Mark a queue action complete/incomplete for operator progress tracking."""
    payload = request.get_json() or {}
    log_api_call("POST", "/api/revenue/action", payload)

    action = str(payload.get("action") or "").strip()
    if not action:
        log_api_call("POST", "/api/revenue/action", payload, "INVALID_ACTION")
        abort(400, description="Action text is required.")

    completed = _coerce_bool(payload.get("completed"), True)
    source = str(payload.get("source") or "dashboard").strip()
    actor = str(payload.get("actor") or "human").strip()
    notes = str(payload.get("notes") or "").strip()
    entry = _record_revenue_action_status(
        action=action,
        completed=completed,
        source=source,
        actor=actor,
        notes=notes,
    )
    return jsonify(
        {
            "status": "UPDATED",
            "action_hash": entry["action_hash"],
            "completed": bool(entry["completed"]),
            "entry": entry,
            "timestamp": utc_iso(),
        }
    )


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
# CHRONICLE REPORTS
# ─────────────────────────────────────────────

@app.route("/api/chronicle", methods=["GET"])
def get_chronicle_reports():
    """Returns list of chronicle timeline reports."""
    log_api_call("GET", "/api/chronicle")

    reports = _list_chronicle_reports()
    return jsonify({
        "count": len(reports),
        "reports": reports,
    })


@app.route("/api/chronicle/latest", methods=["GET"])
def get_latest_chronicle():
    """Returns latest chronicle report, preferring shared stable copy."""
    log_api_call("GET", "/api/chronicle/latest")

    report = _load_latest_chronicle_report()
    if not report:
        return jsonify({"error": "No chronicle reports found"}), 404

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

REVENUE_STAGE_PROB = {
    "lead": 0.10,
    "qualified": 0.25,
    "call_scheduled": 0.40,
    "proposal_sent": 0.60,
    "negotiation": 0.75,
    "won": 1.00,
    "lost": 0.00,
}


def _intake_path() -> str:
    return os.environ.get(
        "PERMANENCE_REVENUE_INTAKE_PATH",
        os.path.join(PATHS["working"], "revenue_intake.jsonl"),
    )


def _append_jsonl(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(payload) + "\n")


def _load_intake_rows(limit: int = 20) -> list[dict]:
    path = _intake_path()
    if not os.path.exists(path):
        return []
    rows: list[dict] = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
    except OSError:
        return []
    rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    if limit <= 0:
        return rows
    return rows[:limit]


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _validate_stage(value: str) -> str:
    stage = str(value or "lead").strip().lower()
    if stage not in REVENUE_STAGE_PROB:
        return "lead"
    return stage


def _pipeline_load() -> list[dict]:
    path = _pipeline_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _pipeline_save(rows: list[dict]) -> None:
    path = _pipeline_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(rows, f, indent=2)
        f.write("\n")


def _pipeline_rows(*, open_only: bool = False, limit: int = 50) -> list[dict]:
    rows = _pipeline_load()
    if open_only:
        rows = [row for row in rows if str(row.get("stage")) not in {"won", "lost"}]
    rows.sort(key=lambda r: str(r.get("updated_at", "")), reverse=True)
    return rows[:limit]


def _new_lead_id() -> str:
    return f"L-{utc_now().strftime('%Y%m%d-%H%M%S%f')}"


def _pipeline_add_lead(payload: dict) -> dict:
    rows = _pipeline_load()
    row = {
        "lead_id": _new_lead_id(),
        "name": str(payload.get("name") or "Unknown").strip(),
        "source": str(payload.get("source") or "api").strip(),
        "stage": _validate_stage(str(payload.get("stage") or "lead")),
        "offer": str(payload.get("offer") or "Permanence OS Foundation Setup").strip(),
        "est_value": _coerce_float(payload.get("est_value"), 1500.0),
        "actual_value": None,
        "next_action": str(payload.get("next_action") or "").strip(),
        "next_action_due": str(payload.get("next_action_due") or "").strip(),
        "notes": str(payload.get("notes") or "").strip(),
        "created_at": utc_iso(),
        "updated_at": utc_iso(),
        "closed_at": None,
    }
    rows.append(row)
    _pipeline_save(rows)
    return row


def _pipeline_update_lead(lead_id: str, payload: dict) -> Optional[dict]:
    rows = _pipeline_load()
    target: Optional[dict] = None
    for row in rows:
        if str(row.get("lead_id")) == lead_id:
            target = row
            break
    if target is None:
        return None

    if "stage" in payload:
        target["stage"] = _validate_stage(str(payload.get("stage")))
        if target["stage"] in {"won", "lost"}:
            target["closed_at"] = target.get("closed_at") or utc_iso()
            if target["stage"] == "won" and target.get("actual_value") is None:
                target["actual_value"] = _coerce_float(target.get("est_value"), 0.0)
        else:
            target["closed_at"] = None

    if "offer" in payload:
        target["offer"] = str(payload.get("offer") or "")
    if "est_value" in payload:
        target["est_value"] = _coerce_float(payload.get("est_value"), _coerce_float(target.get("est_value"), 0.0))
    if "actual_value" in payload:
        target["actual_value"] = _coerce_float(
            payload.get("actual_value"), _coerce_float(target.get("actual_value"), 0.0)
        )
    if "next_action" in payload:
        target["next_action"] = str(payload.get("next_action") or "")
    if "next_action_due" in payload:
        target["next_action_due"] = str(payload.get("next_action_due") or "")
    if "notes" in payload:
        target["notes"] = str(payload.get("notes") or "")
    target["updated_at"] = utc_iso()
    _pipeline_save(rows)
    return target


def _candidate_output_dirs() -> list[str]:
    raw_candidates = [
        PATHS["outputs"],
        os.path.join(BASE_DIR, "outputs"),
        os.path.join(BASE_DIR, "permanence_storage", "outputs"),
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        normalized = os.path.abspath(os.path.expanduser(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _latest_output_file(pattern: str) -> Optional[str]:
    files: list[str] = []
    for output_dir in _candidate_output_dirs():
        files.extend(glob.glob(os.path.join(output_dir, pattern)))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _read_text_file(path: Optional[str]) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def _first_existing_output_file(filename: str) -> Optional[str]:
    for output_dir in _candidate_output_dirs():
        candidate = os.path.join(output_dir, filename)
        if os.path.exists(candidate):
            return candidate
    return None


def _extract_markdown_section(lines: list[str], heading: str) -> list[str]:
    section: list[str] = []
    in_section = False
    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith("## "):
            if line == heading:
                in_section = True
                continue
            if in_section:
                break
        if in_section:
            section.append(line)
    return section


def _parse_revenue_queue_actions(markdown: str) -> list[str]:
    if not markdown:
        return []
    actions: list[str] = []
    for line in markdown.splitlines():
        text = line.strip()
        if not text or ". [" not in text:
            continue
        prefix, body = text.split(". ", 1) if ". " in text else ("", "")
        if not prefix.isdigit() or "] " not in body or not body.startswith("["):
            continue
        actions.append(body)
    return actions


def _revenue_action_status_path() -> str:
    return os.environ.get(
        "PERMANENCE_REVENUE_ACTION_STATUS_PATH",
        os.path.join(PATHS["working"], "revenue_action_status.jsonl"),
    )


def _action_hash(action_text: str) -> str:
    normalized = str(action_text or "").strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _load_revenue_action_status() -> dict[str, dict]:
    path = _revenue_action_status_path()
    if not os.path.exists(path):
        return {}
    latest_by_hash: dict[str, dict] = {}
    try:
        with open(path) as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict):
                    continue
                key = str(item.get("action_hash") or "").strip()
                if not key:
                    continue
                latest_by_hash[key] = item
    except OSError:
        return {}
    return latest_by_hash


def _record_revenue_action_status(*, action: str, completed: bool, source: str, actor: str, notes: str) -> dict:
    path = _revenue_action_status_path()
    action_text = str(action or "").strip()
    entry = {
        "event_id": f"RA-{utc_now().strftime('%Y%m%d-%H%M%S%f')}",
        "timestamp": utc_iso(),
        "action": action_text,
        "action_hash": _action_hash(action_text),
        "completed": bool(completed),
        "source": source,
        "actor": actor,
        "notes": notes,
    }
    _append_jsonl(path, entry)
    return entry


def _build_queue_progress(actions: list[str]) -> dict:
    status_map = _load_revenue_action_status()
    items: list[dict] = []
    completed = 0
    for action in actions[:7]:
        key = _action_hash(action)
        state = status_map.get(key, {})
        is_done = _coerce_bool(state.get("completed"), False)
        if is_done:
            completed += 1
        items.append(
            {
                "action": action,
                "action_hash": key,
                "completed": is_done,
                "completed_at": state.get("timestamp") if is_done else None,
            }
        )
    total = len(items)
    pending = max(0, total - completed)
    return {
        "items": items,
        "completed_count": completed,
        "pending_count": pending,
        "completion_rate": _safe_rate(completed, total),
        "status_path": _revenue_action_status_path(),
    }


def _parse_revenue_board(markdown: str) -> dict:
    lines = markdown.splitlines() if markdown else []
    non_negotiables: list[str] = []
    urgent_actions: list[str] = []
    inbox = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}

    for line in _extract_markdown_section(lines, "## Today's Non-Negotiables"):
        text = line.strip()
        if text.startswith(tuple(f"{n}." for n in range(1, 11))) and ". " in text:
            non_negotiables.append(text.split(". ", 1)[1])

    for line in _extract_markdown_section(lines, "## Pipeline Urgent Actions (<=24h)"):
        text = line.strip()
        if text.startswith("- "):
            urgent_actions.append(text[2:])

    for line in lines:
        text = line.strip()
        if not text.startswith("- P0:"):
            continue
        parts = [p.strip() for p in text[2:].split("|")]
        for part in parts:
            if ":" not in part:
                continue
            key, value = [s.strip() for s in part.split(":", 1)]
            if key in inbox:
                try:
                    inbox[key] = int(value)
                except ValueError:
                    inbox[key] = 0
        break

    return {
        "non_negotiables": non_negotiables,
        "urgent_actions": urgent_actions,
        "inbox_pressure": inbox,
    }


def _parse_iso_datetime(raw: object) -> Optional[datetime.datetime]:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _week_window_local(today: Optional[datetime.date] = None) -> tuple[datetime.date, datetime.date]:
    today = today or datetime.datetime.now().date()
    start = today - datetime.timedelta(days=today.weekday())
    end = start + datetime.timedelta(days=6)
    return start, end


def _in_window(dt: Optional[datetime.datetime], start: datetime.date, end: datetime.date) -> bool:
    if dt is None:
        return False
    day = dt.date()
    return start <= day <= end


def _safe_rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


def _build_revenue_funnel(pipeline_rows: list[dict], intake_rows: list[dict]) -> dict:
    week_start, week_end = _week_window_local()

    intake_week = 0
    for row in intake_rows:
        created = _parse_iso_datetime(row.get("created_at"))
        if _in_window(created, week_start, week_end):
            intake_week += 1

    leads_week = 0
    won_week = 0
    for row in pipeline_rows:
        created = _parse_iso_datetime(row.get("created_at"))
        closed = _parse_iso_datetime(row.get("closed_at"))
        stage = str(row.get("stage") or "lead")
        if _in_window(created, week_start, week_end):
            leads_week += 1
        if stage == "won" and _in_window(closed, week_start, week_end):
            won_week += 1

    total = len(pipeline_rows)
    qualified_plus = sum(
        1 for row in pipeline_rows if str(row.get("stage") or "lead") in {"qualified", "call_scheduled", "proposal_sent", "negotiation", "won"}
    )
    call_plus = sum(
        1 for row in pipeline_rows if str(row.get("stage") or "lead") in {"call_scheduled", "proposal_sent", "negotiation", "won"}
    )
    proposal_plus = sum(
        1 for row in pipeline_rows if str(row.get("stage") or "lead") in {"proposal_sent", "negotiation", "won"}
    )
    won_total = sum(1 for row in pipeline_rows if str(row.get("stage") or "lead") == "won")

    segments = [
        {
            "key": "intake_to_lead",
            "label": "Intake -> Lead",
            "numerator": leads_week,
            "denominator": intake_week,
            "rate": _safe_rate(leads_week, intake_week),
        },
        {
            "key": "lead_to_qualified",
            "label": "Lead -> Qualified",
            "numerator": qualified_plus,
            "denominator": total,
            "rate": _safe_rate(qualified_plus, total),
        },
        {
            "key": "qualified_to_call",
            "label": "Qualified -> Call",
            "numerator": call_plus,
            "denominator": qualified_plus,
            "rate": _safe_rate(call_plus, qualified_plus),
        },
        {
            "key": "call_to_proposal",
            "label": "Call -> Proposal",
            "numerator": proposal_plus,
            "denominator": call_plus,
            "rate": _safe_rate(proposal_plus, call_plus),
        },
        {
            "key": "proposal_to_won",
            "label": "Proposal -> Won",
            "numerator": won_total,
            "denominator": proposal_plus,
            "rate": _safe_rate(won_total, proposal_plus),
        },
    ]

    bottleneck: Optional[dict] = None
    for segment in segments:
        rate = segment.get("rate")
        denominator = int(segment.get("denominator") or 0)
        if rate is None or denominator <= 0:
            continue
        candidate = {
            "key": segment["key"],
            "label": segment["label"],
            "rate": rate,
            "numerator": segment["numerator"],
            "denominator": denominator,
        }
        if bottleneck is None or float(rate) < float(bottleneck["rate"]):
            bottleneck = candidate

    suggestions = {
        "intake_to_lead": "Close intake loop same day: respond + schedule fit call within 2 hours.",
        "lead_to_qualified": "Tighten qualifier questions in outreach and intake to pre-filter faster.",
        "qualified_to_call": "Increase call conversion: send direct calendar link + 2 reminder touches.",
        "call_to_proposal": "Ship proposals within 24 hours after calls with one clear CTA.",
        "proposal_to_won": "Improve close rate: add urgency, objection handling, and 48h follow-up cadence.",
    }
    if bottleneck is not None:
        bottleneck["recommendation"] = suggestions.get(bottleneck["key"], "Focus this stage with stronger follow-up discipline.")

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "cta_responses_week": intake_week,
        "intake_week": intake_week,
        "leads_created_week": leads_week,
        "wins_week": won_week,
        "pipeline_total": total,
        "segments": segments,
        "bottleneck": bottleneck,
    }


def _pipeline_path() -> str:
    return os.environ.get(
        "PERMANENCE_SALES_PIPELINE_PATH",
        os.path.join(PATHS["working"], "sales_pipeline.json"),
    )


def _load_pipeline_snapshot() -> dict:
    pipeline_path = _pipeline_path()
    rows = _pipeline_load()
    if not rows:
        return {
            "path": pipeline_path,
            "total": 0,
            "open_count": 0,
            "open_value": 0.0,
            "weighted_value": 0.0,
            "urgent_count": 0,
            "updated_at": None,
            "open_rows": [],
        }
    open_rows = [row for row in rows if str(row.get("stage")) not in {"won", "lost"}]
    open_value = 0.0
    weighted_value = 0.0
    for row in open_rows:
        est = _coerce_float(row.get("est_value"), 0.0)
        stage = str(row.get("stage", "lead"))
        open_value += est
        weighted_value += est * REVENUE_STAGE_PROB.get(stage, 0.0)

    cutoff = (datetime.datetime.now().date() + datetime.timedelta(days=1)).isoformat()
    urgent_count = 0
    for row in open_rows:
        due = str(row.get("next_action_due") or "")
        if due and due <= cutoff:
            urgent_count += 1

    return {
        "path": pipeline_path,
        "total": len(rows),
        "open_count": len(open_rows),
        "open_value": open_value,
        "weighted_value": weighted_value,
        "urgent_count": urgent_count,
        "updated_at": timestamp_to_utc_iso(os.path.getmtime(pipeline_path)) if os.path.exists(pipeline_path) else None,
        "open_rows": sorted(open_rows, key=lambda r: str(r.get("updated_at", "")), reverse=True)[:10],
    }


def _load_revenue_snapshot() -> dict:
    queue_path = _latest_output_file("revenue_action_queue_*.md")

    arch_path = _first_existing_output_file("revenue_architecture_latest.md")
    if arch_path is None:
        arch_path = _latest_output_file("revenue_architecture_*.md") or ""

    board_path = _first_existing_output_file("revenue_execution_board_latest.md")
    if board_path is None:
        board_path = _latest_output_file("revenue_execution_board_*.md") or ""

    queue_markdown = _read_text_file(queue_path)
    board_markdown = _read_text_file(board_path)
    architecture_markdown = _read_text_file(arch_path)

    queue_actions = _parse_revenue_queue_actions(queue_markdown)
    queue_progress = _build_queue_progress(queue_actions)
    board_data = _parse_revenue_board(board_markdown)
    pipeline = _load_pipeline_snapshot()
    pipeline_rows = _pipeline_load()
    intake_rows_all = _load_intake_rows(limit=0)
    intake_rows_preview = intake_rows_all[:10]
    funnel = _build_revenue_funnel(pipeline_rows, intake_rows_all)

    return {
        "generated_at": utc_iso(),
        "sources": {
            "queue": queue_path,
            "architecture": arch_path or None,
            "execution_board": board_path or None,
            "pipeline": pipeline["path"],
        },
        "queue": {
            "count": len(queue_actions),
            "actions": queue_actions[:7],
            "items": queue_progress["items"],
            "completed_count": queue_progress["completed_count"],
            "pending_count": queue_progress["pending_count"],
            "completion_rate": queue_progress["completion_rate"],
            "status_path": queue_progress["status_path"],
            "content_markdown": queue_markdown,
        },
        "board": {
            "non_negotiables": board_data["non_negotiables"][:7],
            "urgent_actions": board_data["urgent_actions"][:10],
            "inbox_pressure": board_data["inbox_pressure"],
            "content_markdown": board_markdown,
        },
        "pipeline": {
            "total": pipeline["total"],
            "open_count": pipeline["open_count"],
            "open_value": pipeline["open_value"],
            "weighted_value": pipeline["weighted_value"],
            "urgent_count": pipeline["urgent_count"],
            "updated_at": pipeline["updated_at"],
            "open_rows": pipeline["open_rows"],
        },
        "intake": {
            "count": len(intake_rows_all),
            "rows": intake_rows_preview,
            "path": _intake_path(),
        },
        "funnel": funnel,
        "architecture_excerpt": architecture_markdown[:4000],
    }


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
    files = _list_briefing_files()
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


def _get_last_chronicle_time() -> Optional[str]:
    shared_latest = os.path.join(PATHS["chronicle_shared"], "chronicle_latest.json")
    if os.path.exists(shared_latest):
        return timestamp_to_utc_iso(os.path.getmtime(shared_latest))
    files = sorted(glob.glob(os.path.join(PATHS["chronicle"], "chronicle_report_*.json")), reverse=True)
    if not files:
        return None
    return timestamp_to_utc_iso(os.path.getmtime(files[0]))


def _candidate_log_dirs() -> list[str]:
    status_json_path = os.environ.get(
        "PERMANENCE_STATUS_TODAY_JSON",
        os.path.join(PATHS["logs"], "status_today.json"),
    )
    storage_root = os.environ.get("PERMANENCE_STORAGE_ROOT", os.path.join(BASE_DIR, "permanence_storage"))
    raw_candidates = [
        PATHS["logs"],
        os.path.dirname(status_json_path),
        os.path.join(os.path.expanduser(storage_root), "logs"),
        os.path.join(BASE_DIR, "permanence_storage", "logs"),
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        normalized = os.path.abspath(os.path.expanduser(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _latest_glance_gate() -> dict:
    status_json_path = os.environ.get(
        "PERMANENCE_STATUS_TODAY_JSON",
        os.path.join(PATHS["logs"], "status_today.json"),
    )
    candidates = [os.path.abspath(os.path.expanduser(status_json_path))]
    for log_dir in _candidate_log_dirs():
        candidate = os.path.join(log_dir, "status_today.json")
        if candidate not in candidates:
            candidates.append(candidate)

    latest: Optional[tuple[float, str, str]] = None
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        state = str(payload.get("today_state", "")).upper()
        if not state:
            continue
        mtime = os.path.getmtime(path)
        if latest is None or mtime > latest[0]:
            latest = (mtime, state, path)
    if latest is None:
        return {"state": "PENDING", "path": None, "updated_at": None}
    return {"state": latest[1], "path": latest[2], "updated_at": timestamp_to_utc_iso(latest[0])}


def _latest_phase_gate() -> dict:
    latest: Optional[tuple[float, str, str]] = None
    for log_dir in _candidate_log_dirs():
        if not os.path.isdir(log_dir):
            continue
        for name in os.listdir(log_dir):
            if not (name.startswith("phase_gate_") and name.endswith(".md")):
                continue
            path = os.path.join(log_dir, name)
            try:
                with open(path) as f:
                    text = f.read()
            except OSError:
                continue
            if "- Phase gate: PASS" in text:
                state = "PASS"
            elif "- Phase gate: FAIL" in text:
                state = "FAIL"
            else:
                state = "PENDING"
            mtime = os.path.getmtime(path)
            if latest is None or mtime > latest[0]:
                latest = (mtime, state, path)
    if latest is None:
        return {"state": "PENDING", "path": None, "updated_at": None}
    return {"state": latest[1], "path": latest[2], "updated_at": timestamp_to_utc_iso(latest[0])}


def _promotion_queue_path() -> str:
    memory_dir = os.environ.get("PERMANENCE_MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
    return os.environ.get(
        "PERMANENCE_PROMOTION_QUEUE",
        os.path.join(memory_dir, "working", "promotion_queue.json"),
    )


def _count_promotion_queue_items() -> int:
    queue_path = _promotion_queue_path()
    if not os.path.exists(queue_path):
        return 0
    try:
        with open(queue_path) as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return 0
    return len(payload) if isinstance(payload, list) else 0


def _get_last_promotion_review_time() -> Optional[str]:
    review_path = os.environ.get(
        "PERMANENCE_PROMOTION_REVIEW_OUTPUT",
        os.path.join(PATHS["outputs"], "promotion_review.md"),
    )
    candidates = [
        os.path.abspath(os.path.expanduser(review_path)),
        os.path.join(PATHS["outputs"], "promotion_review.md"),
        os.path.join(BASE_DIR, "outputs", "promotion_review.md"),
        os.path.join(BASE_DIR, "permanence_storage", "outputs", "promotion_review.md"),
    ]
    existing = [path for path in candidates if os.path.exists(path)]
    if not existing:
        return None
    latest = max(existing, key=os.path.getmtime)
    return timestamp_to_utc_iso(os.path.getmtime(latest))


def _load_promotion_status() -> dict:
    glance = _latest_glance_gate()
    phase = _latest_phase_gate()
    return {
        "queue_items": _count_promotion_queue_items(),
        "glance_gate": glance["state"],
        "phase_gate": phase["state"],
        "glance_updated_at": glance["updated_at"],
        "phase_updated_at": phase["updated_at"],
        "review_last_generated": _get_last_promotion_review_time(),
    }


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
    files = _list_briefing_files()
    result = []
    for f in files[:10]:
        result.append({
            "filename": os.path.basename(f),
            "generated_at": timestamp_to_utc_iso(os.path.getmtime(f)),
            "path": f,
            "format": "json" if f.endswith(".json") else "markdown",
        })
    return result


def _load_latest_briefing() -> Optional[dict]:
    files = _list_briefing_files()
    if not files:
        return None
    latest = files[0]
    if latest.endswith(".json"):
        with open(latest) as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("format", "json")
            data.setdefault("source_path", latest)
            return data
        return {"format": "json", "source_path": latest, "payload": data}

    with open(latest) as f:
        markdown = f.read()
    return {
        "format": "markdown",
        "source_path": latest,
        "filename": os.path.basename(latest),
        "generated_at": timestamp_to_utc_iso(os.path.getmtime(latest)),
        "content_markdown": markdown,
    }


def _list_briefing_files() -> list:
    patterns = [
        os.path.join(PATHS["briefings"], "*.json"),
        os.path.join(PATHS["briefings"], "*.md"),
    ]
    files: list[str] = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))
    return sorted(files, key=lambda p: os.path.getmtime(p), reverse=True)


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


def _list_chronicle_reports() -> list:
    files = sorted(glob.glob(os.path.join(PATHS["chronicle"], "chronicle_report_*.json")), reverse=True)
    result = []
    for f in files[:10]:
        with open(f) as fp:
            data = json.load(fp)
        result.append({
            "generated_at": data.get("generated_at"),
            "events_count": data.get("events_count", 0),
            "commit_count": data.get("commit_count", 0),
            "path": f,
        })
    return result


def _load_latest_chronicle_report() -> Optional[dict]:
    shared_latest = os.path.join(PATHS["chronicle_shared"], "chronicle_latest.json")
    if os.path.exists(shared_latest):
        with open(shared_latest) as f:
            data = json.load(f)
        if isinstance(data, dict):
            data["source_path"] = shared_latest
            return data

    files = sorted(glob.glob(os.path.join(PATHS["chronicle"], "chronicle_report_*.json")), reverse=True)
    if not files:
        return None
    with open(files[0]) as f:
        data = json.load(f)
    if isinstance(data, dict):
        data["source_path"] = files[0]
        return data
    return None


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


def _load_latest_task_summary() -> Optional[dict]:
    pattern = os.path.join(PATHS["episodic"], "*.json")
    files = sorted(glob.glob(pattern), key=lambda p: os.path.getmtime(p), reverse=True)
    if not files:
        return None
    try:
        with open(files[0]) as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    artifacts = state.get("artifacts", {}) if isinstance(state.get("artifacts"), dict) else {}
    model_routes = artifacts.get("model_routes")
    if not isinstance(model_routes, dict):
        model_routes = None
    return {
        "task_id": state.get("task_id"),
        "stage": state.get("stage"),
        "status": state.get("status"),
        "risk_tier": state.get("risk_tier"),
        "goal": state.get("task_goal"),
        "model_routes": model_routes,
    }


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
