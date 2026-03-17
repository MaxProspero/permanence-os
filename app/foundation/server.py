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

    def _rewrite_workflow_runs(workflow_id: str, rows: list[dict[str, Any]]) -> None:
        log_path = _workflow_run_log(workflow_id)
        log_path.write_text("", encoding="utf-8")
        for row in rows:
            append_jsonl(log_path, row)

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

    def _workflow_permission_for(node_type: str) -> str:
        if node_type in {"task", "research", "review"}:
            return "execute"
        if node_type == "approval":
            return "approve"
        if node_type in {"agent", "model_route"}:
            return "read"
        return "read"

    def _agent_matches_project(agent: dict[str, Any], project_id: str) -> bool:
        project_ids = agent.get("project_ids") if isinstance(agent.get("project_ids"), list) else []
        return not project_id or project_id in project_ids

    def _eligible_agents_for_node(
        all_agents: list[dict[str, Any]],
        *,
        project_id: str,
        node_type: str,
        label: str,
        assignee: str,
    ) -> list[dict[str, Any]]:
        permission = _workflow_permission_for(node_type)
        wanted = assignee.strip().lower() or label.strip().lower()
        ranked: list[tuple[int, dict[str, Any]]] = []
        for agent in all_agents:
            if not isinstance(agent, dict) or not str(agent.get("id") or "").strip():
                continue
            if str(agent.get("status") or "active").strip().lower() != "active":
                continue
            if not _agent_matches_project(agent, project_id):
                continue
            permissions = agent.get("permissions") if isinstance(agent.get("permissions"), list) else []
            if permission not in permissions:
                continue
            name = str(agent.get("name") or "").strip().lower()
            role = str(agent.get("role") or "").strip().lower()
            score = 0
            if wanted and wanted in {name, role}:
                score += 4
            if wanted and wanted and wanted in f"{name} {role}":
                score += 2
            if node_type in role:
                score += 2
            ranked.append((score, agent))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [agent for _score, agent in ranked]

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

    def _workflow_graph(record: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], list[str]]:
        nodes = record.get("nodes") if isinstance(record.get("nodes"), list) else []
        edges = record.get("edges") if isinstance(record.get("edges"), list) else []
        node_map = {
            str(node.get("id") or "").strip(): node
            for node in nodes
            if isinstance(node, dict) and str(node.get("id") or "").strip()
        }
        outgoing: dict[str, list[dict[str, Any]]] = {}
        incoming: dict[str, int] = {node_id: 0 for node_id in node_map}
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("from") or "").strip()
            target = str(edge.get("to") or "").strip()
            if source in node_map and target in node_map:
                outgoing.setdefault(source, []).append(edge)
                incoming[target] = incoming.get(target, 0) + 1
        starts = [
            node_id
            for node_id, node in node_map.items()
            if str(node.get("type") or "").strip() == "start"
        ] or [node_id for node_id, count in incoming.items() if count == 0]
        return node_map, outgoing, starts

def _select_next_node_id(edges: list[dict[str, Any]], outcome: str | None = None) -> str:
    if not edges:
        return ""
    if outcome and outcome.startswith("context:"):
        context: dict[str, Any] = {}
        try:
            context = json.loads(outcome[len("context:"):])
        except json.JSONDecodeError:
            context = {}
        for edge in edges:
            if _condition_matches(edge, context):
                return str(edge.get("to") or "").strip()
    wanted = str(outcome or "").strip().lower()
    aliases = {
        "completed": {"completed", "success", "approved"},
        "success": {"success", "completed", "approved"},
        "failed": {"failed", "rejected", "needs_review"},
        "rejected": {"rejected", "failed"},
        "needs_review": {"needs_review", "failed", "rejected"},
        "approved": {"approved", "success", "completed"},
    }
    if wanted:
        wanted_set = aliases.get(wanted, {wanted})
        for edge in edges:
            label = str(edge.get("label") or "").strip().lower()
            normalized = label.replace(" ", "_")
            if label in wanted_set or normalized in wanted_set:
                return str(edge.get("to") or "").strip()
    for edge in edges:
        if not str(edge.get("label") or "").strip():
            return str(edge.get("to") or "").strip()
    return str(edges[0].get("to") or "").strip()


def _workflow_template_context(run_record: dict[str, Any]) -> dict[str, Any]:
    context = run_record.get("context")
    if not isinstance(context, dict):
        context = {}
    return {
        "latest_output": context.get("latest_output"),
        "task_outputs": context.get("task_outputs") if isinstance(context.get("task_outputs"), dict) else {},
    }


def _template_lookup(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for part in [segment for segment in path.split(".") if segment]:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def _apply_template_transform(value: Any, transform: str) -> Any:
    token = str(transform or "").strip().lower()
    if not token:
        return value
    if token == "json":
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    if token == "lower":
        return str(value or "").lower()
    if token == "upper":
        return str(value or "").upper()
    if token == "strip":
        return str(value or "").strip()
    if token == "len":
        if isinstance(value, (dict, list, str, tuple, set)):
            return len(value)
        return 0
    if token == "first":
        if isinstance(value, (list, tuple)) and value:
            return value[0]
        return None
    if token == "last":
        if isinstance(value, (list, tuple)) and value:
            return value[-1]
        return None
    if token.startswith("split"):
        separator = ","
        if ":" in transform:
            separator = transform.split(":", 1)[1]
        text = "" if value is None else str(value)
        return text.split(separator)
    if token.startswith("get:"):
        index_raw = token.split(":", 1)[1].strip()
        if isinstance(value, (list, tuple)):
            try:
                return value[int(index_raw)]
            except (ValueError, IndexError):
                return None
        return None
    if token == "int":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    if token == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    if token.startswith("round:"):
        precision_raw = token.split(":", 1)[1].strip()
        try:
            precision = int(precision_raw)
        except ValueError:
            precision = 0
        try:
            return round(float(value), precision)
        except (TypeError, ValueError):
            return 0
    if token.startswith("default:"):
        fallback = transform.split(":", 1)[1]
        if value in {None, "", [], {}, ()}:
            return fallback
        return value
    if token.startswith("coalesce:"):
        fallback = transform.split(":", 1)[1]
        text_value = "" if value is None else str(value)
        return text_value if text_value.strip() else fallback
    if token == "text":
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=True, sort_keys=True)
        return "" if value is None else str(value)
    return value


def _render_input_template(template: str, context: dict[str, Any]) -> str:
    raw = str(template or "").strip()
    if not raw:
        return ""

    def replace(match: re.Match[str]) -> str:
        expression = str(match.group(1) or "").strip()
        parts = [part.strip() for part in expression.split("|")]
        value = _template_lookup(context, parts[0] if parts else expression)
        for transform in parts[1:]:
            value = _apply_template_transform(value, transform)
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=True, sort_keys=True)
        return str(value)

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, raw)


def _condition_matches(edge: dict[str, Any], context: dict[str, Any]) -> bool:
    condition = str(edge.get("condition") or "").strip()
    if not condition:
        return False

    def unwrap_parentheses(text: str) -> str:
        raw = str(text or "").strip()
        while raw.startswith("(") and raw.endswith(")"):
            depth = 0
            in_quote: str | None = None
            escaped = False
            balanced = True
            for index, char in enumerate(raw):
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char in {"'", '"'}:
                    if in_quote == char:
                        in_quote = None
                    elif in_quote is None:
                        in_quote = char
                    continue
                if in_quote is not None:
                    continue
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0 and index != len(raw) - 1:
                        balanced = False
                        break
            if not balanced or depth != 0:
                break
            raw = raw[1:-1].strip()
        return raw

    def normalize_literal(text: str) -> str:
        raw = str(text or "").strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
            raw = raw[1:-1]
        raw = raw.replace("\\\\", "\\")
        raw = raw.replace('\\"', '"').replace("\\'", "'")
        return raw

    def parse_literal_list(text: str) -> list[str]:
        raw = str(text or "").strip()
        if not raw:
            return []
        parts = [part.strip() for part in re.split(r""",(?=(?:[^"'\\]|\\.|"[^"]*"|'[^']*')*$)""", raw) if part.strip()]
        return [normalize_literal(part) for part in parts]

    def parse_function_call(text: str) -> tuple[str, list[str]] | None:
        match = re.fullmatch(r"([a-z_]+)\((.*)\)", str(text or "").strip(), flags=re.IGNORECASE)
        if not match:
            return None
        name = str(match.group(1) or "").strip().lower()
        args_raw = str(match.group(2) or "").strip()
        if not args_raw:
            return name, []
        args = parse_literal_list(args_raw)
        return name, args

    def numeric_expression_value(text: str) -> float | None:
        expression = str(text or "").strip()
        function_call = parse_function_call(expression)
        if function_call:
            function_name, function_args = function_call
            if function_name in {"count", "len"} and len(function_args) == 1:
                value = _template_lookup(context, function_args[0])
                if value is None:
                    return 0.0
                if isinstance(value, (str, bytes, list, tuple, set, dict)):
                    return float(len(value))
                return 0.0
        try:
            return float(expression)
        except ValueError:
            value = _template_lookup(context, expression)
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

    def split_top_level(text: str, keyword: str) -> list[str]:
        parts: list[str] = []
        buffer: list[str] = []
        depth = 0
        in_quote: str | None = None
        escaped = False
        index = 0
        token = f" {keyword} "
        raw = str(text or "")
        token_length = len(token)
        while index < len(raw):
            char = raw[index]
            if escaped:
                buffer.append(char)
                escaped = False
                index += 1
                continue
            if char == "\\":
                buffer.append(char)
                escaped = True
                index += 1
                continue
            if char in {"'", '"'}:
                if in_quote == char:
                    in_quote = None
                elif in_quote is None:
                    in_quote = char
                buffer.append(char)
                index += 1
                continue
            if in_quote is None:
                if char == "(":
                    depth += 1
                elif char == ")" and depth > 0:
                    depth -= 1
                elif depth == 0 and raw[index:index + token_length].lower() == token:
                    part = "".join(buffer).strip()
                    if part:
                        parts.append(part)
                    buffer = []
                    index += token_length
                    continue
            buffer.append(char)
            index += 1
        tail = "".join(buffer).strip()
        if tail:
            parts.append(tail)
        return parts

    condition = unwrap_parentheses(condition)
    lowered = condition.lower()
    or_parts = split_top_level(condition, "or")
    if len(or_parts) > 1:
        parts = [part.strip() for part in or_parts if part.strip()]
        return any(_condition_matches({"condition": part}, context) for part in parts)
    and_parts = split_top_level(condition, "and")
    if len(and_parts) > 1:
        parts = [part.strip() for part in and_parts if part.strip()]
        return all(_condition_matches({"condition": part}, context) for part in parts)
    function_call = parse_function_call(condition)
    if function_call:
        function_name, function_args = function_call
        if function_name in {"count", "len"} and len(function_args) == 1:
            numeric_value = numeric_expression_value(condition)
            return bool(numeric_value)
        if function_name in {"any", "all"} and len(function_args) >= 2:
            function_target = function_args[0]
            function_values = function_args[1:]
            target_value = _template_lookup(context, function_target)
            if not isinstance(target_value, (list, tuple, set)):
                target_items = [] if target_value is None else [str(target_value)]
            else:
                target_items = [str(item) for item in target_value]
            normalized_items = {item.strip().lower() for item in target_items}
            normalized_values = [value.strip().lower() for value in function_values]
            if function_name == "any":
                return any(value in normalized_items for value in normalized_values)
            return all(value in normalized_items for value in normalized_values)
        if function_name in {"exists", "empty"} and len(function_args) == 1:
            function_target = function_args[0]
            if function_name == "exists":
                return _condition_matches({"condition": f"exists {function_target}"}, context)
            return _condition_matches({"condition": f"empty {function_target}"}, context)
        if function_name in {"contains", "startswith", "endswith", "matches", "contains_cs", "startswith_cs", "endswith_cs", "matches_cs"} and len(function_args) == 2:
            function_target, function_value = function_args
            return _condition_matches({"condition": f'{function_target} {function_name} "{function_value}"'}, context)
        if function_name in {"not_contains", "not_startswith", "not_endswith", "not_matches", "not_contains_cs", "not_startswith_cs", "not_endswith_cs", "not_matches_cs"} and len(function_args) == 2:
            function_target, function_value = function_args
            positive_name = function_name.removeprefix("not_")
            return not _condition_matches({"condition": f'{function_target} {positive_name} "{function_value}"'}, context)
    if lowered.startswith("not "):
        return not _condition_matches({"condition": condition[4:].strip()}, context)
    if lowered.startswith("exists "):
        value = _template_lookup(context, condition[7:].strip())
        return value is not None and value != ""
    if lowered.startswith("empty "):
        value = _template_lookup(context, condition[6:].strip())
        if value is None:
            return True
        if isinstance(value, (str, bytes, list, tuple, set, dict)):
            return len(value) == 0
        return False
    for operator in (" not in ", " in "):
        if operator not in lowered:
            continue
        split_index = lowered.index(operator)
        left = condition[:split_index].strip()
        right = condition[split_index + len(operator):].strip()
        value = _template_lookup(context, left)
        options = parse_literal_list(right)
        if isinstance(value, (list, tuple, set)):
            actual_values = {str(item).strip().lower() for item in value}
            matches = any(option.lower() in actual_values for option in options)
        else:
            actual_text = "" if value is None else str(value).strip().lower()
            matches = actual_text in {option.lower() for option in options}
        return (not matches) if operator.strip() == "not in" else matches
    for operator in (" contains_cs ", " startswith_cs ", " endswith_cs ", " matches_cs ", " contains ", " startswith ", " endswith ", " matches "):
        if operator not in lowered:
            continue
        split_index = lowered.index(operator)
        left = condition[:split_index].strip()
        right = normalize_literal(condition[split_index + len(operator):].strip())
        value = _template_lookup(context, left)
        case_sensitive = operator.strip().endswith("_cs")
        base_operator = operator.strip().removesuffix("_cs")
        if base_operator == "contains":
            if isinstance(value, (list, tuple, set)):
                if case_sensitive:
                    return right in {str(item).strip() for item in value}
                return right.lower() in {str(item).strip().lower() for item in value}
            actual_text = "" if value is None else str(value)
            if case_sensitive:
                return right in actual_text
            return right.lower() in actual_text.lower()
        actual_text = "" if value is None else str(value).strip()
        if base_operator == "matches":
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                return re.search(right, "" if value is None else str(value), flags=flags) is not None
            except re.error:
                return False
        expected_text = right if case_sensitive else right.lower()
        candidate_text = actual_text if case_sensitive else actual_text.lower()
        if base_operator == "startswith":
            return candidate_text.startswith(expected_text)
        if base_operator == "endswith":
            return candidate_text.endswith(expected_text)
        return False
    for operator in (">=", "<=", "!=", ">", "<", "="):
        if operator not in condition:
            continue
        left, expected = condition.split(operator, 1)
        expected = normalize_literal(expected)
        left_value = _template_lookup(context, left.strip())
        if operator == "=":
            if isinstance(left_value, (dict, list)):
                actual = json.dumps(left_value, ensure_ascii=True, sort_keys=True)
            else:
                actual = "" if left_value is None else str(left_value)
            return actual.strip().lower() == expected.strip().lower()
        actual_num = numeric_expression_value(left.strip())
        expected_num = numeric_expression_value(expected.strip())
        if actual_num is None or expected_num is None:
            actual_text = "" if left_value is None else str(left_value).strip().lower()
            expected_text = expected.strip().lower()
            if operator == "!=":
                return actual_text != expected_text
            return False
        if operator == ">=":
            return actual_num >= expected_num
        if operator == "<=":
            return actual_num <= expected_num
        if operator == ">":
            return actual_num > expected_num
        if operator == "<":
            return actual_num < expected_num
        if operator == "!=":
            return actual_num != expected_num
        return False
    if "=" not in condition:
        return bool(_template_lookup(context, condition))
    return False


    def _record_workflow_run(record: dict[str, Any], run_record: dict[str, Any], *, append: bool) -> None:
        workflow_id = str(record.get("id") or "").strip()
        if append:
            _append_workflow_run(workflow_id, run_record)
            record["run_count"] = int(record.get("run_count") or 0) + 1
        else:
            runs = _workflow_runs(workflow_id, limit=200)
            replaced = False
            for index, row in enumerate(runs):
                if str(row.get("run_id") or "").strip() == str(run_record.get("run_id") or "").strip():
                    runs[index] = run_record
                    replaced = True
                    break
            if not replaced:
                runs.append(run_record)
            _rewrite_workflow_runs(workflow_id, runs)
        record["last_run_at"] = str(run_record.get("completed_at") or run_record.get("updated_at") or _now_iso())
        record["last_run_id"] = str(run_record.get("run_id") or "")
        record["updated_at"] = _now_iso()
        save_object(root, "workflows", workflow_id, record)


    def _execute_workflow(
        record: dict[str, Any],
        owner: str,
        *,
        run_record: dict[str, Any] | None = None,
        start_node_id: str | None = None,
        branch_outcome: str | None = None,
    ) -> dict[str, Any]:
        workflow_id = str(record.get("id") or "").strip()
        project_id = str(record.get("project_id") or "").strip()
        node_map, outgoing, starts = _workflow_graph(record)
        all_agents = list_objects(root, "agents", limit=500)
        agents_by_name = {
            str(row.get("name") or "").strip().lower(): row
            for row in all_agents
            if isinstance(row, dict) and str(row.get("name") or "").strip()
        }
        append_run = run_record is None
        if run_record is None:
            run_record = {
                "run_id": _slug("wfrun"),
                "workflow_id": workflow_id,
                "project_id": project_id,
                "name": str(record.get("name") or "").strip(),
                "owner": owner,
                "status": "running",
                "started_at": _now_iso(),
                "updated_at": _now_iso(),
                "generated_task_ids": [],
                "step_count": 0,
                "steps": [],
                "context": {"task_outputs": {}, "latest_output": None},
            }
        elif not isinstance(run_record.get("context"), dict):
            run_record["context"] = {"task_outputs": {}, "latest_output": None}
        run_id = str(run_record.get("run_id") or _slug("wfrun"))
        current_id = str(start_node_id or run_record.get("next_node_id") or (starts[0] if starts else "")).strip()
        next_outcome = str(branch_outcome or "").strip().lower() or None
        visited: set[str] = set()

        while current_id and current_id in node_map and current_id not in visited:
            visited.add(current_id)
            node = node_map[current_id]
            node_type = str(node.get("type") or "task").strip() or "task"
            label = str(node.get("label") or current_id).strip()
            assignee = str(node.get("assignee") or "").strip()
            input_template = str(node.get("input_template") or "").strip()
            template_context = _workflow_template_context(run_record)
            resolved_input = _render_input_template(input_template, template_context)
            eligible_agents = _eligible_agents_for_node(
                all_agents,
                project_id=project_id,
                node_type=node_type,
                label=label,
                assignee=assignee,
            )
            selected_agent = eligible_agents[0] if eligible_agents else None
            step: dict[str, Any] = {
                "step_id": _slug("wfstep"),
                "index": len(run_record["steps"]) + 1,
                "node_id": current_id,
                "type": node_type,
                "label": label,
                "timestamp": _now_iso(),
            }
            if input_template:
                step["input_template"] = input_template
                step["resolved_input"] = resolved_input
            if node_type in {"task", "research", "review"}:
                task_id = _slug("task")
                task_record = _stamp_record(
                    {
                        "id": task_id,
                        "project_id": project_id,
                        "title": label,
                        "assignee": assignee or str((selected_agent or {}).get("name") or node_type).strip() or node_type,
                        "risk_tier": "medium",
                        "workflow_id": workflow_id,
                        "workflow_run_id": run_id,
                        "node_id": current_id,
                        "assigned_agent_id": str((selected_agent or {}).get("id") or ""),
                        "preferred_models": (selected_agent or {}).get("model_preferences") if selected_agent else [],
                        "input_template": input_template,
                        "resolved_input": resolved_input,
                    },
                    owner=owner,
                    status="queued",
                )
                save_object(root, "tasks", task_id, task_record)
                run_record["generated_task_ids"].append(task_id)
                step["status"] = "queued"
                step["generated_task"] = {"id": task_id, "status": "queued"}
                step["execution_policy"] = {
                    "required_permission": _workflow_permission_for(node_type),
                    "selected_agent_id": str((selected_agent or {}).get("id") or ""),
                    "selected_agent_name": str((selected_agent or {}).get("name") or ""),
                    "preferred_models": (selected_agent or {}).get("model_preferences") if selected_agent else [],
                }
                step["message"] = "Execution paused pending task completion."
                run_record["steps"].append(step)
                run_record["step_count"] = len(run_record["steps"])
                run_record["status"] = "awaiting_task"
                run_record["pending_node_id"] = current_id
                run_record["awaiting_task_id"] = task_id
                run_record["updated_at"] = _now_iso()
                _record_workflow_run(record, run_record, append=append_run)
                _log_workspace_event(
                    "workflow_paused_for_task",
                    owner,
                    {"workflow_id": workflow_id, "workflow_run_id": run_id, "project_id": project_id, "task_id": task_id},
                )
                return run_record
            elif node_type == "approval":
                task_id = _slug("task")
                task_record = _stamp_record(
                    {
                        "id": task_id,
                        "project_id": project_id,
                        "title": label,
                        "assignee": assignee or str((selected_agent or {}).get("name") or "approval").strip() or "approval",
                        "risk_tier": "high",
                        "workflow_id": workflow_id,
                        "workflow_run_id": run_id,
                        "node_id": current_id,
                        "assigned_agent_id": str((selected_agent or {}).get("id") or ""),
                        "preferred_models": (selected_agent or {}).get("model_preferences") if selected_agent else [],
                    },
                    owner=owner,
                    status="awaiting_approval",
                )
                save_object(root, "tasks", task_id, task_record)
                run_record["generated_task_ids"].append(task_id)
                step["status"] = "awaiting_approval"
                step["generated_task"] = {"id": task_id, "status": "awaiting_approval"}
                step["message"] = "Execution paused pending approval."
                step["execution_policy"] = {
                    "required_permission": _workflow_permission_for(node_type),
                    "selected_agent_id": str((selected_agent or {}).get("id") or ""),
                    "selected_agent_name": str((selected_agent or {}).get("name") or ""),
                    "preferred_models": (selected_agent or {}).get("model_preferences") if selected_agent else [],
                }
                run_record["steps"].append(step)
                run_record["step_count"] = len(run_record["steps"])
                run_record["status"] = "awaiting_approval"
                run_record["pending_node_id"] = current_id
                run_record["awaiting_task_id"] = task_id
                run_record["updated_at"] = _now_iso()
                _record_workflow_run(record, run_record, append=append_run)
                _log_workspace_event(
                    "workflow_paused_for_approval",
                    owner,
                    {"workflow_id": workflow_id, "workflow_run_id": run_id, "project_id": project_id, "task_id": task_id},
                )
                return run_record
            elif node_type == "agent":
                agent = agents_by_name.get(label.lower()) or selected_agent
                step["status"] = "completed"
                step["agent"] = {
                    "matched": bool(agent),
                    "agent_id": str(agent.get("id") or "") if agent else "",
                    "role": str(agent.get("role") or "") if agent else "",
                    "permissions": agent.get("permissions") if agent else [],
                    "model_preferences": agent.get("model_preferences") if agent else [],
                }
                if isinstance(run_record.get("context"), dict):
                    step["context"] = {
                        "latest_output": run_record["context"].get("latest_output"),
                        "task_output_count": len(run_record["context"].get("task_outputs") or {}),
                    }
            elif node_type == "model_route":
                route_context = {
                    "project_id": project_id,
                    "workflow_id": workflow_id,
                    "workflow_run_id": run_id,
                }
                if selected_agent:
                    route_context["preferred_models"] = selected_agent.get("model_preferences") or []
                    route_context["agent_id"] = str(selected_agent.get("id") or "")
                if isinstance(run_record.get("context"), dict):
                    route_context["latest_output"] = run_record["context"].get("latest_output")
                    route_context["task_outputs"] = run_record["context"].get("task_outputs") or {}
                if resolved_input:
                    route_context["resolved_input"] = resolved_input
                decision = router.explain_route(
                    _workflow_task_type(node_type, label),
                    route_context,
                )
                step["status"] = "completed"
                step["route"] = {
                    "provider": decision.get("provider"),
                    "model_assigned": decision.get("model_assigned"),
                    "route_reasons": decision.get("route_reasons") or [],
                }
                step["execution_policy"] = {
                    "required_permission": _workflow_permission_for(node_type),
                    "selected_agent_id": str((selected_agent or {}).get("id") or ""),
                    "selected_agent_name": str((selected_agent or {}).get("name") or ""),
                    "preferred_models": (selected_agent or {}).get("model_preferences") if selected_agent else [],
                }
                step["context"] = {
                    "latest_output": route_context.get("latest_output"),
                    "task_output_count": len(route_context.get("task_outputs") or {}),
                }
                if resolved_input:
                    step["context"]["resolved_input"] = resolved_input
            elif node_type == "start":
                step["status"] = "completed"
                step["message"] = "Workflow execution started."
            elif node_type == "end":
                step["status"] = "completed"
                step["message"] = "Workflow execution completed."
                run_record["steps"].append(step)
                current_id = ""
                break
            else:
                step["status"] = "completed"
                step["message"] = f"Processed node type {node_type}."
            run_record["steps"].append(step)
            edges = outgoing.get(current_id, [])
            selection_hint = next_outcome
            if not selection_hint:
                selection_hint = "context:" + json.dumps(_workflow_template_context(run_record), ensure_ascii=True, sort_keys=True)
            current_id = _select_next_node_id(edges, selection_hint)
            next_outcome = None

        run_record["step_count"] = len(run_record["steps"])
        run_record["status"] = "completed"
        run_record["completed_at"] = _now_iso()
        run_record["updated_at"] = _now_iso()
        run_record.pop("pending_node_id", None)
        run_record.pop("awaiting_task_id", None)
        run_record.pop("next_node_id", None)
        _record_workflow_run(record, run_record, append=append_run)
        _log_workspace_event(
            "workflow_executed",
            owner,
            {
                "workflow_id": workflow_id,
                "workflow_run_id": run_id,
                "project_id": project_id,
                "generated_task_count": len(run_record.get("generated_task_ids") or []),
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

    legacy_html_routes: dict[str, tuple[Path, str]] = {
        "/index.html": (official_html_path, "official site"),
        "/local_hub.html": (hub_html_path, "local hub"),
        "/command_center.html": (command_center_html_path, "command center"),
        "/ophtxn_shell.html": (shell_html_path, "ophtxn shell"),
        "/ai_school.html": (ai_school_html_path, "ai school"),
        "/official_app.html": (studio_html_path, "studio page"),
        "/agent_view.html": (agent_view_html_path, "agent view"),
        "/daily_planner.html": (daily_planner_html_path, "daily planner"),
        "/comms_hub.html": (comms_hub_html_path, "comms hub"),
        "/rooms.html": (rooms_html_path, "rooms"),
        "/markets_terminal.html": (markets_terminal_html_path, "markets terminal"),
        "/trading_room.html": (trading_room_html_path, "trading room"),
        "/night_capital.html": (night_capital_html_path, "night capital"),
        "/press_kit.html": (press_html_path, "press kit"),
    }

    for route_path, (html_path, label) in legacy_html_routes.items():
        endpoint = "legacy_" + route_path.strip("/").replace(".", "_").replace("-", "_")

        def _make_legacy_handler(target_path: Path = html_path, target_label: str = label):
            def _handler() -> Any:
                return _serve_html(target_path, target_label)

            return _handler

        app.add_url_rule(route_path, endpoint=endpoint, view_func=_make_legacy_handler(), methods=["GET"])

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
                "output": payload.get("output") if "output" in payload else {},
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

    @app.patch("/api/tasks/<task_id>")
    def tasks_update(task_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        record = load_object(root, "tasks", task_id, {})
        if not isinstance(record, dict) or not record.get("id"):
            return jsonify({"ok": False, "error": "task not found"}), 404
        payload = request.get_json(silent=True) or {}
        owner = str(session.get("user_id") or "").strip()
        if "status" in payload:
            record["status"] = str(payload.get("status") or record.get("status") or "").strip()
        if "assignee" in payload:
            record["assignee"] = str(payload.get("assignee") or record.get("assignee") or "").strip()
        if "notes" in payload:
            record["notes"] = str(payload.get("notes") or "").strip()
        if "result" in payload:
            record["result"] = str(payload.get("result") or "").strip().lower()
        if "output" in payload:
            record["output"] = payload.get("output")
        task_result = str(record.get("result") or "").strip().lower()
        if task_result in {"success", "completed"}:
            record["status"] = "completed"
        elif task_result in {"failed", "needs_review", "rejected"}:
            record["status"] = "failed"
        record["updated_at"] = _now_iso()
        save_object(root, "tasks", task_id, record)

        workflow_id = str(record.get("workflow_id") or "").strip()
        run_id = str(record.get("workflow_run_id") or "").strip()
        node_id = str(record.get("node_id") or "").strip()
        owner = str(session.get("user_id") or "").strip()
        matching_run: dict[str, Any] | None = None
        resumed_run: dict[str, Any] | None = None
        if workflow_id and run_id and node_id:
            runs = _workflow_runs(workflow_id, limit=200)
            for run in runs:
                if str(run.get("run_id") or "").strip() != run_id:
                    continue
                matching_run = run
                for step in run.get("steps") or []:
                    task_ref = step.get("generated_task") if isinstance(step, dict) else None
                    if isinstance(task_ref, dict) and str(task_ref.get("id") or "").strip() == task_id:
                        task_ref["status"] = str(record.get("status") or "")
                        step["status"] = str(record.get("status") or "")
                        step["task_feedback"] = {
                            "status": str(record.get("status") or ""),
                            "result": str(record.get("result") or ""),
                            "notes": str(record.get("notes") or ""),
                            "output": record.get("output"),
                            "updated_at": _now_iso(),
                        }
                context = run.get("context")
                if not isinstance(context, dict):
                    context = {"task_outputs": {}, "latest_output": None}
                    run["context"] = context
                task_outputs = context.get("task_outputs")
                if not isinstance(task_outputs, dict):
                    task_outputs = {}
                    context["task_outputs"] = task_outputs
                task_payload = {
                    "task_id": task_id,
                    "node_id": node_id,
                    "status": str(record.get("status") or ""),
                    "result": str(record.get("result") or ""),
                    "output": record.get("output"),
                    "updated_at": _now_iso(),
                }
                task_outputs[node_id] = task_payload
                context["latest_output"] = record.get("output")
                run["updated_at"] = _now_iso()
            _rewrite_workflow_runs(workflow_id, runs)

        task_outcome = str(record.get("result") or record.get("status") or "").strip().lower()
        if (
            workflow_id
            and run_id
            and node_id
            and matching_run
            and str(matching_run.get("status") or "").strip() == "awaiting_task"
            and str(matching_run.get("awaiting_task_id") or "").strip() == task_id
            and task_outcome in {"completed", "failed", "success", "needs_review"}
        ):
            workflow_record = load_object(root, "workflows", workflow_id, {})
            if isinstance(workflow_record, dict) and workflow_record.get("id"):
                _node_map, outgoing, _starts = _workflow_graph(workflow_record)
                next_node_id = _select_next_node_id(outgoing.get(node_id, []), task_outcome)
                matching_run["task_outcome"] = task_outcome
                matching_run["next_node_id"] = next_node_id
                matching_run["updated_at"] = _now_iso()
                resumed_run = _execute_workflow(
                    workflow_record,
                    owner,
                    run_record=matching_run,
                    start_node_id=next_node_id,
                    branch_outcome=task_outcome,
                )
                _log_workspace_event(
                    "workflow_resumed_from_task",
                    owner,
                    {
                        "workflow_id": workflow_id,
                        "workflow_run_id": run_id,
                        "project_id": str(workflow_record.get("project_id") or ""),
                        "task_id": task_id,
                        "outcome": task_outcome,
                    },
                )

        _log_workspace_event(
            "task_updated",
            owner,
            {"task_id": task_id, "status": record.get("status", ""), "workflow_id": workflow_id, "workflow_run_id": run_id},
        )
        response: dict[str, Any] = {"ok": True, "task": record}
        if resumed_run:
            response["run"] = resumed_run
        return jsonify(response)

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

    @app.post("/api/workflows/<workflow_id>/runs/<run_id>/resume")
    def workflows_resume(workflow_id: str, run_id: str) -> Any:
        _token, session = _active_session()
        if not session:
            return jsonify({"ok": False, "error": "auth required"}), 401
        record = load_object(root, "workflows", workflow_id, {})
        if not isinstance(record, dict) or not record.get("id"):
            return jsonify({"ok": False, "error": "workflow not found"}), 404
        runs = _workflow_runs(workflow_id, limit=200)
        target_run = None
        for row in runs:
            if str(row.get("run_id") or "").strip() == run_id:
                target_run = row
                break
        if not isinstance(target_run, dict):
            return jsonify({"ok": False, "error": "run not found"}), 404
        if str(target_run.get("status") or "").strip() != "awaiting_approval":
            return jsonify({"ok": False, "error": "run is not awaiting approval"}), 400
        payload = request.get_json(silent=True) or {}
        outcome = str(payload.get("outcome") or "approved").strip().lower()
        if outcome not in {"approved", "rejected", "success", "needs_review"}:
            return jsonify({"ok": False, "error": "invalid outcome"}), 400
        pending_node_id = str(target_run.get("pending_node_id") or "").strip()
        if not pending_node_id:
            return jsonify({"ok": False, "error": "pending node missing"}), 400
        approval_task_id = str(target_run.get("awaiting_task_id") or "").strip()
        if approval_task_id:
            approval_task = load_object(root, "tasks", approval_task_id, {})
            if isinstance(approval_task, dict) and approval_task.get("id"):
                approval_task["status"] = outcome
                approval_task["updated_at"] = _now_iso()
                save_object(root, "tasks", approval_task_id, approval_task)
        _node_map, outgoing, _starts = _workflow_graph(record)
        next_node_id = _select_next_node_id(outgoing.get(pending_node_id, []), outcome)
        owner = str(session.get("user_id") or "").strip()
        target_run["approval_outcome"] = outcome
        target_run["next_node_id"] = next_node_id
        target_run["updated_at"] = _now_iso()
        run_record = _execute_workflow(record, owner, run_record=target_run, start_node_id=next_node_id, branch_outcome=outcome)
        _log_workspace_event(
            "workflow_resumed",
            owner,
            {"workflow_id": workflow_id, "workflow_run_id": run_id, "project_id": str(record.get("project_id") or ""), "outcome": outcome},
        )
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
