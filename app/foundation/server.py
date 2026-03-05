from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request

from app.foundation.storage import append_jsonl, ensure_root, load_json, read_jsonl, save_json


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_csv(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    token = str(value or "").strip()
    if not token:
        return []
    return [item.strip() for item in token.split(",") if item.strip()]


def _storage_root(base_dir: Path) -> Path:
    override = str(os.getenv("PERMANENCE_FOUNDATION_STORAGE_ROOT", "")).strip()
    if override:
        return ensure_root(Path(override).expanduser())
    return ensure_root(base_dir / "memory" / "working" / "app_foundation")


def _latest_tool_payload(tool_root: Path, prefix: str) -> dict[str, Any]:
    rows = sorted(tool_root.glob(f"{prefix}_*.json"), key=lambda row: row.stat().st_mtime, reverse=True)
    if not rows:
        return {}
    payload = load_json(rows[0], {})
    return payload if isinstance(payload, dict) else {}


def create_app(storage_root: Path | None = None, tool_root: Path | None = None, shell_path: Path | None = None) -> Flask:
    base_dir = Path(__file__).resolve().parents[2]
    root = ensure_root(storage_root or _storage_root(base_dir))
    tool_dir = ensure_root(tool_root or (base_dir / "memory" / "tool"))
    shell_html_path = Path(shell_path or (base_dir / "site" / "foundation" / "ophtxn_shell.html"))
    sessions_path = root / "sessions.json"
    profiles_path = root / "profiles.json"
    memory_path = root / "memory_entries.jsonl"
    schema_path = Path(__file__).with_name("memory_schema.json")

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    def _sessions() -> dict[str, dict[str, Any]]:
        payload = load_json(sessions_path, {})
        return payload if isinstance(payload, dict) else {}

    def _profiles() -> dict[str, dict[str, Any]]:
        payload = load_json(profiles_path, {})
        return payload if isinstance(payload, dict) else {}

    def _write_sessions(payload: dict[str, dict[str, Any]]) -> None:
        save_json(sessions_path, payload)

    def _write_profiles(payload: dict[str, dict[str, Any]]) -> None:
        save_json(profiles_path, payload)

    def _active_session() -> tuple[str, dict[str, Any]] | tuple[None, None]:
        token = str(request.headers.get("X-Session-Token") or "").strip()
        if not token:
            return None, None
        sessions = _sessions()
        session = sessions.get(token)
        if not isinstance(session, dict):
            return None, None
        expires_raw = str(session.get("expires_at") or "").strip()
        if not expires_raw:
            return None, None
        try:
            expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
        except ValueError:
            return None, None
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return None, None
        return token, session

    @app.get("/health")
    def health() -> Any:
        return jsonify(
            {
                "ok": True,
                "service": "foundation-api",
                "storage_root": str(root),
                "timestamp": _now_iso(),
            }
        )

    @app.get("/app/ophtxn")
    def ophtxn_shell() -> Any:
        try:
            html = shell_html_path.read_text(encoding="utf-8")
        except OSError:
            return jsonify({"ok": False, "error": "ophtxn shell not found"}), 404
        return Response(html, mimetype="text/html; charset=utf-8")

    @app.post("/auth/session")
    def auth_session() -> Any:
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        configured_passcode = str(os.getenv("PERMANENCE_FOUNDATION_PASSCODE", "")).strip()
        provided_passcode = str(payload.get("passcode") or "").strip()
        if configured_passcode and configured_passcode != provided_passcode:
            return jsonify({"ok": False, "error": "invalid passcode"}), 403

        ttl_minutes = max(5, min(1440, int(float(payload.get("ttl_minutes") or 720))))
        token = secrets.token_urlsafe(24)
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat()
        sessions = _sessions()
        sessions[token] = {
            "user_id": user_id,
            "name": str(payload.get("name") or "").strip(),
            "created_at": _now_iso(),
            "expires_at": expires_at,
        }
        _write_sessions(sessions)
        return jsonify({"ok": True, "token": token, "expires_at": expires_at, "user_id": user_id})

    @app.post("/onboarding/start")
    def onboarding_start() -> Any:
        token, session = _active_session()
        if not token or not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        payload = request.get_json(silent=True) or {}
        user_id = str(session.get("user_id") or "").strip()
        profiles = _profiles()
        profile = profiles.get(user_id) if isinstance(profiles.get(user_id), dict) else {}
        profile.update(
            {
                "user_id": user_id,
                "name": str(payload.get("name") or session.get("name") or "").strip(),
                "mission": str(payload.get("mission") or "").strip(),
                "goals": _split_csv(payload.get("goals")),
                "strengths": _split_csv(payload.get("strengths")),
                "growth_edges": _split_csv(payload.get("growth_edges")),
                "work_style": str(payload.get("work_style") or "").strip(),
                "values": _split_csv(payload.get("values")),
                "personality_mode": str(payload.get("personality_mode") or "adaptive").strip() or "adaptive",
                "updated_at": _now_iso(),
            }
        )
        profiles[user_id] = profile
        _write_profiles(profiles)
        return jsonify({"ok": True, "user_id": user_id, "profile": profile})

    @app.get("/memory/schema")
    def memory_schema() -> Any:
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {"schema_version": "unknown", "entities": {}}
        return jsonify(payload)

    @app.get("/ops/summary")
    def ops_summary() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        user_id = str(session.get("user_id") or "").strip()

        completion = _latest_tool_payload(tool_dir, "ophtxn_completion")
        money_gate = _latest_tool_payload(tool_dir, "money_first_gate")
        comms_status = _latest_tool_payload(tool_dir, "comms_status")
        self_improvement = _latest_tool_payload(tool_dir, "self_improvement")
        approvals = _latest_tool_payload(tool_dir, "approval_execution_board")

        money_status = money_gate.get("status") if isinstance(money_gate.get("status"), dict) else {}
        payload = {
            "ok": True,
            "user_id": user_id,
            "generated_at": _now_iso(),
            "summary": {
                "completion_pct": int(float(completion.get("completion_pct") or 0)),
                "completion_blockers": len(completion.get("blockers") or []),
                "feature_work_unlocked": bool(money_status.get("gate_pass")),
                "won_revenue_usd": float(money_status.get("won_revenue_usd") or 0.0),
                "won_deals": int(float(money_status.get("won_deals") or 0)),
                "comms_warnings": len(comms_status.get("warnings") or []),
                "self_improvement_pending": int(float(self_improvement.get("pending_count") or 0)),
                "approved_execution_tasks": int(float(approvals.get("task_count") or 0)),
                "newly_queued_tasks": int(float(approvals.get("marked_queued_count") or 0)),
            },
            "sources": {
                "completion": str(completion.get("latest_markdown") or ""),
                "money_first_gate": str(money_gate.get("latest_markdown") or ""),
                "comms_status": str(comms_status.get("latest_markdown") or ""),
                "self_improvement": str(self_improvement.get("latest_markdown") or ""),
                "approval_execution_board": str(approvals.get("latest_markdown") or ""),
            },
        }
        return jsonify(payload)

    @app.post("/memory/entry")
    def memory_entry_add() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text") or "").strip()
        if not text:
            return jsonify({"ok": False, "error": "text required"}), 400
        user_id = str(session.get("user_id") or "").strip()
        entry = {
            "entry_id": f"MEM-{secrets.token_hex(6)}",
            "user_id": user_id,
            "source": str(payload.get("source") or "manual").strip() or "manual",
            "text": text,
            "tags": _split_csv(payload.get("tags")),
            "importance": max(0.0, min(1.0, float(payload.get("importance") or 0.5))),
            "timestamp": _now_iso(),
        }
        append_jsonl(memory_path, entry)
        return jsonify({"ok": True, "entry": entry})

    @app.get("/memory/entry")
    def memory_entry_list() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        user_id = str(session.get("user_id") or "").strip()
        limit = max(1, min(200, int(float(request.args.get("limit", 50)))))
        rows = read_jsonl(memory_path, limit=1000)
        scoped = [row for row in rows if str(row.get("user_id") or "").strip() == user_id]
        return jsonify({"ok": True, "count": len(scoped[-limit:]), "entries": scoped[-limit:]})

    return app
