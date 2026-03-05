from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request

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


def create_app(storage_root: Path | None = None) -> Flask:
    base_dir = Path(__file__).resolve().parents[2]
    root = ensure_root(storage_root or _storage_root(base_dir))
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
