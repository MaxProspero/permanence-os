from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def ensure_root(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return payload


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def read_jsonl(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for raw in rows[-max(1, int(limit)):]:
        token = raw.strip()
        if not token:
            continue
        try:
            payload = json.loads(token)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def safe_object_id(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip("-_.").lower()
    return token or "item"


def collection_root(root: Path, collection: str) -> Path:
    return ensure_root(root / safe_object_id(collection))


def object_path(root: Path, collection: str, object_id: str) -> Path:
    return collection_root(root, collection) / f"{safe_object_id(object_id)}.json"


def save_object(root: Path, collection: str, object_id: str, payload: dict[str, Any]) -> Path:
    path = object_path(root, collection, object_id)
    save_json(path, payload)
    return path


def load_object(root: Path, collection: str, object_id: str, default: Any | None = None) -> Any:
    return load_json(object_path(root, collection, object_id), default if default is not None else {})


def list_objects(root: Path, collection: str, limit: int = 100) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    rows = sorted(collection_root(root, collection).glob("*.json"), key=lambda row: row.stat().st_mtime, reverse=True)
    for path in rows[: max(1, int(limit))]:
        payload = load_json(path, {})
        if isinstance(payload, dict):
            items.append(payload)
    return items


def append_activity_event(root: Path, payload: dict[str, Any]) -> None:
    append_jsonl(root / "activity.jsonl", payload)
