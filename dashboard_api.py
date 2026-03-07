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
import re
import subprocess
import sys
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


@app.route("/api/approvals/approve-all", methods=["POST"])
def approve_all():
    """
    Bulk-approve all PENDING_HUMAN_REVIEW items at LOW or MEDIUM priority.
    HIGH priority items are intentionally skipped — those remain in queue
    for individual human review per the non-negotiable governance model.
    Returns the count and IDs of everything approved.
    """
    payload = request.get_json() or {}
    notes = payload.get("notes", "bulk approve — human authority confirmed")

    log_api_call("POST", "/api/approvals/approve-all", payload)

    approvals = _load_approvals()
    approved_ids = []
    skipped_high = []

    for item in approvals:
        if item.get("status") != "PENDING_HUMAN_REVIEW":
            continue
        priority = str(item.get("priority", "")).upper()
        if priority == "HIGH":
            skipped_high.append(item.get("id") or item.get("approval_id", ""))
            continue
        approval_id = item.get("id") or item.get("approval_id", "")
        _update_approval_status(approval_id, "APPROVED", notes)
        approved_ids.append(approval_id)

    return jsonify({
        "approved": len(approved_ids),
        "skipped_high_risk": len(skipped_high),
        "approved_ids": approved_ids,
        "skipped_ids": skipped_high,
        "decided_at": utc_iso(),
        "message": f"Approved {len(approved_ids)} items. {len(skipped_high)} HIGH-risk items kept for individual review.",
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


@app.route("/api/second-brain/latest", methods=["GET"])
def get_second_brain_latest():
    """Returns latest second-brain artifacts (life + side-income + unified report)."""
    log_api_call("GET", "/api/second-brain/latest")
    return jsonify(_load_second_brain_snapshot())


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
    playbook = _load_revenue_playbook()
    default_offer = str(playbook.get("offer_name") or "Permanence OS Foundation Setup")
    name = str(payload.get("name") or "").strip()
    if not name:
        log_api_call("POST", "/api/revenue/pipeline/lead", payload, "INVALID_NAME")
        abort(400, description="Lead name is required.")

    created = _pipeline_add_lead(
        {
            "name": name,
            "source": str(payload.get("source") or "dashboard"),
            "stage": str(payload.get("stage") or "lead"),
            "offer": str(payload.get("offer") or default_offer),
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

    playbook = _load_revenue_playbook()
    default_offer = str(playbook.get("offer_name") or "Permanence OS Foundation Setup")
    default_price = _coerce_float(playbook.get("price_usd"), 1500.0)

    create_lead = payload.get("create_lead", True) is not False
    lead_id: Optional[str] = None
    if create_lead:
        package_value = {"pilot": 750, "core": 1500, "operator": 3000}.get(package.strip().lower(), default_price)
        tomorrow = (utc_now().date() + datetime.timedelta(days=1)).isoformat()
        lead = _pipeline_add_lead(
            {
                "name": name,
                "source": f"{source}:{email}",
                "stage": "lead",
                "offer": default_offer,
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


@app.route("/api/revenue/playbook", methods=["GET", "POST"])
def revenue_playbook():
    """Read/update locked offer + CTA playbook."""
    if request.method == "GET":
        log_api_call("GET", "/api/revenue/playbook")
        return jsonify(
            {
                "status": "OK",
                "path": _revenue_playbook_path(),
                "playbook": _load_revenue_playbook(),
                "timestamp": utc_iso(),
            }
        )

    payload = request.get_json() or {}
    log_api_call("POST", "/api/revenue/playbook", payload)
    current = _load_revenue_playbook()
    updates = dict(current)
    if "offer_name" in payload:
        updates["offer_name"] = str(payload.get("offer_name") or "").strip()
    if "offer_promise" in payload:
        updates["offer_promise"] = str(payload.get("offer_promise") or "").strip()
    if "delivery_window_days" in payload:
        updates["delivery_window_days"] = max(1, int(_coerce_float(payload.get("delivery_window_days"), 7)))
    if "cta_keyword" in payload:
        updates["cta_keyword"] = str(payload.get("cta_keyword") or "").strip().upper()
    if "cta_public" in payload:
        updates["cta_public"] = str(payload.get("cta_public") or "").strip()
    if "cta_direct" in payload:
        updates["cta_direct"] = str(payload.get("cta_direct") or "").strip()
    if "call_policy" in payload:
        updates["call_policy"] = _normalize_call_policy(payload.get("call_policy"))
    if "booking_link" in payload:
        updates["booking_link"] = str(payload.get("booking_link") or "").strip()
    if "payment_link" in payload:
        updates["payment_link"] = str(payload.get("payment_link") or "").strip()
    if "pricing_tier" in payload:
        updates["pricing_tier"] = str(payload.get("pricing_tier") or "").strip()
    if "price_usd" in payload:
        updates["price_usd"] = max(0, int(_coerce_float(payload.get("price_usd"), 0)))
    updates["source"] = "dashboard_api"

    saved = _save_revenue_playbook(updates)
    return jsonify(
        {
            "status": "UPDATED",
            "path": _revenue_playbook_path(),
            "playbook": saved,
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/revenue/targets", methods=["GET", "POST"])
def revenue_targets():
    """Read/update revenue targets used by architecture and execution board."""
    if request.method == "GET":
        log_api_call("GET", "/api/revenue/targets")
        return jsonify(
            {
                "status": "OK",
                "path": _revenue_targets_path(),
                "targets": _load_revenue_targets(),
                "timestamp": utc_iso(),
            }
        )

    payload = request.get_json() or {}
    log_api_call("POST", "/api/revenue/targets", payload)
    current = _load_revenue_targets()
    updates = dict(current)
    if "week_of" in payload:
        updates["week_of"] = str(payload.get("week_of") or "").strip()
    if "weekly_revenue_target" in payload:
        updates["weekly_revenue_target"] = max(0, int(_coerce_float(payload.get("weekly_revenue_target"), 0)))
    if "monthly_revenue_target" in payload:
        updates["monthly_revenue_target"] = max(0, int(_coerce_float(payload.get("monthly_revenue_target"), 0)))
    if "weekly_leads_target" in payload:
        updates["weekly_leads_target"] = max(0, int(_coerce_float(payload.get("weekly_leads_target"), 0)))
    if "weekly_calls_target" in payload:
        updates["weekly_calls_target"] = max(0, int(_coerce_float(payload.get("weekly_calls_target"), 0)))
    if "weekly_closes_target" in payload:
        updates["weekly_closes_target"] = max(0, int(_coerce_float(payload.get("weekly_closes_target"), 0)))
    if "daily_outreach_target" in payload:
        updates["daily_outreach_target"] = max(1, int(_coerce_float(payload.get("daily_outreach_target"), 1)))
    updates["source"] = "dashboard_api"

    saved = _save_revenue_targets(updates)
    return jsonify(
        {
            "status": "UPDATED",
            "path": _revenue_targets_path(),
            "targets": saved,
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


@app.route("/api/revenue/outreach", methods=["POST"])
def update_revenue_outreach_status():
    """Update outreach status for a lead/message (pending/sent/replied)."""
    payload = request.get_json() or {}
    log_api_call("POST", "/api/revenue/outreach", payload)

    lead_id = str(payload.get("lead_id") or "").strip()
    message_key = str(payload.get("message_key") or "").strip()
    status_raw = str(payload.get("status") or "").strip().lower()
    if not lead_id and not message_key:
        log_api_call("POST", "/api/revenue/outreach", payload, "MISSING_LEAD_ID")
        abort(400, description="lead_id or message_key is required.")
    if status_raw not in REVENUE_OUTREACH_STATUSES:
        log_api_call("POST", "/api/revenue/outreach", payload, "INVALID_STATUS")
        abort(400, description="status must be one of: pending, sent, replied")

    source = str(payload.get("source") or "dashboard").strip()
    actor = str(payload.get("actor") or "human").strip()
    notes = str(payload.get("notes") or "").strip()
    key = lead_id or message_key
    entry = _record_revenue_outreach_status(
        key=key,
        lead_id=lead_id,
        status=status_raw,
        source=source,
        actor=actor,
        notes=notes,
    )
    return jsonify(
        {
            "status": "UPDATED",
            "lead_id": lead_id or None,
            "message_key": key,
            "outreach_status": status_raw,
            "entry": entry,
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/revenue/deal-event", methods=["POST"])
def create_revenue_deal_event():
    """Record a deal event and synchronize lead stage/value."""
    payload = request.get_json() or {}
    log_api_call("POST", "/api/revenue/deal-event", payload)

    lead_id = str(payload.get("lead_id") or "").strip()
    event_type = str(payload.get("event_type") or "").strip().lower()
    if not lead_id:
        log_api_call("POST", "/api/revenue/deal-event", payload, "MISSING_LEAD_ID")
        abort(400, description="lead_id is required.")
    if event_type not in REVENUE_DEAL_EVENT_TYPES:
        log_api_call("POST", "/api/revenue/deal-event", payload, "INVALID_EVENT_TYPE")
        abort(400, description="event_type must be one of: proposal_sent, invoice_sent, payment_received, kickoff_scheduled")

    amount = payload.get("amount_usd")
    amount_usd = None if amount is None or str(amount).strip() == "" else _coerce_float(amount, 0.0)
    source = str(payload.get("source") or "dashboard").strip()
    actor = str(payload.get("actor") or "human").strip()
    notes = str(payload.get("notes") or "").strip()
    event = _record_revenue_deal_event(
        lead_id=lead_id,
        event_type=event_type,
        amount_usd=amount_usd,
        source=source,
        actor=actor,
        notes=notes,
    )

    tomorrow = (utc_now().date() + datetime.timedelta(days=1)).isoformat()
    update_payload: dict = {}
    if event_type == "proposal_sent":
        update_payload = {
            "stage": "proposal_sent",
            "next_action": "Follow up on proposal response",
            "next_action_due": tomorrow,
        }
    elif event_type == "invoice_sent":
        update_payload = {
            "stage": "negotiation",
            "next_action": "Confirm invoice receipt and payment timeline",
            "next_action_due": tomorrow,
        }
    elif event_type == "payment_received":
        update_payload = {
            "stage": "won",
            "next_action": "Kickoff scheduled",
            "next_action_due": "",
        }
        if amount_usd is not None:
            update_payload["actual_value"] = amount_usd
    elif event_type == "kickoff_scheduled":
        update_payload = {
            "next_action": "Execute kickoff and delivery plan",
            "next_action_due": "",
        }

    updated = _pipeline_update_lead(lead_id, update_payload)
    if updated is None:
        log_api_call("POST", "/api/revenue/deal-event", payload, "LEAD_NOT_FOUND")
        abort(404, description="Lead not found.")

    return jsonify(
        {
            "status": "UPDATED",
            "event": event,
            "lead": updated,
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/revenue/deal-events", methods=["GET"])
def list_revenue_deal_events():
    """List recent deal events."""
    limit = max(1, min(200, request.args.get("limit", 50, type=int)))
    log_api_call("GET", "/api/revenue/deal-events", {"limit": limit})
    rows = _load_revenue_deal_events(limit=limit)
    return jsonify(
        {
            "status": "OK",
            "count": len(rows),
            "rows": rows,
            "path": _revenue_deal_events_path(),
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/revenue/site-event", methods=["POST"])
def create_revenue_site_event():
    """Capture site funnel telemetry event from FOUNDATION surface."""
    payload = request.get_json() or {}
    log_api_call("POST", "/api/revenue/site-event", payload)

    event_type = str(payload.get("event_type") or "").strip().lower()
    if event_type not in REVENUE_SITE_EVENT_TYPES:
        log_api_call("POST", "/api/revenue/site-event", payload, "INVALID_EVENT_TYPE")
        abort(400, description="event_type must be one of: page_view, cta_click, intake_submit, intake_captured, intake_fallback")
    source = str(payload.get("source") or "foundation_site").strip()
    session_id = str(payload.get("session_id") or "").strip()
    channel = str(payload.get("channel") or "").strip()
    meta = payload.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    entry = _record_revenue_site_event(
        event_type=event_type,
        source=source,
        session_id=session_id,
        channel=channel,
        meta=meta,
    )
    return jsonify(
        {
            "status": "CAPTURED",
            "entry": entry,
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/revenue/site-events", methods=["GET"])
def list_revenue_site_events():
    """List recent site telemetry events."""
    limit = max(1, min(500, request.args.get("limit", 100, type=int)))
    log_api_call("GET", "/api/revenue/site-events", {"limit": limit})
    rows = _load_revenue_site_events(limit=limit)
    return jsonify(
        {
            "status": "OK",
            "count": len(rows),
            "rows": rows,
            "path": _revenue_site_events_path(),
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/revenue/run-loop", methods=["POST"])
def run_revenue_loop():
    """Run revenue loop commands from dashboard (full loop or queue refresh)."""
    payload = request.get_json() or {}
    log_api_call("POST", "/api/revenue/run-loop", payload)

    mode = str(payload.get("mode") or "full").strip().lower()
    if mode not in {"full", "queue"}:
        log_api_call("POST", "/api/revenue/run-loop", payload, "INVALID_MODE")
        abort(400, description="mode must be 'full' or 'queue'")

    if mode == "full":
        commands = [
            [sys.executable, os.path.join(BASE_DIR, "cli.py"), "money-loop"],
        ]
    else:
        commands = [
            [sys.executable, os.path.join(BASE_DIR, "cli.py"), "revenue-action-queue"],
            [sys.executable, os.path.join(BASE_DIR, "cli.py"), "revenue-architecture"],
            [sys.executable, os.path.join(BASE_DIR, "cli.py"), "revenue-execution-board"],
            [sys.executable, os.path.join(BASE_DIR, "cli.py"), "revenue-outreach-pack"],
            [sys.executable, os.path.join(BASE_DIR, "cli.py"), "revenue-followup-queue"],
            [sys.executable, os.path.join(BASE_DIR, "cli.py"), "revenue-eval"],
        ]

    started = utc_now()
    run_results: list[dict] = []
    for command in commands:
        rc = subprocess.call(command, cwd=BASE_DIR, env=os.environ.copy())
        run_results.append({"command": command, "return_code": rc})
        if rc != 0:
            break

    elapsed_ms = int((utc_now() - started).total_seconds() * 1000)
    ok = all(int(item["return_code"]) == 0 for item in run_results) and len(run_results) == len(commands)
    if ok:
        status = "OK"
    else:
        status = "FAILED"
    return jsonify(
        {
            "status": status,
            "mode": mode,
            "started_at": started.isoformat().replace("+00:00", "Z"),
            "elapsed_ms": elapsed_ms,
            "commands": run_results,
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
# AGENT CONSOLE
# ─────────────────────────────────────────────

@app.route("/api/agent-console/commands", methods=["GET"])
def get_agent_console_commands():
    """List governed agent-console commands exposed to dashboard UI."""
    log_api_call("GET", "/api/agent-console/commands")
    command_specs = _agent_console_command_specs()
    constitution, constitution_status = _ensure_agent_constitution(command_specs)
    commands = _agent_console_command_payloads(command_specs, constitution=constitution)
    return jsonify(
        {
            "status": "OK",
            "count": len(commands),
            "commands": commands,
            "constitution": _agent_constitution_public_payload(constitution, constitution_status),
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/agent-console/constitution", methods=["GET"])
def get_agent_console_constitution():
    """Return the active machine-readable constitution used by the agent console."""
    log_api_call("GET", "/api/agent-console/constitution")
    command_specs = _agent_console_command_specs()
    constitution, constitution_status = _ensure_agent_constitution(command_specs)
    return jsonify(
        {
            "status": "OK",
            "constitution_status": constitution_status,
            "constitution_path": _agent_constitution_path(),
            "constitution": constitution,
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/agent-console/messages", methods=["GET"])
def get_agent_console_messages():
    """Return recent agent-console conversation history."""
    limit = max(1, min(200, request.args.get("limit", 60, type=int)))
    log_api_call("GET", "/api/agent-console/messages", {"limit": limit})
    messages = _load_agent_console_history(limit=limit)
    return jsonify(
        {
            "status": "OK",
            "count": len(messages),
            "messages": messages,
            "path": _agent_console_history_path(),
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/agent-console/uploads", methods=["GET"])
def get_agent_console_uploads():
    """Return recent uploaded attachment files from the agent console inbox."""
    limit = max(1, min(200, request.args.get("limit", 40, type=int)))
    log_api_call("GET", "/api/agent-console/uploads", {"limit": limit})
    uploads = _agent_console_recent_uploads(limit=limit)
    return jsonify(
        {
            "status": "OK",
            "count": len(uploads),
            "uploads": uploads,
            "inbox_dir": _agent_console_attachment_inbox_dir(),
            "timestamp": utc_iso(),
        }
    )


@app.route("/api/agent-console/upload", methods=["POST"])
def upload_agent_console_file():
    """Upload a local attachment file into the managed inbox for Phase2 processing."""
    if "file" not in request.files:
        log_api_call("POST", "/api/agent-console/upload", {"error": "missing_file"}, "MISSING_FILE")
        abort(400, description="Missing file upload")
    upload = request.files["file"]
    filename = _sanitize_upload_filename(upload.filename or "")
    if not filename:
        log_api_call("POST", "/api/agent-console/upload", {"error": "empty_filename"}, "INVALID_FILENAME")
        abort(400, description="Invalid filename")

    raw = upload.read()
    size_bytes = len(raw)
    max_bytes = _agent_console_upload_max_bytes()
    if size_bytes > max_bytes:
        log_api_call(
            "POST",
            "/api/agent-console/upload",
            {"filename": filename, "size_bytes": size_bytes, "max_bytes": max_bytes},
            "TOO_LARGE",
        )
        abort(413, description=f"File too large. Max bytes: {max_bytes}")

    inbox_dir = _agent_console_attachment_inbox_dir()
    os.makedirs(inbox_dir, exist_ok=True)
    target_path = os.path.join(inbox_dir, filename)
    final_path = target_path
    stem, ext = os.path.splitext(filename)
    suffix = 1
    while os.path.exists(final_path):
        final_path = os.path.join(inbox_dir, f"{stem}_{suffix}{ext}")
        suffix += 1
    with open(final_path, "wb") as handle:
        handle.write(raw)

    rel = os.path.relpath(final_path, inbox_dir)
    item = {
        "filename": os.path.basename(final_path),
        "relative_path": rel,
        "path": final_path,
        "size_bytes": size_bytes,
        "kind": _agent_attachment_kind(final_path),
        "created_at": utc_iso(),
    }
    _record_agent_console_message(
        role="assistant",
        text=f"Attachment uploaded: {item['filename']} ({item['kind']}, {size_bytes} bytes).",
        status="UPLOADED",
    )
    log_api_call("POST", "/api/agent-console/upload", item, "OK")
    return jsonify({"status": "UPLOADED", "file": item, "inbox_dir": inbox_dir, "timestamp": utc_iso()})


@app.route("/api/agent-console/send", methods=["POST"])
def send_agent_console_message():
    """Accept a dashboard message, route to a safe command, execute, and log outcome."""
    payload = request.get_json() or {}
    log_api_call("POST", "/api/agent-console/send", payload)

    raw_message = str(payload.get("message") or "").strip()
    requested_command_id = str(payload.get("command_id") or "").strip()
    command_specs = _agent_console_command_specs()

    if not raw_message and not requested_command_id:
        log_api_call("POST", "/api/agent-console/send", payload, "MISSING_INPUT")
        abort(400, description="Provide message or command_id")

    if requested_command_id and requested_command_id not in command_specs:
        log_api_call("POST", "/api/agent-console/send", payload, "INVALID_COMMAND")
        abort(400, description="Unknown command_id")

    command_id = requested_command_id
    route_reason = "Command selected from quick actions."
    if not command_id:
        routed = _route_agent_console_intent(raw_message)
        command_id = routed.get("command_id")
        route_reason = routed.get("reason", "No route")

    constitution, constitution_status = _ensure_agent_constitution(command_specs)

    user_text = raw_message or (
        f"Run command: {command_specs[command_id]['label']}"
        if command_id and command_id in command_specs
        else "Dashboard request"
    )
    user_entry = _record_agent_console_message(
        role="user",
        text=user_text,
        status="RECEIVED",
        command_id=command_id,
    )

    policy_gate = _evaluate_agent_console_request(
        message=raw_message,
        command_id=command_id,
        constitution=constitution,
    )
    gate_status = str(policy_gate.get("status") or "ALLOW").upper()
    if gate_status != "ALLOW":
        assistant_text = str(policy_gate.get("message") or "Request blocked by governance policy.")
        assistant_entry = _record_agent_console_message(
            role="assistant",
            text=assistant_text,
            status=gate_status,
            command_id=command_id,
        )
        history = _load_agent_console_history(limit=60)
        return jsonify(
            {
                "status": gate_status,
                "message": assistant_text,
                "route_reason": route_reason,
                "policy_reason": policy_gate.get("reason"),
                "suggested_commands": _agent_console_command_payloads(command_specs, constitution=constitution),
                "constitution": _agent_constitution_public_payload(constitution, constitution_status),
                "user_message": user_entry,
                "assistant_message": assistant_entry,
                "history": history,
                "timestamp": utc_iso(),
            }
        )

    if not command_id:
        assistant_text = (
            "I could not map that request to a governed action yet. "
            "Use a quick action or ask for one of: phase2 refresh, attachment pipeline, resume brand brief, "
            "phase3 refresh, opportunity ranker, opportunity approval queue, approval execution board, money loop, "
            "revenue refresh, second brain loop, social research, world watch, world alerts, github research, "
            "daily briefing, integration readiness, openclaw sync."
        )
        assistant_entry = _record_agent_console_message(
            role="assistant",
            text=assistant_text,
            status="NEEDS_COMMAND",
        )
        history = _load_agent_console_history(limit=60)
        return jsonify(
            {
                "status": "NEEDS_COMMAND",
                "message": assistant_text,
                "route_reason": route_reason,
                "suggested_commands": _agent_console_command_payloads(command_specs, constitution=constitution),
                "constitution": _agent_constitution_public_payload(constitution, constitution_status),
                "user_message": user_entry,
                "assistant_message": assistant_entry,
                "history": history,
                "timestamp": utc_iso(),
            }
        )

    run_result = _run_agent_console_command(command_id, command_specs[command_id])
    assistant_text = _agent_console_result_text(command_specs[command_id], run_result)
    assistant_status = "OK" if run_result.get("status") == "OK" else "FAILED"
    assistant_entry = _record_agent_console_message(
        role="assistant",
        text=assistant_text,
        status=assistant_status,
        command_id=command_id,
        result=run_result,
    )
    history = _load_agent_console_history(limit=60)
    return jsonify(
        {
            "status": run_result.get("status", "FAILED"),
            "command_id": command_id,
            "command_label": command_specs[command_id]["label"],
            "route_reason": route_reason,
            "result": run_result,
            "constitution": _agent_constitution_public_payload(constitution, constitution_status),
            "user_message": user_entry,
            "assistant_message": assistant_entry,
            "history": history,
            "timestamp": utc_iso(),
        }
    )


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────

AGENT_CONSOLE_MAX_OUTPUT_CHARS = 2400
AGENT_CONSOLE_MAX_OUTPUT_LINES = 40
AGENT_CONSOLE_SECRET_PATTERNS = [
    (r"sk-ant-[A-Za-z0-9_-]+", "sk-ant-***REDACTED***"),
    (r"ghp_[A-Za-z0-9]{20,}", "ghp_***REDACTED***"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "xox***REDACTED***"),
    (r"(?i)(api[_-]?key\s*[=:]\s*)([A-Za-z0-9_-]{12,})", r"\1***REDACTED***"),
]
AGENT_ATTACHMENT_DOC_EXTS = {".txt", ".md", ".markdown", ".json", ".pdf", ".doc", ".docx", ".rtf"}
AGENT_ATTACHMENT_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp", ".tiff"}
AGENT_ATTACHMENT_AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aiff"}
AGENT_ATTACHMENT_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AGENT_CONSTITUTION_RISK_BY_COMMAND = {
    "phase2_refresh": "medium",
    "phase3_refresh": "medium",
    "approval_execution_board": "medium",
    "attachment_pipeline": "low",
    "resume_brand_brief": "low",
    "opportunity_ranker": "medium",
    "opportunity_approval_queue": "medium",
    "world_watch": "low",
    "world_watch_alerts": "medium",
    "money_loop": "medium",
    "revenue_refresh": "medium",
    "second_brain_loop": "low",
    "social_research": "low",
    "github_research": "low",
    "briefing": "low",
    "integration_readiness": "low",
    "prediction_ingest": "medium",
    "prediction_lab": "medium",
    "openclaw_sync": "low",
}
AGENT_CONSTITUTION_BLOCK_KEYWORDS = [
    "disable guardrail",
    "disable guardrails",
    "bypass guardrail",
    "bypass policy",
    "ignore policy",
    "ignore approval",
    "remove constitution",
    "delete constitution",
    "show api key",
    "reveal api key",
    "print api key",
    "export private key",
    "send private key",
]
AGENT_CONSTITUTION_APPROVAL_KEYWORDS = [
    "autopilot",
    "auto trade",
    "auto post",
    "mass dm",
    "send payment",
    "wire transfer",
]
AGENT_CONSTITUTION_LIVE_TRADING_KEYWORDS = [
    "live trade",
    "execute trade",
    "place trade",
    "send crypto",
    "buy now",
    "sell now",
]
AGENT_CONSTITUTION_EXTERNAL_WRITE_KEYWORDS = [
    "publish",
    "post to x",
    "post on x",
    "send dm",
    "send message",
    "reply to",
    "tweet",
]
AGENT_CONSTITUTION_VOICE_CAPTURE_KEYWORDS = [
    "voice activity",
    "always listen",
    "record voice",
    "save voice",
]
AGENT_CONSTITUTION_SELF_MODIFY_KEYWORDS = [
    "rewrite yourself",
    "self modify",
    "change your rules",
    "change your constitution",
]


def _agent_console_history_path() -> str:
    return os.environ.get(
        "PERMANENCE_AGENT_CONSOLE_HISTORY_PATH",
        os.path.join(PATHS["working"], "agent_console_history.jsonl"),
    )


def _agent_console_attachment_inbox_dir() -> str:
    return os.environ.get(
        "PERMANENCE_ATTACHMENT_INBOX_DIR",
        os.path.join(BASE_DIR, "memory", "inbox", "attachments"),
    )


def _agent_console_upload_max_bytes() -> int:
    limit_mb = max(1, int(_coerce_float(os.environ.get("PERMANENCE_ATTACHMENT_UPLOAD_MAX_MB", "64"), 64.0)))
    return limit_mb * 1024 * 1024


def _sanitize_upload_filename(name: str) -> str:
    cleaned = os.path.basename(str(name or "").strip())
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("._")
    if not cleaned:
        return ""
    if len(cleaned) > 160:
        root, ext = os.path.splitext(cleaned)
        cleaned = root[:140] + ext[:20]
    return cleaned


def _agent_attachment_kind(path: str) -> str:
    ext = os.path.splitext(str(path or ""))[1].lower()
    if ext in AGENT_ATTACHMENT_DOC_EXTS:
        return "document"
    if ext in AGENT_ATTACHMENT_IMAGE_EXTS:
        return "image"
    if ext in AGENT_ATTACHMENT_AUDIO_EXTS:
        return "audio"
    if ext in AGENT_ATTACHMENT_VIDEO_EXTS:
        return "video"
    return "other"


def _agent_console_recent_uploads(limit: int = 40) -> list[dict]:
    inbox_dir = _agent_console_attachment_inbox_dir()
    if not os.path.isdir(inbox_dir):
        return []
    rows: list[dict] = []
    for root, _, files in os.walk(inbox_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            rows.append(
                {
                    "filename": name,
                    "relative_path": os.path.relpath(path, inbox_dir),
                    "path": path,
                    "size_bytes": int(stat.st_size),
                    "modified_at": timestamp_to_utc_iso(stat.st_mtime),
                    "kind": _agent_attachment_kind(path),
                }
            )
    rows.sort(key=lambda row: str(row.get("modified_at", "")), reverse=True)
    return rows[: max(1, limit)]


def _agent_constitution_path() -> str:
    return os.environ.get(
        "PERMANENCE_AGENT_CONSTITUTION_PATH",
        os.path.join(PATHS["working"], "agent_constitution.json"),
    )


def _agent_constitution_default_command_policy(command_id: str, spec: dict) -> dict:
    risk_tier = AGENT_CONSTITUTION_RISK_BY_COMMAND.get(command_id, "low")
    return {
        "enabled": True,
        "execution": "allow",
        "risk_tier": risk_tier,
        "notes": str(spec.get("description") or "").strip(),
    }


def _default_agent_constitution(command_specs: dict[str, dict]) -> dict:
    command_policies: dict[str, dict] = {}
    for command_id, spec in command_specs.items():
        command_policies[command_id] = _agent_constitution_default_command_policy(command_id, spec)
    return {
        "version": "1.0",
        "created_at": utc_iso(),
        "identity_statement": (
            "PermanenceOS is a governed second-brain and execution copilot. "
            "It must optimize long-term outcomes with safety, truth, and human authority first."
        ),
        "core_objectives": [
            "Increase owner clarity, output quality, and strategic consistency.",
            "Create sustainable income streams through research, packaging, and execution discipline.",
            "Protect health, reputation, legal posture, and relationship integrity while scaling.",
        ],
        "non_negotiables": [
            "No autonomous real-money trades, payments, or transfers.",
            "No secret exfiltration, credential display, or policy bypass attempts.",
            "No autonomous outbound publishing/messages without explicit human approval.",
            "No self-modification of governance without human-written change approval.",
        ],
        "privacy": {
            "store_raw_voice": False,
            "store_transcripts": "opt_in",
            "message_retention_days": 30,
        },
        "capability_toggles": {
            "allow_external_reads": True,
            "allow_external_writes": False,
            "allow_live_trading": False,
            "allow_voice_mode": False,
            "allow_self_modification": False,
        },
        "danger_patterns": {
            "block_keywords": list(AGENT_CONSTITUTION_BLOCK_KEYWORDS),
            "require_approval_keywords": list(AGENT_CONSTITUTION_APPROVAL_KEYWORDS),
        },
        "command_policies": command_policies,
        "updated_at": utc_iso(),
    }


def _normalize_agent_constitution(payload: dict, command_specs: dict[str, dict]) -> dict:
    merged = _default_agent_constitution(command_specs)
    if not isinstance(payload, dict):
        return merged
    for key in ["version", "identity_statement", "created_at", "updated_at"]:
        if key in payload and payload.get(key):
            merged[key] = payload.get(key)
    for key in ["core_objectives", "non_negotiables"]:
        if isinstance(payload.get(key), list):
            merged[key] = [str(item) for item in payload.get(key) if str(item).strip()]
    if isinstance(payload.get("privacy"), dict):
        merged["privacy"].update(payload.get("privacy"))
    if isinstance(payload.get("capability_toggles"), dict):
        merged["capability_toggles"].update(payload.get("capability_toggles"))
    if isinstance(payload.get("danger_patterns"), dict):
        incoming = payload.get("danger_patterns")
        if isinstance(incoming.get("block_keywords"), list):
            merged["danger_patterns"]["block_keywords"] = [
                str(item).strip().lower() for item in incoming.get("block_keywords") if str(item).strip()
            ]
        if isinstance(incoming.get("require_approval_keywords"), list):
            merged["danger_patterns"]["require_approval_keywords"] = [
                str(item).strip().lower() for item in incoming.get("require_approval_keywords") if str(item).strip()
            ]

    incoming_policies = payload.get("command_policies")
    if isinstance(incoming_policies, dict):
        for command_id, spec in command_specs.items():
            default_policy = _agent_constitution_default_command_policy(command_id, spec)
            override = incoming_policies.get(command_id)
            if not isinstance(override, dict):
                merged["command_policies"][command_id] = default_policy
                continue
            policy = dict(default_policy)
            policy["enabled"] = _coerce_bool(override.get("enabled"), policy["enabled"])
            execution = str(override.get("execution") or policy["execution"]).strip().lower()
            if execution not in {"allow", "approval_only", "deny"}:
                execution = policy["execution"]
            policy["execution"] = execution
            risk_tier = str(override.get("risk_tier") or policy["risk_tier"]).strip().lower()
            if risk_tier not in {"low", "medium", "high"}:
                risk_tier = policy["risk_tier"]
            policy["risk_tier"] = risk_tier
            policy["notes"] = str(override.get("notes") or policy["notes"]).strip()
            merged["command_policies"][command_id] = policy
    return merged


def _ensure_agent_constitution(command_specs: dict[str, dict]) -> tuple[dict, str]:
    path = _agent_constitution_path()
    existing = _read_json_file(path)
    if isinstance(existing, dict) and existing:
        normalized = _normalize_agent_constitution(existing, command_specs)
        if normalized != existing:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(normalized, f, indent=2)
                f.write("\n")
            return normalized, "updated"
        return normalized, "existing"
    payload = _default_agent_constitution(command_specs)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return payload, "written"


def _agent_constitution_public_payload(constitution: dict, status: str) -> dict:
    return {
        "status": status,
        "path": _agent_constitution_path(),
        "version": constitution.get("version"),
        "updated_at": constitution.get("updated_at"),
        "capability_toggles": constitution.get("capability_toggles", {}),
        "non_negotiables": constitution.get("non_negotiables", []),
        "command_policy_count": len(constitution.get("command_policies", {})),
    }


def _contains_any_phrase(text: str, phrases: list[str]) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    for phrase in phrases:
        token = str(phrase or "").strip().lower()
        if token and token in normalized:
            return True
    return False


def _evaluate_agent_console_request(message: str, command_id: Optional[str], constitution: dict) -> dict:
    text = str(message or "").strip().lower()
    command_policies = constitution.get("command_policies", {}) if isinstance(constitution, dict) else {}
    capability_toggles = constitution.get("capability_toggles", {}) if isinstance(constitution, dict) else {}
    danger_patterns = constitution.get("danger_patterns", {}) if isinstance(constitution, dict) else {}

    block_keywords = [
        str(item).strip().lower()
        for item in (danger_patterns.get("block_keywords") or AGENT_CONSTITUTION_BLOCK_KEYWORDS)
        if str(item).strip()
    ]
    approval_keywords = [
        str(item).strip().lower()
        for item in (danger_patterns.get("require_approval_keywords") or AGENT_CONSTITUTION_APPROVAL_KEYWORDS)
        if str(item).strip()
    ]

    if _contains_any_phrase(text, block_keywords):
        return {
            "status": "BLOCKED_BY_CONSTITUTION",
            "reason": "blocked_keyword",
            "message": (
                "Request blocked by Agent Constitution. This system will not disable safeguards, expose secrets, "
                "or bypass approval controls."
            ),
        }

    if not _coerce_bool(capability_toggles.get("allow_live_trading"), False) and _contains_any_phrase(
        text, AGENT_CONSTITUTION_LIVE_TRADING_KEYWORDS
    ):
        return {
            "status": "BLOCKED_BY_CONSTITUTION",
            "reason": "live_trading_disabled",
            "message": (
                "Live trading is disabled by constitution. Use prediction research outputs for manual review only."
            ),
        }

    if not _coerce_bool(capability_toggles.get("allow_external_writes"), False) and _contains_any_phrase(
        text, AGENT_CONSTITUTION_EXTERNAL_WRITE_KEYWORDS
    ):
        return {
            "status": "NEEDS_APPROVAL",
            "reason": "external_write_requires_approval",
            "message": (
                "External publishing/messaging is in manual-approval mode. Draft first, then approve before sending."
            ),
        }

    if not _coerce_bool(capability_toggles.get("allow_voice_mode"), False) and _contains_any_phrase(
        text, AGENT_CONSTITUTION_VOICE_CAPTURE_KEYWORDS
    ):
        return {
            "status": "NEEDS_APPROVAL",
            "reason": "voice_mode_disabled",
            "message": (
                "Voice capture is disabled by constitution. Enable voice mode explicitly before recording behavior."
            ),
        }

    if not _coerce_bool(capability_toggles.get("allow_self_modification"), False) and _contains_any_phrase(
        text, AGENT_CONSTITUTION_SELF_MODIFY_KEYWORDS
    ):
        return {
            "status": "BLOCKED_BY_CONSTITUTION",
            "reason": "self_modification_disabled",
            "message": (
                "Self-modification is blocked by constitution. Governance changes require explicit human-written edits."
            ),
        }

    if command_id:
        policy = command_policies.get(command_id, {})
        if isinstance(policy, dict):
            if not _coerce_bool(policy.get("enabled"), True):
                return {
                    "status": "BLOCKED_BY_CONSTITUTION",
                    "reason": "command_disabled",
                    "message": f"Command '{command_id}' is disabled by constitution policy.",
                }
            execution = str(policy.get("execution") or "allow").strip().lower()
            if execution == "deny":
                return {
                    "status": "BLOCKED_BY_CONSTITUTION",
                    "reason": "command_denied",
                    "message": f"Command '{command_id}' is denied by constitution policy.",
                }
            if execution == "approval_only":
                return {
                    "status": "NEEDS_APPROVAL",
                    "reason": "command_requires_approval",
                    "message": f"Command '{command_id}' is approval-only. Review and approve before running.",
                }

    if _contains_any_phrase(text, approval_keywords):
        return {
            "status": "NEEDS_APPROVAL",
            "reason": "approval_keyword",
            "message": "Request requires manual approval under constitution rules.",
        }

    return {"status": "ALLOW", "reason": "allowed"}


def _agent_console_command_specs() -> dict[str, dict]:
    cli_path = os.path.join(BASE_DIR, "cli.py")
    return {
        "phase2_refresh": {
            "label": "Run Phase2 Refresh (Attachments + Resume/Brand)",
            "description": "Run attachment pipeline, doc ingest, life brief, resume/brand brief, and second-brain report.",
            "order": 5,
            "commands": [[sys.executable, cli_path, "phase2-refresh"]],
            "aliases": ["phase2", "phase 2", "personal os refresh", "resume brand refresh"],
            "artifacts": [
                {"label": "Phase2 refresh", "scope": "output", "pattern": "phase2_refresh_latest.md"},
                {"label": "Attachment pipeline", "scope": "output", "pattern": "attachment_pipeline_latest.md"},
                {"label": "Resume + brand brief", "scope": "output", "pattern": "resume_brand_brief_latest.md"},
                {"label": "Second brain report", "scope": "output", "pattern": "second_brain_report_latest.md"},
            ],
        },
        "phase3_refresh": {
            "label": "Run Phase3 Refresh (Opportunities + Approval Queue)",
            "description": "Refresh research + world-watch signals, rank opportunities, queue manual approvals, and refresh second-brain report.",
            "order": 8,
            "commands": [[sys.executable, cli_path, "phase3-refresh"]],
            "aliases": ["phase3", "phase 3", "phase3 refresh", "opportunity refresh"],
            "artifacts": [
                {"label": "Phase3 refresh", "scope": "output", "pattern": "phase3_refresh_latest.md"},
                {"label": "World watch", "scope": "output", "pattern": "world_watch_latest.md"},
                {"label": "World watch alerts", "scope": "output", "pattern": "world_watch_alerts_latest.md"},
                {"label": "Opportunity ranker", "scope": "output", "pattern": "opportunity_ranker_latest.md"},
                {"label": "Opportunity approval queue", "scope": "output", "pattern": "opportunity_approval_queue_latest.md"},
            ],
        },
        "attachment_pipeline": {
            "label": "Run Attachment Pipeline",
            "description": "Index uploaded files (docs/images/audio/video) and refresh transcription queue.",
            "order": 6,
            "commands": [[sys.executable, cli_path, "attachment-pipeline"]],
            "aliases": ["attachments", "attachment pipeline", "scan uploads", "attachment scan", "file inbox"],
            "artifacts": [
                {"label": "Attachment pipeline", "scope": "output", "pattern": "attachment_pipeline_latest.md"},
                {"label": "Transcription queue", "scope": "working", "pattern": "transcription_queue.json"},
            ],
        },
        "resume_brand_brief": {
            "label": "Run Resume + Brand Brief",
            "description": "Generate actionable resume bullets and brand system actions from current context.",
            "order": 7,
            "commands": [[sys.executable, cli_path, "resume-brand-brief"]],
            "aliases": ["resume brief", "brand brief", "resume brand", "profile brand"],
            "artifacts": [
                {"label": "Resume + brand brief", "scope": "output", "pattern": "resume_brand_brief_latest.md"},
            ],
        },
        "money_loop": {
            "label": "Run Money Loop",
            "description": "Run full revenue loop (queue, board, outreach, follow-up, eval, backups).",
            "order": 10,
            "commands": [[sys.executable, cli_path, "money-loop"]],
            "aliases": ["money loop", "run money loop", "revenue loop", "run revenue loop"],
            "artifacts": [
                {"label": "Revenue execution board", "scope": "output", "pattern": "revenue_execution_board_latest.md"},
                {"label": "Revenue eval", "scope": "output", "pattern": "revenue_eval_latest.md"},
                {"label": "Cost recovery", "scope": "output", "pattern": "revenue_cost_recovery_latest.md"},
            ],
        },
        "revenue_refresh": {
            "label": "Refresh Revenue Queue + Board",
            "description": "Refresh queue, architecture, execution board, outreach pack, follow-up queue, and eval.",
            "order": 20,
            "commands": [
                [sys.executable, cli_path, "revenue-action-queue"],
                [sys.executable, cli_path, "revenue-architecture"],
                [sys.executable, cli_path, "revenue-execution-board"],
                [sys.executable, cli_path, "revenue-outreach-pack"],
                [sys.executable, cli_path, "revenue-followup-queue"],
                [sys.executable, cli_path, "revenue-eval"],
            ],
            "aliases": ["revenue refresh", "refresh revenue", "refresh queue", "revenue queue"],
            "artifacts": [
                {"label": "Revenue queue", "scope": "output", "pattern": "revenue_action_queue_latest.md"},
                {"label": "Revenue architecture", "scope": "output", "pattern": "revenue_architecture_latest.md"},
                {"label": "Revenue execution board", "scope": "output", "pattern": "revenue_execution_board_latest.md"},
                {"label": "Revenue outreach pack", "scope": "output", "pattern": "revenue_outreach_pack_latest.md"},
                {"label": "Revenue follow-up queue", "scope": "output", "pattern": "revenue_followup_queue_latest.md"},
                {"label": "Revenue eval", "scope": "output", "pattern": "revenue_eval_latest.md"},
            ],
        },
        "second_brain_loop": {
            "label": "Run Second Brain Loop",
            "description": "Run life + research + side-business + prediction + clipping pipeline and unified report.",
            "order": 30,
            "commands": [[sys.executable, cli_path, "second-brain-loop"]],
            "aliases": ["second brain", "second brain loop", "life os loop", "run second brain"],
            "artifacts": [
                {"label": "Second brain report", "scope": "output", "pattern": "second_brain_report_latest.md"},
            ],
        },
        "social_research": {
            "label": "Run Social Research Ingest",
            "description": "Ingest and rank social signals using read-only connector feeds.",
            "order": 40,
            "commands": [[sys.executable, cli_path, "social-research-ingest"]],
            "aliases": ["social research", "x research", "twitter research", "social ingest"],
            "artifacts": [
                {"label": "Social research report", "scope": "output", "pattern": "social_research_ingest_latest.md"},
            ],
        },
        "world_watch": {
            "label": "Run World Watch Ingest",
            "description": "Ingest global conflict/weather/natural-event intelligence and rank alerts.",
            "order": 41,
            "commands": [[sys.executable, cli_path, "world-watch"]],
            "aliases": ["world watch", "global monitor", "world monitor", "geopolitical monitor"],
            "artifacts": [
                {"label": "World watch report", "scope": "output", "pattern": "world_watch_latest.md"},
            ],
        },
        "world_watch_alerts": {
            "label": "Build World Watch Alerts",
            "description": "Generate world-watch alert message draft and optional channel dispatch.",
            "order": 42,
            "commands": [[sys.executable, cli_path, "world-watch-alerts"]],
            "aliases": ["world alerts", "global alerts", "alert digest", "risk alerts"],
            "artifacts": [
                {"label": "World watch alerts", "scope": "output", "pattern": "world_watch_alerts_latest.md"},
            ],
        },
        "opportunity_ranker": {
            "label": "Run Opportunity Ranker",
            "description": "Rank opportunities across social, GitHub, prediction, and portfolio signals.",
            "order": 43,
            "commands": [[sys.executable, cli_path, "opportunity-ranker"]],
            "aliases": ["opportunity ranker", "rank opportunities", "opportunity scoring", "phase3 ranking"],
            "artifacts": [
                {"label": "Opportunity ranker", "scope": "output", "pattern": "opportunity_ranker_latest.md"},
            ],
        },
        "opportunity_approval_queue": {
            "label": "Run Opportunity Approval Queue",
            "description": "Queue ranked opportunities into the human approval inbox.",
            "order": 44,
            "commands": [[sys.executable, cli_path, "opportunity-approval-queue"]],
            "aliases": ["opportunity queue", "approval queue", "queue opportunities", "phase3 queue"],
            "artifacts": [
                {"label": "Opportunity approval queue", "scope": "output", "pattern": "opportunity_approval_queue_latest.md"},
            ],
        },
        "approval_execution_board": {
            "label": "Build Approved Execution Board",
            "description": "Convert approved queue items into a prioritized execution board.",
            "order": 45,
            "commands": [[sys.executable, cli_path, "approval-execution-board"]],
            "aliases": ["approved board", "approved execution", "execution board", "run approved tasks"],
            "artifacts": [
                {"label": "Approval execution board", "scope": "output", "pattern": "approval_execution_board_latest.md"},
            ],
        },
        "github_research": {
            "label": "Run GitHub Research Ingest",
            "description": "Read open repo issues/PRs and generate prioritized action suggestions.",
            "order": 50,
            "commands": [[sys.executable, cli_path, "github-research-ingest"]],
            "aliases": ["github research", "repo research", "github ingest"],
            "artifacts": [
                {"label": "GitHub research report", "scope": "output", "pattern": "github_research_ingest_latest.md"},
            ],
        },
        "briefing": {
            "label": "Generate Daily Briefing",
            "description": "Generate the latest system briefing report for command context.",
            "order": 60,
            "commands": [[sys.executable, cli_path, "briefing"]],
            "aliases": ["briefing", "daily briefing", "generate briefing"],
            "artifacts": [
                {"label": "Latest briefing", "scope": "output", "pattern": "briefings/*"},
            ],
        },
        "integration_readiness": {
            "label": "Run Integration Readiness",
            "description": "Check keys, connectors, and external integration readiness.",
            "order": 70,
            "commands": [[sys.executable, cli_path, "integration-readiness"]],
            "aliases": ["integration readiness", "readiness", "readiness check"],
            "artifacts": [
                {"label": "Integration readiness", "scope": "output", "pattern": "integration_readiness_latest.md"},
            ],
        },
        "prediction_ingest": {
            "label": "Run Prediction Ingest (News + Telegram)",
            "description": "Refresh prediction signals from news feeds and configured Telegram channels.",
            "order": 75,
            "commands": [[sys.executable, cli_path, "prediction-ingest"]],
            "aliases": ["prediction ingest", "telegram", "telegram ingest", "iccmafia", "trade signals"],
            "artifacts": [
                {"label": "Prediction ingest", "scope": "output", "pattern": "prediction_ingest_latest.md"},
            ],
        },
        "prediction_lab": {
            "label": "Run Prediction Lab (Manual Review Queue)",
            "description": "Generate ranked prediction candidates and risk-capped suggested stakes (advisory only).",
            "order": 76,
            "commands": [[sys.executable, cli_path, "prediction-lab"]],
            "aliases": ["prediction lab", "trade recommendations", "manual review trades", "paper trade ideas"],
            "artifacts": [
                {"label": "Prediction lab", "scope": "output", "pattern": "prediction_lab_latest.md"},
            ],
        },
        "openclaw_sync": {
            "label": "Run OpenClaw Sync",
            "description": "Capture OpenClaw status/health and update health state snapshot.",
            "order": 80,
            "commands": [[sys.executable, cli_path, "openclaw-sync"]],
            "aliases": ["openclaw", "open claw", "openclaw sync", "sync openclaw"],
            "artifacts": [
                {"label": "OpenClaw health state", "scope": "tool", "pattern": "openclaw_health_state.json"},
            ],
        },
    }


def _agent_console_command_payloads(command_specs: dict[str, dict], constitution: Optional[dict] = None) -> list[dict]:
    command_policies = {}
    if isinstance(constitution, dict):
        command_policies = constitution.get("command_policies", {}) or {}
    rows: list[dict] = []
    for command_id, spec in command_specs.items():
        policy = command_policies.get(command_id, {}) if isinstance(command_policies, dict) else {}
        rows.append(
            {
                "id": command_id,
                "label": spec.get("label", command_id),
                "description": spec.get("description", ""),
                "order": int(spec.get("order", 999)),
                "aliases": list(spec.get("aliases", [])),
                "policy": {
                    "enabled": _coerce_bool(policy.get("enabled"), True),
                    "execution": str(policy.get("execution") or "allow").strip().lower(),
                    "risk_tier": str(policy.get("risk_tier") or AGENT_CONSTITUTION_RISK_BY_COMMAND.get(command_id, "low")).strip().lower(),
                },
            }
        )
    rows.sort(key=lambda row: row.get("order", 999))
    return rows


def _route_agent_console_intent(message: str) -> dict[str, Optional[str]]:
    text = str(message or "").strip().lower()
    if not text:
        return {"command_id": None, "reason": "Empty request"}

    slash_map = {
        "/phase2": "phase2_refresh",
        "/phase3": "phase3_refresh",
        "/attachments": "attachment_pipeline",
        "/resume": "resume_brand_brief",
        "/brand": "resume_brand_brief",
        "/opportunity": "opportunity_ranker",
        "/opportunities": "opportunity_ranker",
        "/approval-queue": "opportunity_approval_queue",
        "/queue-opps": "opportunity_approval_queue",
        "/approved-board": "approval_execution_board",
        "/approved": "approval_execution_board",
        "/world": "world_watch",
        "/world-alerts": "world_watch_alerts",
        "/money": "money_loop",
        "/money-loop": "money_loop",
        "/revenue": "revenue_refresh",
        "/refresh": "revenue_refresh",
        "/brain": "second_brain_loop",
        "/second-brain": "second_brain_loop",
        "/social": "social_research",
        "/github": "github_research",
        "/briefing": "briefing",
        "/readiness": "integration_readiness",
        "/telegram": "prediction_ingest",
        "/prediction": "prediction_lab",
        "/trades": "prediction_lab",
        "/openclaw": "openclaw_sync",
    }
    for slash, command_id in slash_map.items():
        if text.startswith(slash):
            return {"command_id": command_id, "reason": f"Matched slash command {slash}"}

    command_specs = _agent_console_command_specs()
    for command_id, spec in sorted(command_specs.items(), key=lambda item: int(item[1].get("order", 999))):
        aliases = [str(alias).strip().lower() for alias in spec.get("aliases", []) if str(alias).strip()]
        for alias in aliases:
            if alias and alias in text:
                return {"command_id": command_id, "reason": f"Matched alias '{alias}'"}

    return {"command_id": None, "reason": "No safe command match found"}


def _sanitize_agent_console_output(text: str) -> str:
    cleaned = (text or "").replace("\r", "").strip()
    if not cleaned:
        return ""
    for pattern, replacement in AGENT_CONSOLE_SECRET_PATTERNS:
        cleaned = re.sub(pattern, replacement, cleaned)
    lines = cleaned.splitlines()
    if len(lines) > AGENT_CONSOLE_MAX_OUTPUT_LINES:
        lines = ["...(truncated)..."] + lines[-AGENT_CONSOLE_MAX_OUTPUT_LINES:]
    cleaned = "\n".join(lines)
    if len(cleaned) > AGENT_CONSOLE_MAX_OUTPUT_CHARS:
        cleaned = "...(truncated)...\n" + cleaned[-AGENT_CONSOLE_MAX_OUTPUT_CHARS:]
    return cleaned


def _resolve_agent_console_artifacts(artifact_specs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in artifact_specs:
        pattern = str(item.get("pattern") or "").strip()
        if not pattern:
            continue
        scope = str(item.get("scope") or "output").strip().lower()
        if scope == "tool":
            path = _latest_tool_file(pattern)
        elif scope == "working":
            path = _latest_working_file(pattern)
        else:
            path = _latest_output_file(pattern)
        if not path:
            continue
        rows.append(
            {
                "label": str(item.get("label") or pattern),
                "path": path,
                "scope": scope,
            }
        )
    return rows


def _run_agent_console_command(command_id: str, spec: dict) -> dict:
    commands = spec.get("commands") or []
    started = utc_now()
    started_iso = started.isoformat().replace("+00:00", "Z")
    timeout_sec = int(spec.get("timeout_sec", 900))
    command_runs: list[dict] = []
    previews: list[str] = []
    status = "OK"
    return_code = 0

    for command in commands:
        try:
            proc = subprocess.run(
                command,
                cwd=BASE_DIR,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            return_code = int(proc.returncode)
            combined = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
            preview = _sanitize_agent_console_output(combined)
        except subprocess.TimeoutExpired as exc:
            return_code = 124
            timeout_output = "\n".join(str(part) for part in [exc.stdout, exc.stderr] if part)
            preview = _sanitize_agent_console_output(f"Command timed out after {timeout_sec}s.\n{timeout_output}")
            status = "FAILED"
            command_runs.append({"command": command, "return_code": return_code, "preview": preview})
            if preview:
                previews.append(f"$ {' '.join(command)}\n{preview}")
            break
        except OSError as exc:
            return_code = 127
            preview = _sanitize_agent_console_output(f"Command launch failed: {exc}")
            status = "FAILED"
            command_runs.append({"command": command, "return_code": return_code, "preview": preview})
            if preview:
                previews.append(f"$ {' '.join(command)}\n{preview}")
            break

        command_runs.append({"command": command, "return_code": return_code, "preview": preview})
        if preview:
            previews.append(f"$ {' '.join(command)}\n{preview}")
        if return_code != 0:
            status = "FAILED"
            break

    elapsed_ms = int((utc_now() - started).total_seconds() * 1000)
    artifacts = _resolve_agent_console_artifacts(spec.get("artifacts") or [])
    preview = _sanitize_agent_console_output("\n\n".join(previews))
    return {
        "status": status,
        "command_id": command_id,
        "commands": command_runs,
        "return_code": return_code,
        "started_at": started_iso,
        "elapsed_ms": elapsed_ms,
        "artifacts": artifacts,
        "preview": preview,
    }


def _agent_console_result_text(spec: dict, result: dict) -> str:
    label = str(spec.get("label") or "Command")
    status = str(result.get("status") or "FAILED").upper()
    elapsed_ms = int(result.get("elapsed_ms") or 0)
    header = f"{label} {status.lower()} in {elapsed_ms}ms."
    artifacts = result.get("artifacts") or []
    artifact_lines = [
        f"- {item.get('label', 'Artifact')}: {item.get('path', '')}"
        for item in artifacts
        if isinstance(item, dict)
    ]
    preview = str(result.get("preview") or "").strip()
    blocks: list[str] = [header]
    if artifact_lines:
        blocks.append("Latest artifacts:\n" + "\n".join(artifact_lines))
    if preview:
        blocks.append("Output tail:\n" + preview)
    return "\n\n".join(blocks).strip()


def _record_agent_console_message(
    *,
    role: str,
    text: str,
    status: str,
    command_id: Optional[str] = None,
    result: Optional[dict] = None,
) -> dict:
    created_at = utc_iso()
    raw_text = str(text or "").strip()
    message_text = _sanitize_agent_console_output(raw_text) or raw_text
    digest = hashlib.sha1(f"{created_at}|{role}|{message_text}".encode("utf-8")).hexdigest()[:12]
    entry = {
        "id": f"AC-{digest}",
        "created_at": created_at,
        "role": role,
        "status": status,
        "text": message_text,
    }
    if command_id:
        entry["command_id"] = command_id
    if isinstance(result, dict):
        entry["result"] = {
            "status": result.get("status"),
            "return_code": result.get("return_code"),
            "elapsed_ms": result.get("elapsed_ms"),
            "artifacts": result.get("artifacts", []),
        }
    _append_jsonl(_agent_console_history_path(), entry)
    return entry


def _load_agent_console_history(limit: int = 60) -> list[dict]:
    path = _agent_console_history_path()
    if not os.path.exists(path):
        return []
    rows: list[dict] = []
    try:
        with open(path) as f:
            for line in f:
                payload = line.strip()
                if not payload:
                    continue
                try:
                    item = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
    except OSError:
        return []
    if limit <= 0:
        return rows
    return rows[-limit:]

REVENUE_STAGE_PROB = {
    "lead": 0.10,
    "qualified": 0.25,
    "call_scheduled": 0.40,
    "proposal_sent": 0.60,
    "negotiation": 0.75,
    "won": 1.00,
    "lost": 0.00,
}
REVENUE_OUTREACH_STATUSES = {"pending", "sent", "replied"}
REVENUE_DEAL_EVENT_TYPES = {"proposal_sent", "invoice_sent", "payment_received", "kickoff_scheduled"}
REVENUE_SITE_EVENT_TYPES = {"page_view", "cta_click", "intake_submit", "intake_captured", "intake_fallback"}
REVENUE_CALL_POLICIES = {"recommended", "required", "direct_pay"}


def _intake_path() -> str:
    return os.environ.get(
        "PERMANENCE_REVENUE_INTAKE_PATH",
        os.path.join(PATHS["working"], "revenue_intake.jsonl"),
    )


def _revenue_playbook_path() -> str:
    return os.environ.get(
        "PERMANENCE_REVENUE_PLAYBOOK_PATH",
        os.path.join(PATHS["working"], "revenue_playbook.json"),
    )


def _revenue_targets_path() -> str:
    return os.environ.get(
        "PERMANENCE_REVENUE_TARGETS_PATH",
        os.path.join(PATHS["working"], "revenue_targets.json"),
    )


def _revenue_deal_events_path() -> str:
    return os.environ.get(
        "PERMANENCE_REVENUE_DEAL_EVENTS_PATH",
        os.path.join(PATHS["working"], "revenue_deal_events.jsonl"),
    )


def _revenue_site_events_path() -> str:
    return os.environ.get(
        "PERMANENCE_REVENUE_SITE_EVENTS_PATH",
        os.path.join(PATHS["working"], "revenue_site_events.jsonl"),
    )


def _normalize_call_policy(value: object) -> str:
    policy = str(value or "").strip().lower()
    if policy in REVENUE_CALL_POLICIES:
        return policy
    return "recommended"


def _default_revenue_playbook() -> dict:
    return {
        "offer_name": "Permanence OS Foundation Setup",
        "offer_promise": "Install and operationalize a governed AI operating system on a client's Mac in 7 days.",
        "delivery_window_days": 7,
        "cta_keyword": "FOUNDATION",
        "cta_public": 'DM me "FOUNDATION".',
        "cta_direct": 'If you want this set up for you, DM "FOUNDATION" and I will send fit-call + direct-checkout options.',
        "call_policy": "recommended",
        "booking_link": str(os.environ.get("PERMANENCE_BOOKING_LINK", "")).strip(),
        "payment_link": str(os.environ.get("PERMANENCE_PAYMENT_LINK", "")).strip(),
        "pricing_tier": "Core",
        "price_usd": 1500,
        "updated_at": utc_iso(),
        "source": "dashboard_default",
    }


def _load_revenue_playbook() -> dict:
    default = _default_revenue_playbook()
    path = _revenue_playbook_path()
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(payload, dict):
        return default
    merged = dict(default)
    merged.update(payload)
    merged["call_policy"] = _normalize_call_policy(merged.get("call_policy"))
    return merged


def _save_revenue_playbook(playbook: dict) -> dict:
    path = _revenue_playbook_path()
    merged = dict(_default_revenue_playbook())
    merged.update(playbook or {})
    merged["updated_at"] = utc_iso()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")
    return merged


def _default_revenue_targets() -> dict:
    weekly_revenue_target = int(os.environ.get("PERMANENCE_REVENUE_WEEKLY_TARGET", "3000"))
    monthly_revenue_target = int(os.environ.get("PERMANENCE_REVENUE_MONTHLY_TARGET", str(max(12000, weekly_revenue_target * 4))))
    week_start = datetime.datetime.now().date() - datetime.timedelta(days=datetime.datetime.now().date().weekday())
    return {
        "week_of": week_start.isoformat(),
        "weekly_revenue_target": weekly_revenue_target,
        "monthly_revenue_target": monthly_revenue_target,
        "weekly_leads_target": int(os.environ.get("PERMANENCE_REVENUE_WEEKLY_LEADS_TARGET", "10")),
        "weekly_calls_target": int(os.environ.get("PERMANENCE_REVENUE_WEEKLY_CALLS_TARGET", "5")),
        "weekly_closes_target": int(os.environ.get("PERMANENCE_REVENUE_WEEKLY_CLOSES_TARGET", "2")),
        "daily_outreach_target": int(os.environ.get("PERMANENCE_REVENUE_DAILY_OUTREACH_TARGET", "10")),
        "updated_at": utc_iso(),
        "source": "dashboard_default",
    }


def _load_revenue_targets() -> dict:
    default = _default_revenue_targets()
    path = _revenue_targets_path()
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(payload, dict):
        return default
    merged = dict(default)
    merged.update(payload)
    return merged


def _save_revenue_targets(targets: dict) -> dict:
    path = _revenue_targets_path()
    merged = dict(_default_revenue_targets())
    merged.update(targets or {})
    merged["updated_at"] = utc_iso()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")
    return merged


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


def _candidate_tool_dirs() -> list[str]:
    raw_candidates = [
        PATHS["tool"],
        os.path.join(BASE_DIR, "memory", "tool"),
        os.path.join(BASE_DIR, "permanence_storage", "memory", "tool"),
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


def _latest_tool_file(pattern: str) -> Optional[str]:
    for tool_dir in _candidate_tool_dirs():
        matches = glob.glob(os.path.join(tool_dir, pattern))
        if matches:
            return max(matches, key=os.path.getmtime)
    return None


def _candidate_working_dirs() -> list[str]:
    raw_candidates = [
        PATHS["working"],
        os.path.join(BASE_DIR, "memory", "working"),
        os.path.join(BASE_DIR, "permanence_storage", "memory", "working"),
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


def _latest_working_file(pattern: str) -> Optional[str]:
    for working_dir in _candidate_working_dirs():
        matches = glob.glob(os.path.join(working_dir, pattern))
        if matches:
            return max(matches, key=os.path.getmtime)
    return None


def _read_text_file(path: Optional[str]) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def _read_json_file(path: Optional[str]) -> dict | list | None:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


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


def _revenue_outreach_status_path() -> str:
    return os.environ.get(
        "PERMANENCE_REVENUE_OUTREACH_STATUS_PATH",
        os.path.join(PATHS["working"], "revenue_outreach_status.jsonl"),
    )


def _outreach_message_key(message: dict) -> str:
    lead_id = str(message.get("lead_id") or "").strip()
    if lead_id:
        return lead_id
    explicit_key = str(message.get("message_key") or "").strip()
    if explicit_key:
        return explicit_key
    return _action_hash(f"{message.get('title', '')}|{message.get('subject', '')}")


def _load_revenue_outreach_status() -> dict[str, dict]:
    path = _revenue_outreach_status_path()
    if not os.path.exists(path):
        return {}
    latest_by_key: dict[str, dict] = {}
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
                key = str(item.get("message_key") or "").strip()
                if not key:
                    continue
                latest_by_key[key] = item
    except OSError:
        return {}
    return latest_by_key


def _record_revenue_outreach_status(*, key: str, lead_id: str, status: str, source: str, actor: str, notes: str) -> dict:
    path = _revenue_outreach_status_path()
    entry = {
        "event_id": f"RO-{utc_now().strftime('%Y%m%d-%H%M%S%f')}",
        "timestamp": utc_iso(),
        "message_key": key,
        "lead_id": lead_id or None,
        "status": status,
        "source": source,
        "actor": actor,
        "notes": notes,
    }
    _append_jsonl(path, entry)
    return entry


def _apply_outreach_status(messages: list[dict]) -> dict:
    status_map = _load_revenue_outreach_status()
    pending = 0
    sent = 0
    replied = 0
    merged: list[dict] = []
    for message in messages[:7]:
        item = dict(message)
        key = _outreach_message_key(item)
        state = status_map.get(key, {})
        status = str(state.get("status") or "pending").strip().lower()
        if status not in REVENUE_OUTREACH_STATUSES:
            status = "pending"
        if status == "sent":
            sent += 1
        elif status == "replied":
            replied += 1
        else:
            pending += 1

        item["message_key"] = key
        item["status"] = status
        item["status_updated_at"] = state.get("timestamp")
        merged.append(item)

    total = len(merged)
    return {
        "messages": merged,
        "count": total,
        "pending_count": pending,
        "sent_count": sent,
        "replied_count": replied,
        "completion_rate": _safe_rate(replied, total),
        "status_path": _revenue_outreach_status_path(),
    }


def _load_revenue_deal_events(limit: int = 200) -> list[dict]:
    path = _revenue_deal_events_path()
    if not os.path.exists(path):
        return []
    rows: list[dict] = []
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
                if isinstance(item, dict):
                    rows.append(item)
    except OSError:
        return []
    rows.sort(key=lambda row: str(row.get("timestamp") or ""), reverse=True)
    if limit > 0:
        return rows[:limit]
    return rows


def _record_revenue_deal_event(
    *,
    lead_id: str,
    event_type: str,
    amount_usd: Optional[float],
    source: str,
    actor: str,
    notes: str,
) -> dict:
    entry = {
        "event_id": f"RD-{utc_now().strftime('%Y%m%d-%H%M%S%f')}",
        "timestamp": utc_iso(),
        "lead_id": lead_id,
        "event_type": event_type,
        "amount_usd": amount_usd,
        "source": source,
        "actor": actor,
        "notes": notes,
    }
    _append_jsonl(_revenue_deal_events_path(), entry)
    return entry


def _summarize_revenue_deal_events(events: list[dict], *, week_start: datetime.date, week_end: datetime.date) -> dict:
    counts = {event_type: 0 for event_type in sorted(REVENUE_DEAL_EVENT_TYPES)}
    week_counts = {event_type: 0 for event_type in sorted(REVENUE_DEAL_EVENT_TYPES)}
    payment_total = 0.0
    payment_week_total = 0.0
    for event in events:
        event_type = str(event.get("event_type") or "").strip().lower()
        if event_type not in counts:
            continue
        counts[event_type] += 1
        amount = _coerce_float(event.get("amount_usd"), 0.0)
        if event_type == "payment_received":
            payment_total += amount
        ts = _parse_iso_datetime(event.get("timestamp"))
        if _in_window(ts, week_start, week_end):
            week_counts[event_type] += 1
            if event_type == "payment_received":
                payment_week_total += amount
    return {
        "counts": counts,
        "week_counts": week_counts,
        "payment_total": payment_total,
        "payment_week_total": payment_week_total,
        "path": _revenue_deal_events_path(),
    }


def _load_revenue_site_events(limit: int = 1000) -> list[dict]:
    path = _revenue_site_events_path()
    if not os.path.exists(path):
        return []
    rows: list[dict] = []
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
                if isinstance(item, dict):
                    rows.append(item)
    except OSError:
        return []
    rows.sort(key=lambda row: str(row.get("timestamp") or ""), reverse=True)
    if limit > 0:
        return rows[:limit]
    return rows


def _record_revenue_site_event(
    *,
    event_type: str,
    source: str,
    session_id: str,
    channel: str,
    meta: dict,
) -> dict:
    entry = {
        "event_id": f"RS-{utc_now().strftime('%Y%m%d-%H%M%S%f')}",
        "timestamp": utc_iso(),
        "event_type": event_type,
        "source": source,
        "session_id": session_id or None,
        "channel": channel or None,
        "meta": meta,
    }
    _append_jsonl(_revenue_site_events_path(), entry)
    return entry


def _summarize_revenue_site_events(events: list[dict], *, week_start: datetime.date, week_end: datetime.date) -> dict:
    counts = {event_type: 0 for event_type in sorted(REVENUE_SITE_EVENT_TYPES)}
    week_counts = {event_type: 0 for event_type in sorted(REVENUE_SITE_EVENT_TYPES)}
    session_ids: set[str] = set()
    week_session_ids: set[str] = set()
    for event in events:
        event_type = str(event.get("event_type") or "").strip().lower()
        if event_type in counts:
            counts[event_type] += 1
        session_id = str(event.get("session_id") or "").strip()
        if session_id:
            session_ids.add(session_id)
        ts = _parse_iso_datetime(event.get("timestamp"))
        if not _in_window(ts, week_start, week_end):
            continue
        if event_type in week_counts:
            week_counts[event_type] += 1
        if session_id:
            week_session_ids.add(session_id)
    return {
        "counts": counts,
        "week_counts": week_counts,
        "sessions_total": len(session_ids),
        "sessions_week": len(week_session_ids),
        "cta_rate_week": _safe_rate(week_counts.get("cta_click", 0), week_counts.get("page_view", 0)),
        "intake_submit_rate_week": _safe_rate(week_counts.get("intake_submit", 0), week_counts.get("cta_click", 0)),
        "intake_capture_rate_week": _safe_rate(week_counts.get("intake_captured", 0), week_counts.get("intake_submit", 0)),
        "path": _revenue_site_events_path(),
    }


def _load_followup_queue_payload() -> tuple[list[dict], Optional[str], Optional[str]]:
    tool_path = _latest_tool_file("revenue_followup_queue_*.json")
    if tool_path and os.path.exists(tool_path):
        try:
            with open(tool_path) as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict):
            items = payload.get("followups")
            if isinstance(items, list):
                rows = [item for item in items if isinstance(item, dict)]
                markdown_path = str(payload.get("latest_markdown") or "") or None
                return rows, markdown_path, tool_path
    markdown_path = _first_existing_output_file("revenue_followup_queue_latest.md")
    if not markdown_path:
        markdown_path = _latest_output_file("revenue_followup_queue_*.md")
    rows: list[dict] = []
    markdown = _read_text_file(markdown_path)
    for line in markdown.splitlines():
        text = line.strip()
        if not text or ". [" not in text:
            continue
        if not text.split(". ", 1)[0].isdigit():
            continue
        rows.append({"action": text.split(". ", 1)[1]})
    return rows, markdown_path, tool_path


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


def _parse_outreach_pack(markdown: str) -> list[dict]:
    if not markdown:
        return []
    messages: list[dict] = []
    current: Optional[dict] = None
    in_body = False
    body_lines: list[str] = []

    for raw in markdown.splitlines():
        line = raw.rstrip("\n")
        text = line.strip()
        if text.startswith("### "):
            if current is not None:
                current["body"] = "\n".join(body_lines).strip()
                messages.append(current)
            current = {
                "title": text[4:].strip(),
                "stage": "",
                "channel": "",
                "subject": "",
                "body": "",
            }
            body_lines = []
            in_body = False
            continue

        if current is None:
            continue

        if text == "```text":
            in_body = True
            continue
        if text == "```":
            in_body = False
            continue
        if in_body:
            body_lines.append(line)
            continue

        if text.startswith("- Stage:"):
            current["stage"] = text.split(":", 1)[1].strip()
        elif text.startswith("- Channel:"):
            current["channel"] = text.split(":", 1)[1].strip()
        elif text.startswith("- Subject:"):
            current["subject"] = text.split(":", 1)[1].strip()

    if current is not None:
        current["body"] = "\n".join(body_lines).strip()
        messages.append(current)
    return messages


def _parse_outreach_title(title: str) -> tuple[str, str]:
    text = str(title or "").strip()
    if " (" in text and text.endswith(")"):
        name_part, maybe_id = text.rsplit(" (", 1)
        candidate = maybe_id[:-1].strip()
        if candidate.startswith("L-"):
            return name_part.strip(), candidate
    return text, ""


def _normalize_outreach_message(message: dict) -> dict:
    title = str(message.get("title") or "").strip()
    lead_name = str(message.get("lead_name") or "").strip()
    lead_id = str(message.get("lead_id") or "").strip()
    if title and (not lead_name or not lead_id):
        parsed_name, parsed_lead_id = _parse_outreach_title(title)
        lead_name = lead_name or parsed_name
        lead_id = lead_id or parsed_lead_id
    if not title:
        if lead_name and lead_id:
            title = f"{lead_name} ({lead_id})"
        elif lead_name:
            title = lead_name
        else:
            title = "Outreach Draft"
    return {
        "title": title,
        "lead_name": lead_name or title,
        "lead_id": lead_id,
        "stage": str(message.get("stage") or "").strip(),
        "channel": str(message.get("channel") or "").strip(),
        "subject": str(message.get("subject") or "").strip(),
        "body": str(message.get("body") or "").strip(),
        "next_action_due": str(message.get("next_action_due") or "").strip(),
    }


def _load_outreach_messages(markdown: str) -> tuple[list[dict], Optional[str]]:
    tool_path = _latest_tool_file("revenue_outreach_pack_*.json")
    if tool_path and os.path.exists(tool_path):
        try:
            with open(tool_path) as f:
                payload = json.load(f)
            raw_messages = payload.get("messages", []) if isinstance(payload, dict) else []
            if isinstance(raw_messages, list):
                normalized = [_normalize_outreach_message(item) for item in raw_messages if isinstance(item, dict)]
                if normalized:
                    return normalized, tool_path
        except (OSError, json.JSONDecodeError):
            pass

    parsed = _parse_outreach_pack(markdown)
    normalized = [_normalize_outreach_message(item) for item in parsed]
    return normalized, None


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


def _safe_float_rate(numerator: float, denominator: float) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


def _build_revenue_target_progress(pipeline_rows: list[dict], targets: dict) -> dict:
    week_start, week_end = _week_window_local()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    won_week_count = 0
    won_week_value = 0.0
    won_month_count = 0
    won_month_value = 0.0
    for row in pipeline_rows:
        stage = str(row.get("stage") or "lead")
        if stage != "won":
            continue
        closed = _parse_iso_datetime(row.get("closed_at")) or _parse_iso_datetime(row.get("updated_at"))
        if closed is None:
            continue
        value = _coerce_float(row.get("actual_value"), _coerce_float(row.get("est_value"), 0.0))
        if _in_window(closed, week_start, week_end):
            won_week_count += 1
            won_week_value += value
        if closed.year == now_utc.year and closed.month == now_utc.month:
            won_month_count += 1
            won_month_value += value

    weekly_revenue_target = max(0.0, _coerce_float(targets.get("weekly_revenue_target"), 0.0))
    monthly_revenue_target = max(0.0, _coerce_float(targets.get("monthly_revenue_target"), 0.0))
    weekly_closes_target = max(0, int(_coerce_float(targets.get("weekly_closes_target"), 0.0)))
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "won_week_count": won_week_count,
        "won_week_value": won_week_value,
        "won_week_progress": _safe_float_rate(won_week_value, weekly_revenue_target),
        "won_week_close_progress": _safe_rate(won_week_count, weekly_closes_target),
        "won_month_count": won_month_count,
        "won_month_value": won_month_value,
        "won_month_progress": _safe_float_rate(won_month_value, monthly_revenue_target),
    }


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

    outreach_path = _first_existing_output_file("revenue_outreach_pack_latest.md")
    if outreach_path is None:
        outreach_path = _latest_output_file("revenue_outreach_pack_*.md") or ""
    followup_path = _first_existing_output_file("revenue_followup_queue_latest.md")
    if followup_path is None:
        followup_path = _latest_output_file("revenue_followup_queue_*.md") or ""
    eval_path = _first_existing_output_file("revenue_eval_latest.md")
    if eval_path is None:
        eval_path = _latest_output_file("revenue_eval_*.md") or ""
    integration_path = _first_existing_output_file("integration_readiness_latest.md")
    if integration_path is None:
        integration_path = _latest_output_file("integration_readiness_*.md") or ""

    queue_markdown = _read_text_file(queue_path)
    board_markdown = _read_text_file(board_path)
    architecture_markdown = _read_text_file(arch_path)
    outreach_markdown = _read_text_file(outreach_path)
    followup_markdown = _read_text_file(followup_path)
    eval_markdown = _read_text_file(eval_path)
    integration_markdown = _read_text_file(integration_path)

    queue_actions = _parse_revenue_queue_actions(queue_markdown)
    queue_progress = _build_queue_progress(queue_actions)
    board_data = _parse_revenue_board(board_markdown)
    outreach_messages, outreach_tool_path = _load_outreach_messages(outreach_markdown)
    outreach_status = _apply_outreach_status(outreach_messages)
    followup_items, followup_markdown_path, followup_tool_path = _load_followup_queue_payload()
    pipeline = _load_pipeline_snapshot()
    pipeline_rows = _pipeline_load()
    intake_rows_all = _load_intake_rows(limit=0)
    intake_rows_preview = intake_rows_all[:10]
    funnel = _build_revenue_funnel(pipeline_rows, intake_rows_all)
    playbook = _load_revenue_playbook()
    targets = _load_revenue_targets()
    target_progress = _build_revenue_target_progress(pipeline_rows, targets)
    deal_events = _load_revenue_deal_events(limit=200)
    site_events = _load_revenue_site_events(limit=1000)
    week_start, week_end = _week_window_local()
    deal_summary = _summarize_revenue_deal_events(deal_events, week_start=week_start, week_end=week_end)
    site_summary = _summarize_revenue_site_events(site_events, week_start=week_start, week_end=week_end)

    return {
        "generated_at": utc_iso(),
        "sources": {
            "queue": queue_path,
            "architecture": arch_path or None,
            "execution_board": board_path or None,
            "outreach_pack": outreach_path or None,
            "outreach_tool": outreach_tool_path,
            "outreach_status": outreach_status["status_path"],
            "followup_queue": followup_markdown_path or followup_path or None,
            "followup_tool": followup_tool_path,
            "revenue_eval": eval_path or None,
            "integration_readiness": integration_path or None,
            "pipeline": pipeline["path"],
            "playbook": _revenue_playbook_path(),
            "targets": _revenue_targets_path(),
            "deal_events": _revenue_deal_events_path(),
            "site_events": _revenue_site_events_path(),
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
        "playbook": {
            "path": _revenue_playbook_path(),
            "data": playbook,
        },
        "targets": {
            "path": _revenue_targets_path(),
            "data": targets,
            "progress": target_progress,
        },
        "outreach": {
            "source": outreach_path or None,
            "tool_source": outreach_tool_path,
            "status_path": outreach_status["status_path"],
            "count": outreach_status["count"],
            "pending_count": outreach_status["pending_count"],
            "sent_count": outreach_status["sent_count"],
            "replied_count": outreach_status["replied_count"],
            "completion_rate": outreach_status["completion_rate"],
            "messages": outreach_status["messages"],
            "content_markdown": outreach_markdown[:6000],
        },
        "followups": {
            "count": len(followup_items),
            "items": followup_items[:14],
            "source": followup_markdown_path or followup_path or None,
            "tool_source": followup_tool_path,
            "content_markdown": followup_markdown[:6000],
        },
        "deal_events": {
            "path": _revenue_deal_events_path(),
            "count": len(deal_events),
            "recent": deal_events[:25],
            "summary": deal_summary,
        },
        "site": {
            "path": _revenue_site_events_path(),
            "count": len(site_events),
            "summary": site_summary,
            "recent": site_events[:25],
        },
        "eval": {
            "source": eval_path or None,
            "status": "PASS" if "- Result: PASS" in eval_markdown else ("FAIL" if "- Result: FAIL" in eval_markdown else "PENDING"),
            "content_markdown": eval_markdown[:4000],
        },
        "integration": {
            "source": integration_path or None,
            "status": "BLOCKED" if "Overall status: BLOCKED" in integration_markdown else ("READY" if "Overall status: READY" in integration_markdown else "PENDING"),
            "content_markdown": integration_markdown[:4000],
        },
        "architecture_excerpt": architecture_markdown[:4000],
    }


def _load_second_brain_snapshot() -> dict:
    life_path = _first_existing_output_file("life_os_brief_latest.md")
    if life_path is None:
        life_path = _latest_output_file("life_os_brief_*.md")
    portfolio_path = _first_existing_output_file("side_business_portfolio_latest.md")
    if portfolio_path is None:
        portfolio_path = _latest_output_file("side_business_portfolio_*.md")
    prediction_path = _first_existing_output_file("prediction_lab_latest.md")
    if prediction_path is None:
        prediction_path = _latest_output_file("prediction_lab_*.md")
    clipping_path = _first_existing_output_file("clipping_pipeline_latest.md")
    if clipping_path is None:
        clipping_path = _latest_output_file("clipping_pipeline_*.md")
    attachment_path = _first_existing_output_file("attachment_pipeline_latest.md")
    if attachment_path is None:
        attachment_path = _latest_output_file("attachment_pipeline_*.md")
    resume_brand_path = _first_existing_output_file("resume_brand_brief_latest.md")
    if resume_brand_path is None:
        resume_brand_path = _latest_output_file("resume_brand_brief_*.md")
    world_watch_path = _first_existing_output_file("world_watch_latest.md")
    if world_watch_path is None:
        world_watch_path = _latest_output_file("world_watch_20*.md")
    world_watch_alerts_path = _first_existing_output_file("world_watch_alerts_latest.md")
    if world_watch_alerts_path is None:
        world_watch_alerts_path = _latest_output_file("world_watch_alerts_*.md")
    opportunity_rank_path = _first_existing_output_file("opportunity_ranker_latest.md")
    if opportunity_rank_path is None:
        opportunity_rank_path = _latest_output_file("opportunity_ranker_*.md")
    opportunity_queue_path = _first_existing_output_file("opportunity_approval_queue_latest.md")
    if opportunity_queue_path is None:
        opportunity_queue_path = _latest_output_file("opportunity_approval_queue_*.md")
    report_path = _first_existing_output_file("second_brain_report_latest.md")
    if report_path is None:
        report_path = _latest_output_file("second_brain_report_*.md")

    life_tool_path = _latest_tool_file("life_os_brief_*.json")
    portfolio_tool_path = _latest_tool_file("side_business_portfolio_*.json")
    prediction_tool_path = _latest_tool_file("prediction_lab_*.json")
    clipping_tool_path = _latest_tool_file("clipping_pipeline_*.json")
    attachment_tool_path = _latest_tool_file("attachment_pipeline_*.json")
    resume_brand_tool_path = _latest_tool_file("resume_brand_brief_*.json")
    world_watch_tool_path = _latest_tool_file("world_watch_20*.json")
    world_watch_alerts_tool_path = _latest_tool_file("world_watch_alerts_*.json")
    opportunity_rank_tool_path = _latest_tool_file("opportunity_ranker_*.json")
    opportunity_queue_tool_path = _latest_tool_file("opportunity_approval_queue_*.json")
    report_tool_path = _latest_tool_file("second_brain_report_*.json")

    life_payload = _read_json_file(life_tool_path) if life_tool_path else {}
    portfolio_payload = _read_json_file(portfolio_tool_path) if portfolio_tool_path else {}
    prediction_payload = _read_json_file(prediction_tool_path) if prediction_tool_path else {}
    clipping_payload = _read_json_file(clipping_tool_path) if clipping_tool_path else {}
    attachment_payload = _read_json_file(attachment_tool_path) if attachment_tool_path else {}
    resume_brand_payload = _read_json_file(resume_brand_tool_path) if resume_brand_tool_path else {}
    world_watch_payload = _read_json_file(world_watch_tool_path) if world_watch_tool_path else {}
    world_watch_alerts_payload = _read_json_file(world_watch_alerts_tool_path) if world_watch_alerts_tool_path else {}
    opportunity_rank_payload = _read_json_file(opportunity_rank_tool_path) if opportunity_rank_tool_path else {}
    opportunity_queue_payload = _read_json_file(opportunity_queue_tool_path) if opportunity_queue_tool_path else {}
    report_payload = _read_json_file(report_tool_path) if report_tool_path else {}

    if not isinstance(life_payload, dict):
        life_payload = {}
    if not isinstance(portfolio_payload, dict):
        portfolio_payload = {}
    if not isinstance(prediction_payload, dict):
        prediction_payload = {}
    if not isinstance(clipping_payload, dict):
        clipping_payload = {}
    if not isinstance(attachment_payload, dict):
        attachment_payload = {}
    if not isinstance(resume_brand_payload, dict):
        resume_brand_payload = {}
    if not isinstance(world_watch_payload, dict):
        world_watch_payload = {}
    if not isinstance(world_watch_alerts_payload, dict):
        world_watch_alerts_payload = {}
    if not isinstance(opportunity_rank_payload, dict):
        opportunity_rank_payload = {}
    if not isinstance(opportunity_queue_payload, dict):
        opportunity_queue_payload = {}
    if not isinstance(report_payload, dict):
        report_payload = {}

    return {
        "generated_at": utc_iso(),
        "sources": {
            "life_markdown": life_path,
            "portfolio_markdown": portfolio_path,
            "prediction_markdown": prediction_path,
            "clipping_markdown": clipping_path,
            "attachment_markdown": attachment_path,
            "resume_brand_markdown": resume_brand_path,
            "world_watch_markdown": world_watch_path,
            "world_watch_alerts_markdown": world_watch_alerts_path,
            "opportunity_rank_markdown": opportunity_rank_path,
            "opportunity_queue_markdown": opportunity_queue_path,
            "report_markdown": report_path,
            "life_tool": life_tool_path,
            "portfolio_tool": portfolio_tool_path,
            "prediction_tool": prediction_tool_path,
            "clipping_tool": clipping_tool_path,
            "attachment_tool": attachment_tool_path,
            "resume_brand_tool": resume_brand_tool_path,
            "world_watch_tool": world_watch_tool_path,
            "world_watch_alerts_tool": world_watch_alerts_tool_path,
            "opportunity_rank_tool": opportunity_rank_tool_path,
            "opportunity_queue_tool": opportunity_queue_tool_path,
            "report_tool": report_tool_path,
        },
        "life": {
            "open_task_count": int(life_payload.get("open_task_count", 0) or 0),
            "domain_counts": life_payload.get("domain_counts", {}),
            "content_markdown": _read_text_file(life_path)[:4000],
        },
        "portfolio": {
            "stream_count": int(portfolio_payload.get("stream_count", 0) or 0),
            "totals": portfolio_payload.get("totals", {}),
            "top_actions": (portfolio_payload.get("top_actions") or [])[:7],
            "content_markdown": _read_text_file(portfolio_path)[:4000],
        },
        "prediction": {
            "manual_review_candidates": int(prediction_payload.get("manual_review_candidates", 0) or 0),
            "results": (prediction_payload.get("results") or [])[:10],
            "content_markdown": _read_text_file(prediction_path)[:4000],
        },
        "clipping": {
            "job_count": int(clipping_payload.get("job_count", 0) or 0),
            "candidate_count": int(clipping_payload.get("candidate_count", 0) or 0),
            "content_markdown": _read_text_file(clipping_path)[:4000],
        },
        "attachments": {
            "counts": attachment_payload.get("counts", {}),
            "transcription_queue_pending": int(attachment_payload.get("transcription_queue_pending", 0) or 0),
            "content_markdown": _read_text_file(attachment_path)[:4000],
        },
        "resume_brand": {
            "brand_doc_count": int(resume_brand_payload.get("brand_doc_count", 0) or 0),
            "resume_bullets": (resume_brand_payload.get("resume_bullets") or [])[:6],
            "brand_actions": (resume_brand_payload.get("brand_actions") or [])[:6],
            "content_markdown": _read_text_file(resume_brand_path)[:4000],
        },
        "world_watch": {
            "item_count": int(world_watch_payload.get("item_count", 0) or 0),
            "high_alert_count": int(world_watch_payload.get("high_alert_count", 0) or 0),
            "top_alerts": (world_watch_payload.get("top_alerts") or [])[:10],
            "alert_dispatch_count": len((world_watch_alerts_payload.get("dispatch_results") or [])),
            "content_markdown": _read_text_file(world_watch_path)[:3000],
            "alerts_markdown": _read_text_file(world_watch_alerts_path)[:3000],
        },
        "opportunities": {
            "ranked_count": int(opportunity_rank_payload.get("item_count", 0) or 0),
            "queued_count": int(opportunity_queue_payload.get("queued_count", 0) or 0),
            "pending_total": int(opportunity_queue_payload.get("pending_total", 0) or 0),
            "top_items": (opportunity_rank_payload.get("top_items") or [])[:10],
            "rank_markdown": _read_text_file(opportunity_rank_path)[:3000],
            "queue_markdown": _read_text_file(opportunity_queue_path)[:3000],
        },
        "report": {
            "snapshot": report_payload.get("snapshot", {}),
            "content_markdown": _read_text_file(report_path)[:4000],
        },
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
