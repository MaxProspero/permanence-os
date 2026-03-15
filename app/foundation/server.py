from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request, send_from_directory

try:
    from flask_cors import CORS
except ModuleNotFoundError:
    CORS = None

from app.foundation.storage import (
    append_activity_event,
    append_jsonl,
    ensure_root,
    list_objects,
    load_json,
    load_object,
    read_jsonl,
    save_json,
    save_object,
    safe_object_id,
)
from core.model_router import ModelRouter


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _slug(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def create_app(storage_root: Path | None = None, tool_root: Path | None = None, shell_path: Path | None = None) -> Flask:
    base_dir = Path(__file__).resolve().parents[2]
    site_root = base_dir / "site" / "foundation"

    root = ensure_root(storage_root or _storage_root(base_dir))
    tool_dir = ensure_root(tool_root or (base_dir / "memory" / "tool"))

    shell_html_path = Path(shell_path or (site_root / "ophtxn_shell.html"))
    official_html_path = site_root / "index.html"
    studio_html_path = site_root / "official_app.html"
    press_html_path = site_root / "press_kit.html"
    hub_html_path = site_root / "local_hub.html"
    ai_school_html_path = site_root / "ai_school.html"
    agent_view_html_path = site_root / "agent_view.html"
    command_center_html_path = site_root / "command_center.html"
    daily_planner_html_path = site_root / "daily_planner.html"
    comms_hub_html_path = site_root / "comms_hub.html"
    rooms_html_path = site_root / "rooms.html"
    markets_terminal_html_path = site_root / "markets_terminal.html"
    trading_room_html_path = site_root / "trading_room.html"
    night_capital_html_path = site_root / "night_capital.html"
    runtime_config_path = site_root / "runtime.config.js"
    assets_root = site_root / "assets"

    sessions_path = root / "sessions.json"
    profiles_path = root / "profiles.json"
    memory_path = root / "memory_entries.jsonl"
    schema_path = Path(__file__).with_name("memory_schema.json")
    router = ModelRouter()

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    if CORS is not None:
        CORS(
            app,
            origins=[
                "http://127.0.0.1:8787",
                "http://localhost:8787",
                "http://127.0.0.1:8797",
                "http://localhost:8797",
                "https://ophtxn.com",
                "https://www.ophtxn.com",
                "https://permanencesystems.com",
                "https://app.permanencesystems.com",
                "https://ophtxn-official.pages.dev",
            ],
        )

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

    def _workspace_activity(limit: int = 50) -> list[dict[str, Any]]:
        return read_jsonl(root / "activity.jsonl", limit=limit)

    def _stamp_record(payload: dict[str, Any], *, owner: str, status: str | None = None) -> dict[str, Any]:
        now = _now_iso()
        record = dict(payload)
        record.setdefault("owner", owner)
        record.setdefault("created_at", now)
        record["updated_at"] = now
        if status is not None:
            record["status"] = status
        return record

    def _log_workspace_event(event_type: str, owner: str, payload: dict[str, Any]) -> None:
        append_activity_event(
            root,
            {
                "event_id": _slug("evt"),
                "event_type": event_type,
                "owner": owner,
                "timestamp": _now_iso(),
                **payload,
            },
        )

    def _document_body_path(document_id: str) -> Path:
        return ensure_root(root / "documents_body") / f"{safe_object_id(document_id)}.md"

    def _document_revision_log(document_id: str) -> Path:
        return ensure_root(root / "document_revisions") / f"{safe_object_id(document_id)}.jsonl"

    def _document_suggestion_log(document_id: str) -> Path:
        return ensure_root(root / "document_suggestions") / f"{safe_object_id(document_id)}.jsonl"

    def _workflow_run_log(workflow_id: str) -> Path:
        return ensure_root(root / "workflow_runs") / f"{safe_object_id(workflow_id)}.jsonl"

    def _append_workflow_run(workflow_id: str, payload: dict[str, Any]) -> None:
        append_jsonl(_workflow_run_log(workflow_id), payload)

    def _workflow_runs(workflow_id: str, limit: int = 30) -> list[dict[str, Any]]:
        return read_jsonl(_workflow_run_log(workflow_id), limit=limit)

    def _workflow_task_type(node_type: str, label: str) -> str:
        token = f"{node_type} {label}".lower()
        if "code" in token or "build" in token or "app" in token:
            return "code_generation"
        if "classif" in token:
            return "classification"
        if "summary" in token or "brief" in token:
            return "summarization"
        if "research" in token:
            return "research_synthesis"
        return "planning"

    def _ordered_workflow_nodes(record: dict[str, Any]) -> list[dict[str, Any]]:
        nodes = record.get("nodes") if isinstance(record.get("nodes"), list) else []
        edges = record.get("edges") if isinstance(record.get("edges"), list) else []
        node_map = {
            str(node.get("id") or ""): node
            for node in nodes
            if isinstance(node, dict) and str(node.get("id") or "").strip()
        }
        if not node_map:
            return []
        outgoing: dict[str, list[str]] = {}
        incoming: dict[str, int] = {node_id: 0 for node_id in node_map}
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("from") or "").strip()
            target = str(edge.get("to") or "").strip()
            if source in node_map and target in node_map:
                outgoing.setdefault(source, []).append(target)
                incoming[target] = incoming.get(target, 0) + 1
        start_ids = [
            node_id
            for node_id, node in node_map.items()
            if str(node.get("type") or "").strip() == "start"
        ] or [node_id for node_id, count in incoming.items() if count == 0]
        ordered: list[dict[str, Any]] = []
        seen: set[str] = set()

        def walk(node_id: str) -> None:
            if node_id in seen or node_id not in node_map:
                return
            seen.add(node_id)
            ordered.append(node_map[node_id])
            for target in outgoing.get(node_id, []):
                walk(target)

        for node_id in start_ids:
            walk(node_id)
        for node in nodes:
            node_id = str(node.get("id") or "").strip()
            if node_id and node_id not in seen:
                ordered.append(node)
        return ordered

    def _execute_workflow(record: dict[str, Any], owner: str) -> dict[str, Any]:
        workflow_id = str(record.get("id") or "").strip()
        project_id = str(record.get("project_id") or "").strip()
        run_id = _slug("wfrun")
        steps: list[dict[str, Any]] = []
        generated_task_ids: list[str] = []
        nodes = _ordered_workflow_nodes(record)
        agents = {
            str(row.get("name") or "").strip().lower(): row
            for row in list_objects(root, "agents", limit=500)
            if isinstance(row, dict) and str(row.get("name") or "").strip()
        }

        for index, node in enumerate(nodes, start=1):
            node_id = str(node.get("id") or "").strip()
            node_type = str(node.get("type") or "task").strip() or "task"
            label = str(node.get("label") or node_id or f"step-{index}").strip()
            step: dict[str, Any] = {
                "step_id": _slug("wfstep"),
                "index": index,
                "node_id": node_id,
                "type": node_type,
                "label": label,
                "status": "completed",
                "timestamp": _now_iso(),
            }
            if node_type in {"task", "research", "review", "approval"}:
                task_id = _slug("task")
                task_status = "awaiting_approval" if node_type == "approval" else "queued"
                task_record = _stamp_record(
                    {
                        "id": task_id,
                        "project_id": project_id,
                        "title": label,
                        "assignee": str(node.get("assignee") or node_type).strip() or node_type,
                        "risk_tier": "high" if node_type == "approval" else "medium",
                        "workflow_id": workflow_id,
                        "workflow_run_id": run_id,
                        "node_id": node_id,
                    },
                    owner=owner,
                    status=task_status,
                )
                save_object(root, "tasks", task_id, task_record)
                generated_task_ids.append(task_id)
                step["generated_task"] = {"id": task_id, "status": task_status}
            elif node_type == "agent":
                agent = agents.get(label.lower())
                step["agent"] = {
                    "matched": bool(agent),
                    "agent_id": str(agent.get("id") or "") if agent else "",
                    "model_preferences": agent.get("model_preferences") if agent else [],
                }
            elif node_type == "model_route":
                decision = router.explain_route(
                    _workflow_task_type(node_type, label),
                    {"project_id": project_id, "workflow_id": workflow_id, "workflow_run_id": run_id},
                )
                step["route"] = {
                    "provider": decision.get("provider"),
                    "model_assigned": decision.get("model_assigned"),
                    "route_reasons": decision.get("route_reasons") or [],
                }
            elif node_type == "start":
                step["message"] = "Workflow execution started."
            elif node_type == "end":
                step["message"] = "Workflow execution completed."
            else:
                step["message"] = f"Processed node type {node_type}."
            steps.append(step)

        run_record = {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "project_id": project_id,
            "name": str(record.get("name") or "").strip(),
            "owner": owner,
            "status": "completed",
            "started_at": _now_iso(),
            "completed_at": _now_iso(),
            "generated_task_ids": generated_task_ids,
            "step_count": len(steps),
            "steps": steps,
        }
        _append_workflow_run(workflow_id, run_record)
        record["last_run_at"] = run_record["completed_at"]
        record["last_run_id"] = run_id
        record["run_count"] = int(record.get("run_count") or 0) + 1
        record["updated_at"] = _now_iso()
        save_object(root, "workflows", workflow_id, record)
        _log_workspace_event(
            "workflow_executed",
            owner,
            {
                "workflow_id": workflow_id,
                "workflow_run_id": run_id,
                "project_id": project_id,
                "generated_task_count": len(generated_task_ids),
            },
        )
        return run_record

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

    def _request_is_loopback() -> bool:
        remote = str(request.remote_addr or "").strip().lower()
        return remote in {"127.0.0.1", "::1", "localhost"} or remote.startswith("::ffff:127.0.0.1")

    def _serve_html(path: Path, error_label: str) -> Any:
        try:
            html = path.read_text(encoding="utf-8")
        except OSError:
            return jsonify({"ok": False, "error": f"{error_label} not found"}), 404
        return Response(html, mimetype="text/html; charset=utf-8")

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
        return _serve_html(shell_html_path, "ophtxn shell")

    @app.get("/app/official")
    def official_site() -> Any:
        return _serve_html(official_html_path, "official site")

    @app.get("/app/studio")
    def official_studio() -> Any:
        return _serve_html(studio_html_path, "studio page")

    @app.get("/app/press")
    def official_press() -> Any:
        return _serve_html(press_html_path, "press kit")

    @app.get("/app/hub")
    def local_hub() -> Any:
        return _serve_html(hub_html_path, "local hub")

    @app.get("/app/command-center")
    def command_center() -> Any:
        return _serve_html(command_center_html_path, "command center")

    @app.get("/app/ai-school")
    def ai_school() -> Any:
        return _serve_html(ai_school_html_path, "ai school")

    @app.get("/app/agent-view")
    def agent_view() -> Any:
        return _serve_html(agent_view_html_path, "agent view")

    @app.get("/app/daily-planner")
    def daily_planner() -> Any:
        return _serve_html(daily_planner_html_path, "daily planner")

    @app.get("/app/comms")
    def comms_hub() -> Any:
        return _serve_html(comms_hub_html_path, "comms hub")

    @app.get("/app/rooms")
    def rooms() -> Any:
        return _serve_html(rooms_html_path, "rooms")

    @app.get("/app/markets")
    def markets_terminal() -> Any:
        return _serve_html(markets_terminal_html_path, "markets terminal")

    @app.get("/app/trading")
    def trading_room() -> Any:
        return _serve_html(trading_room_html_path, "trading room")

    @app.get("/app/night-capital")
    def night_capital() -> Any:
        return _serve_html(night_capital_html_path, "night capital")

    @app.get("/app/runtime.config.js")
    def runtime_config() -> Any:
        try:
            content = runtime_config_path.read_text(encoding="utf-8")
        except OSError:
            return jsonify({"ok": False, "error": "runtime config not found"}), 404
        return Response(content, mimetype="application/javascript; charset=utf-8")

    @app.get("/app/assets/<path:filename>")
    def app_assets(filename: str) -> Any:
        if not assets_root.exists():
            return jsonify({"ok": False, "error": "assets directory not found"}), 404
        return send_from_directory(str(assets_root), filename)

    @app.post("/auth/session")
    def auth_session() -> Any:
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id") or "").strip()
        if not user_id:
            return jsonify({"ok": False, "error": "user_id required"}), 400

        configured_passcode = str(os.getenv("PERMANENCE_FOUNDATION_PASSCODE", "")).strip()
        provided_passcode = str(payload.get("passcode") or "").strip()
        if configured_passcode:
            if not secrets.compare_digest(provided_passcode, configured_passcode):
                return jsonify({"ok": False, "error": "invalid passcode"}), 403
        elif not _request_is_loopback():
            return jsonify({"ok": False, "error": "passcode required for non-local access"}), 403

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

    @app.post("/api/router/explain")
    def router_explain() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        payload = request.get_json(silent=True) or {}
        task_type = str(payload.get("task_type") or "").strip()
        if not task_type:
            return jsonify({"ok": False, "error": "task_type required"}), 400
        context = payload.get("context")
        if context is not None and not isinstance(context, dict):
            return jsonify({"ok": False, "error": "context must be an object"}), 400
        decision = router.explain_route(task_type=task_type, context=context or {})
        return jsonify({"ok": True, "decision": decision})

    @app.get("/api/workspace/bootstrap")
    def workspace_bootstrap() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        limit = max(1, min(50, int(float(request.args.get("limit", 12)))))
        return jsonify(
            {
                "ok": True,
                "projects": list_objects(root, "projects", limit=limit),
                "tasks": list_objects(root, "tasks", limit=limit * 2),
                "documents": list_objects(root, "documents", limit=limit),
                "workflows": list_objects(root, "workflows", limit=limit),
                "activity": _workspace_activity(limit=limit * 3),
            }
        )

    @app.get("/api/projects")
    def projects_list() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        limit = max(1, min(100, int(float(request.args.get("limit", 50)))))
        return jsonify({"ok": True, "projects": list_objects(root, "projects", limit=limit)})

    @app.post("/api/projects")
    def projects_create() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "name required"}), 400
        owner = str(session.get("user_id") or "").strip()
        project_id = safe_object_id(str(payload.get("id") or "")) or _slug("project")
        if project_id == "item":
            project_id = _slug("project")
        record = _stamp_record(
            {
                "id": project_id,
                "name": name,
                "summary": str(payload.get("summary") or "").strip(),
                "goals": _split_csv(payload.get("goals")),
                "agents": _split_csv(payload.get("agents")),
                "documents": [],
                "workflows": [],
            },
            owner=owner,
            status=str(payload.get("status") or "active").strip() or "active",
        )
        save_object(root, "projects", project_id, record)
        _log_workspace_event("project_created", owner, {"project_id": project_id, "name": name})
        return jsonify({"ok": True, "project": record})

    @app.get("/api/tasks")
    def tasks_list() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        limit = max(1, min(200, int(float(request.args.get("limit", 100)))))
        project_id = str(request.args.get("project_id") or "").strip()
        rows = list_objects(root, "tasks", limit=limit)
        if project_id:
            rows = [row for row in rows if str(row.get("project_id") or "").strip() == project_id]
        return jsonify({"ok": True, "tasks": rows})

    @app.post("/api/tasks")
    def tasks_create() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title") or "").strip()
        if not title:
            return jsonify({"ok": False, "error": "title required"}), 400
        owner = str(session.get("user_id") or "").strip()
        task_id = safe_object_id(str(payload.get("id") or "")) or _slug("task")
        if task_id == "item":
            task_id = _slug("task")
        record = _stamp_record(
            {
                "id": task_id,
                "project_id": str(payload.get("project_id") or "").strip(),
                "title": title,
                "assignee": str(payload.get("assignee") or "").strip(),
                "risk_tier": str(payload.get("risk_tier") or "medium").strip() or "medium",
                "budget_tier": str(payload.get("budget_tier") or "standard").strip() or "standard",
                "success_criteria": _split_csv(payload.get("success_criteria")),
                "dependencies": _split_csv(payload.get("dependencies")),
            },
            owner=owner,
            status=str(payload.get("status") or "queued").strip() or "queued",
        )
        save_object(root, "tasks", task_id, record)
        _log_workspace_event(
            "task_created",
            owner,
            {"task_id": task_id, "project_id": record.get("project_id", ""), "title": title},
        )
        return jsonify({"ok": True, "task": record})

    @app.get("/api/agents")
    def agents_list() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        limit = max(1, min(200, int(float(request.args.get("limit", 100)))))
        return jsonify({"ok": True, "agents": list_objects(root, "agents", limit=limit)})

    @app.post("/api/agents")
    def agents_create() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name") or "").strip()
        role = str(payload.get("role") or "").strip()
        if not name or not role:
            return jsonify({"ok": False, "error": "name and role required"}), 400
        owner = str(session.get("user_id") or "").strip()
        agent_id = safe_object_id(str(payload.get("id") or "")) or _slug("agent")
        if agent_id == "item":
            agent_id = _slug("agent")
        record = _stamp_record(
            {
                "id": agent_id,
                "name": name,
                "role": role,
                "model_preferences": _split_csv(payload.get("model_preferences")),
                "permissions": _split_csv(payload.get("permissions")),
                "project_ids": _split_csv(payload.get("project_ids")),
            },
            owner=owner,
            status=str(payload.get("status") or "active").strip() or "active",
        )
        save_object(root, "agents", agent_id, record)
        for project_id in record.get("project_ids", []):
            project = load_object(root, "projects", project_id, {})
            if isinstance(project, dict) and project.get("id"):
                agents = project.get("agents") if isinstance(project.get("agents"), list) else []
                if agent_id not in agents:
                    agents.append(agent_id)
                project["agents"] = agents
                project["updated_at"] = _now_iso()
                save_object(root, "projects", project_id, project)
        _log_workspace_event("agent_created", owner, {"agent_id": agent_id, "name": name, "role": role})
        return jsonify({"ok": True, "agent": record})

    @app.patch("/api/agents/<agent_id>")
    def agents_update(agent_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        record = load_object(root, "agents", agent_id, {})
        if not isinstance(record, dict) or not record.get("id"):
            return jsonify({"ok": False, "error": "agent not found"}), 404
        payload = request.get_json(silent=True) or {}
        owner = str(session.get("user_id") or "").strip()
        old_projects = set(record.get("project_ids") if isinstance(record.get("project_ids"), list) else [])
        if "name" in payload:
            record["name"] = str(payload.get("name") or record.get("name") or "").strip()
        if "role" in payload:
            record["role"] = str(payload.get("role") or record.get("role") or "").strip()
        if "status" in payload:
            record["status"] = str(payload.get("status") or record.get("status") or "").strip()
        if "model_preferences" in payload:
            record["model_preferences"] = _split_csv(payload.get("model_preferences"))
        if "permissions" in payload:
            record["permissions"] = _split_csv(payload.get("permissions"))
        if "project_ids" in payload:
            record["project_ids"] = _split_csv(payload.get("project_ids"))
        record["updated_at"] = _now_iso()
        save_object(root, "agents", agent_id, record)

        new_projects = set(record.get("project_ids") if isinstance(record.get("project_ids"), list) else [])
        for project_id in old_projects | new_projects:
            project = load_object(root, "projects", project_id, {})
            if not isinstance(project, dict) or not project.get("id"):
                continue
            agents = project.get("agents") if isinstance(project.get("agents"), list) else []
            agents = [row for row in agents if row != agent_id]
            if project_id in new_projects:
                agents.append(agent_id)
            project["agents"] = agents
            project["updated_at"] = _now_iso()
            save_object(root, "projects", project_id, project)

        _log_workspace_event("agent_updated", owner, {"agent_id": agent_id, "name": record.get("name", "")})
        return jsonify({"ok": True, "agent": record})

    @app.get("/api/workflows")
    def workflows_list() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        limit = max(1, min(200, int(float(request.args.get("limit", 100)))))
        project_id = str(request.args.get("project_id") or "").strip()
        rows = list_objects(root, "workflows", limit=limit)
        if project_id:
            rows = [row for row in rows if str(row.get("project_id") or "").strip() == project_id]
        return jsonify({"ok": True, "workflows": rows})

    @app.post("/api/workflows")
    def workflows_create() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "name required"}), 400
        owner = str(session.get("user_id") or "").strip()
        workflow_id = safe_object_id(str(payload.get("id") or "")) or _slug("workflow")
        if workflow_id == "item":
            workflow_id = _slug("workflow")
        record = _stamp_record(
            {
                "id": workflow_id,
                "project_id": str(payload.get("project_id") or "").strip(),
                "name": name,
                "nodes": payload.get("nodes") if isinstance(payload.get("nodes"), list) else [],
                "edges": payload.get("edges") if isinstance(payload.get("edges"), list) else [],
            },
            owner=owner,
            status=str(payload.get("status") or "draft").strip() or "draft",
        )
        save_object(root, "workflows", workflow_id, record)
        project_id = str(record.get("project_id") or "").strip()
        if project_id:
            project = load_object(root, "projects", project_id, {})
            if isinstance(project, dict) and project.get("id"):
                workflows = project.get("workflows") if isinstance(project.get("workflows"), list) else []
                if workflow_id not in workflows:
                    workflows.append(workflow_id)
                project["workflows"] = workflows
                project["updated_at"] = _now_iso()
                save_object(root, "projects", project_id, project)
        _log_workspace_event("workflow_created", owner, {"workflow_id": workflow_id, "project_id": project_id, "name": name})
        return jsonify({"ok": True, "workflow": record})

    @app.get("/api/workflows/<workflow_id>")
    def workflows_detail(workflow_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        record = load_object(root, "workflows", workflow_id, {})
        if not isinstance(record, dict) or not record.get("id"):
            return jsonify({"ok": False, "error": "workflow not found"}), 404
        return jsonify({"ok": True, "workflow": record, "runs": _workflow_runs(workflow_id, limit=20)})

    @app.patch("/api/workflows/<workflow_id>")
    def workflows_update(workflow_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        record = load_object(root, "workflows", workflow_id, {})
        if not isinstance(record, dict) or not record.get("id"):
            return jsonify({"ok": False, "error": "workflow not found"}), 404
        payload = request.get_json(silent=True) or {}
        owner = str(session.get("user_id") or "").strip()
        if "name" in payload:
            record["name"] = str(payload.get("name") or record.get("name") or "").strip()
        if "status" in payload:
            record["status"] = str(payload.get("status") or record.get("status") or "").strip()
        if isinstance(payload.get("nodes"), list):
            record["nodes"] = payload.get("nodes")
        if isinstance(payload.get("edges"), list):
            record["edges"] = payload.get("edges")
        record["updated_at"] = _now_iso()
        save_object(root, "workflows", workflow_id, record)
        _log_workspace_event("workflow_updated", owner, {"workflow_id": workflow_id, "name": record.get("name", "")})
        return jsonify({"ok": True, "workflow": record})

    @app.post("/api/workflows/<workflow_id>/execute")
    def workflows_execute(workflow_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        record = load_object(root, "workflows", workflow_id, {})
        if not isinstance(record, dict) or not record.get("id"):
            return jsonify({"ok": False, "error": "workflow not found"}), 404
        owner = str(session.get("user_id") or "").strip()
        run_record = _execute_workflow(record, owner)
        return jsonify({"ok": True, "workflow": record, "run": run_record})

    @app.get("/api/documents")
    def documents_list() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        limit = max(1, min(200, int(float(request.args.get("limit", 100)))))
        project_id = str(request.args.get("project_id") or "").strip()
        rows = list_objects(root, "documents", limit=limit)
        if project_id:
            rows = [row for row in rows if str(row.get("project_id") or "").strip() == project_id]
        return jsonify({"ok": True, "documents": rows})

    @app.post("/api/documents")
    def documents_create() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title") or "").strip()
        if not title:
            return jsonify({"ok": False, "error": "title required"}), 400
        owner = str(session.get("user_id") or "").strip()
        document_id = safe_object_id(str(payload.get("id") or "")) or _slug("document")
        if document_id == "item":
            document_id = _slug("document")
        body = str(payload.get("body") or "").strip()
        body_path = _document_body_path(document_id)
        body_path.write_text(body + ("\n" if body else ""), encoding="utf-8")
        record = _stamp_record(
            {
                "id": document_id,
                "project_id": str(payload.get("project_id") or "").strip(),
                "title": title,
                "body_path": str(body_path.relative_to(root)),
                "revision_count": 1 if body else 0,
                "suggestion_count": 0,
            },
            owner=owner,
            status=str(payload.get("status") or "draft").strip() or "draft",
        )
        save_object(root, "documents", document_id, record)
        if body:
            append_jsonl(
                _document_revision_log(document_id),
                {
                    "revision_id": _slug("rev"),
                    "document_id": document_id,
                    "author": owner,
                    "timestamp": _now_iso(),
                    "kind": "create",
                    "body": body,
                },
            )
        _log_workspace_event(
            "document_created",
            owner,
            {"document_id": document_id, "project_id": record.get("project_id", ""), "title": title},
        )
        return jsonify({"ok": True, "document": record})

    @app.get("/api/documents/<document_id>")
    def documents_detail(document_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        record = load_object(root, "documents", document_id, {})
        if not isinstance(record, dict) or not record.get("id"):
            return jsonify({"ok": False, "error": "document not found"}), 404
        body_rel = str(record.get("body_path") or "").strip()
        body = ""
        if body_rel:
            try:
                body = (root / body_rel).read_text(encoding="utf-8")
            except OSError:
                body = ""
        revisions = read_jsonl(_document_revision_log(document_id), limit=20)
        suggestions = read_jsonl(_document_suggestion_log(document_id), limit=50)
        return jsonify(
            {
                "ok": True,
                "document": record,
                "body": body,
                "revisions": revisions,
                "suggestions": suggestions,
            }
        )

    @app.patch("/api/documents/<document_id>")
    def documents_update(document_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        record = load_object(root, "documents", document_id, {})
        if not isinstance(record, dict) or not record.get("id"):
            return jsonify({"ok": False, "error": "document not found"}), 404
        payload = request.get_json(silent=True) or {}
        owner = str(session.get("user_id") or "").strip()
        body = str(payload.get("body") or "")
        title = str(payload.get("title") or record.get("title") or "").strip()
        body_path = root / str(record.get("body_path") or _document_body_path(document_id).relative_to(root))
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_text(body, encoding="utf-8")
        record["title"] = title or str(record.get("title") or "")
        record["revision_count"] = int(record.get("revision_count") or 0) + 1
        record["updated_at"] = _now_iso()
        save_object(root, "documents", document_id, record)
        append_jsonl(
            _document_revision_log(document_id),
            {
                "revision_id": _slug("rev"),
                "document_id": document_id,
                "author": owner,
                "timestamp": _now_iso(),
                "kind": "edit",
                "body": body,
            },
        )
        _log_workspace_event("document_revised", owner, {"document_id": document_id, "title": record.get("title", "")})
        return jsonify({"ok": True, "document": record})

    @app.get("/api/documents/<document_id>/suggestions")
    def documents_suggestions_list(document_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        return jsonify({"ok": True, "suggestions": read_jsonl(_document_suggestion_log(document_id), limit=100)})

    @app.post("/api/documents/<document_id>/suggestions")
    def documents_suggestions_create(document_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        record = load_object(root, "documents", document_id, {})
        if not isinstance(record, dict) or not record.get("id"):
            return jsonify({"ok": False, "error": "document not found"}), 404
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text") or "").strip()
        if not text:
            return jsonify({"ok": False, "error": "text required"}), 400
        owner = str(session.get("user_id") or "").strip()
        suggestion = {
            "suggestion_id": _slug("sug"),
            "document_id": document_id,
            "author": str(payload.get("author") or owner).strip() or owner,
            "text": text,
            "status": "proposed",
            "timestamp": _now_iso(),
        }
        append_jsonl(_document_suggestion_log(document_id), suggestion)
        record["suggestion_count"] = int(record.get("suggestion_count") or 0) + 1
        record["updated_at"] = _now_iso()
        save_object(root, "documents", document_id, record)
        _log_workspace_event("document_suggestion_added", owner, {"document_id": document_id, "suggestion_id": suggestion["suggestion_id"]})
        return jsonify({"ok": True, "suggestion": suggestion})

    @app.patch("/api/documents/<document_id>/suggestions/<suggestion_id>")
    def documents_suggestions_update(document_id: str, suggestion_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        payload = request.get_json(silent=True) or {}
        new_status = str(payload.get("status") or "").strip().lower()
        if new_status not in {"proposed", "accepted", "rejected"}:
            return jsonify({"ok": False, "error": "invalid status"}), 400
        suggestions = read_jsonl(_document_suggestion_log(document_id), limit=500)
        updated = None
        for row in suggestions:
            if str(row.get("suggestion_id") or "") == suggestion_id:
                row["status"] = new_status
                row["updated_at"] = _now_iso()
                updated = row
        if updated is None:
            return jsonify({"ok": False, "error": "suggestion not found"}), 404
        log_path = _document_suggestion_log(document_id)
        log_path.write_text("", encoding="utf-8")
        for row in suggestions:
            append_jsonl(log_path, row)
        owner = str(session.get("user_id") or "").strip()
        _log_workspace_event("document_suggestion_" + new_status, owner, {"document_id": document_id, "suggestion_id": suggestion_id})
        return jsonify({"ok": True, "suggestion": updated})

    @app.get("/api/activity")
    def activity_list() -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        limit = max(1, min(200, int(float(request.args.get("limit", 100)))))
        return jsonify({"ok": True, "activity": _workspace_activity(limit=limit)})

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
        approval_triage = _latest_tool_payload(tool_dir, "approval_triage")
        no_spend_audit = _latest_tool_payload(tool_dir, "no_spend_audit")

        money_status = money_gate.get("status") if isinstance(money_gate.get("status"), dict) else {}
        approval_counts = approval_triage.get("counts") if isinstance(approval_triage.get("counts"), dict) else {}
        audit_violations = no_spend_audit.get("violations") if isinstance(no_spend_audit.get("violations"), list) else []

        payload = {
            "ok": True,
            "user_id": user_id,
            "generated_at": _now_iso(),
            "summary": {
                "completion_pct": _safe_int(completion.get("completion_pct"), 0),
                "completion_blockers": len(completion.get("blockers") or []),
                "feature_work_unlocked": bool(money_status.get("gate_pass")),
                "won_revenue_usd": float(money_status.get("won_revenue_usd") or 0.0),
                "won_deals": _safe_int(money_status.get("won_deals"), 0),
                "comms_warnings": len(comms_status.get("warnings") or []),
                "self_improvement_pending": _safe_int(self_improvement.get("pending_count"), 0),
                "approved_execution_tasks": _safe_int(approvals.get("task_count"), 0),
                "newly_queued_tasks": _safe_int(approvals.get("marked_queued_count"), 0),
                "approvals_pending": _safe_int(approval_counts.get("PENDING_HUMAN_REVIEW"), 0),
                "no_spend_violations": len(audit_violations),
            },
            "sources": {
                "completion": str(completion.get("latest_markdown") or ""),
                "money_first_gate": str(money_gate.get("latest_markdown") or ""),
                "comms_status": str(comms_status.get("latest_markdown") or ""),
                "self_improvement": str(self_improvement.get("latest_markdown") or ""),
                "approval_execution_board": str(approvals.get("latest_markdown") or ""),
                "approval_triage": str(approval_triage.get("latest_markdown") or ""),
                "no_spend_audit": str(no_spend_audit.get("latest_markdown") or ""),
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
