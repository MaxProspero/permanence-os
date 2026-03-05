#!/usr/bin/env python3
"""
Poll Telegram updates and route them into Permanence OS pipelines.

Default behavior:
- Reads bot token from PERMANENCE_TELEGRAM_BOT_TOKEN
- Reads target chat from --chat-id or PERMANENCE_TELEGRAM_CHAT_ID
- Converts incoming text/media messages into glasses-bridge events
- Stores poll offset state to avoid duplicate processing
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]

URL_RE = re.compile(r"https?://[^\s<>\"]+")
ID_SPLIT_RE = re.compile(r"[\s,]+")
WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9'-]{2,}")
CARD_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[\s-]?){13,19}(?!\d)")
STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "been",
    "before",
    "being",
    "between",
    "build",
    "could",
    "does",
    "dont",
    "from",
    "have",
    "into",
    "just",
    "know",
    "make",
    "more",
    "most",
    "need",
    "next",
    "only",
    "really",
    "should",
    "some",
    "that",
    "them",
    "there",
    "they",
    "this",
    "very",
    "want",
    "what",
    "when",
    "where",
    "which",
    "will",
    "with",
    "would",
    "your",
}
PROFILE_FIELD_ALIASES: dict[str, str] = {
    "name": "name",
    "mission": "mission",
    "goal": "goals",
    "goals": "goals",
    "strength": "strengths",
    "strengths": "strengths",
    "weakness": "growth_edges",
    "weaknesses": "growth_edges",
    "growth": "growth_edges",
    "growth-edge": "growth_edges",
    "growth-edges": "growth_edges",
    "workstyle": "work_style",
    "work-style": "work_style",
    "work_style": "work_style",
    "values": "values",
    "taste": "taste",
    "persona": "personality_mode",
    "personality": "personality_mode",
}
PROFILE_FIELDS_ORDER = (
    "name",
    "mission",
    "goals",
    "strengths",
    "growth_edges",
    "work_style",
    "values",
    "taste",
    "personality_mode",
)
PERSONALITY_MODES: dict[str, str] = {
    "adaptive": "Match the user's tone while staying clear and grounded.",
    "strategist": "Think in systems, leverage, tradeoffs, and sequencing.",
    "coach": "Encourage action, accountability, and consistency with empathy.",
    "operator": "Be direct, execution-focused, and prioritize speed with correctness.",
    "calm": "Use a composed, steady tone and reduce unnecessary urgency.",
    "creative": "Offer imaginative options while preserving practical next steps.",
}
MEMORY_SYNONYM_MAP: dict[str, set[str]] = {
    "deep": {"focus", "concentration"},
    "focus": {"deep", "concentration"},
    "plan": {"planning", "roadmap", "strategy"},
    "planning": {"plan", "strategy"},
    "outreach": {"sales", "prospecting", "followup", "follow-up"},
    "sales": {"outreach", "prospecting"},
    "habit": {"routine"},
    "routine": {"habit"},
    "stress": {"overwhelmed", "anxious", "pressure"},
    "execution": {"ship", "shipping", "deliver"},
    "learn": {"learning", "study"},
}
PAYMENT_URL_HINTS = (
    "stripe.com",
    "paypal.com",
    "squareup.com",
    "cash.app",
    "checkout",
    "billing",
    "payment_intent",
    "invoice",
)
PROFILE_HISTORY_MAX_ROWS = 300
PROFILE_CONFLICT_MAX_ROWS = 120
MODEL_PROVIDER_ALIASES: dict[str, str] = {
    "anthropic": "anthropic",
    "claude": "anthropic",
    "openai": "openai",
    "gpt": "openai",
    "xai": "xai",
    "grok": "xai",
    "ollama": "ollama",
    "local": "ollama",
    "qwen": "ollama",
}
MODEL_PROVIDER_ORDER = ("anthropic", "openai", "xai", "ollama")

try:
    from core.model_router import ModelRouter
except Exception:  # pragma: no cover - optional dependency
    ModelRouter = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value


def _keychain_secret(service: str, account: str) -> str:
    if sys.platform != "darwin":
        return ""
    if not service or not account:
        return ""
    proc = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return str(proc.stdout or "").strip()


def _inject_anthropic_key_from_keychain() -> None:
    current = str(os.getenv("ANTHROPIC_API_KEY", "")).strip()
    if current:
        return
    service = str(
        os.getenv("PERMANENCE_ANTHROPIC_KEYCHAIN_SERVICE", "permanence_os_anthropic_api_key")
    ).strip()
    account = str(os.getenv("PERMANENCE_ANTHROPIC_KEYCHAIN_ACCOUNT", os.getenv("USER", ""))).strip()
    secret = _keychain_secret(service=service, account=account)
    if secret:
        os.environ["ANTHROPIC_API_KEY"] = secret


def _normalize_model_provider(value: str) -> str:
    token = str(value or "").strip().lower()
    return MODEL_PROVIDER_ALIASES.get(token, "")


def _model_provider_fallbacks() -> list[str]:
    raw = str(os.getenv("PERMANENCE_MODEL_PROVIDER_FALLBACKS", "anthropic,openai,xai,ollama"))
    out: list[str] = []
    for item in raw.split(","):
        token = _normalize_model_provider(item)
        if token and token not in out:
            out.append(token)
    for token in MODEL_PROVIDER_ORDER:
        if token not in out:
            out.append(token)
    return out


def _update_env_key(path: Path, key: str, value: str) -> tuple[bool, str]:
    lines: list[str] = []
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            return False, str(exc)
    merged: list[str] = []
    updated = False
    for raw in lines:
        if "=" in raw and (not raw.lstrip().startswith("#")):
            env_key, _old = raw.split("=", 1)
            if env_key.strip() == key:
                merged.append(f"{key}={value}")
                updated = True
                continue
        merged.append(raw)
    if not updated:
        merged.append(f"{key}={value}")
    try:
        path.write_text("\n".join(merged).rstrip() + "\n", encoding="utf-8")
    except OSError as exc:
        return False, str(exc)
    return True, ""


def _provider_status_text(prefix: str = "/") -> str:
    provider = _normalize_model_provider(os.getenv("PERMANENCE_MODEL_PROVIDER", "anthropic")) or "anthropic"
    fallbacks = _model_provider_fallbacks()
    caps = str(os.getenv("PERMANENCE_MODEL_PROVIDER_CAPS_USD", "")).strip() or "-"
    lines = [
        f"Active model provider: {provider}",
        f"Fallback order: {', '.join(fallbacks)}",
        f"Provider caps: {caps}",
        f"Set provider with `{prefix}provider-set <anthropic|openai|xai|ollama>`.",
    ]
    return "\n".join(lines)


def _set_model_provider(provider_value: str) -> tuple[bool, str]:
    provider = _normalize_model_provider(provider_value)
    if provider not in MODEL_PROVIDER_ORDER:
        allowed = ", ".join(MODEL_PROVIDER_ORDER)
        return False, f"Unknown provider `{provider_value}`. Allowed: {allowed}."
    os.environ["PERMANENCE_MODEL_PROVIDER"] = provider
    env_path = BASE_DIR / ".env"
    ok, error = _update_env_key(env_path, "PERMANENCE_MODEL_PROVIDER", provider)
    if not ok:
        return False, f"Failed to update {env_path}: {error}"
    return True, f"Model provider set to `{provider}`."


_load_local_env()
_inject_anthropic_key_from_keychain()


def _working_dir() -> Path:
    return Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))


def _output_dir() -> Path:
    return Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))


def _tool_dir() -> Path:
    return Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))


def _default_state_path() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_TELEGRAM_CONTROL_STATE_PATH",
            str(_working_dir() / "telegram_control" / "state.json"),
        )
    )


def _default_download_dir() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_TELEGRAM_CONTROL_DOWNLOAD_DIR",
            str(_working_dir() / "telegram_control" / "downloads"),
        )
    )


def _default_transcription_queue_path() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_TRANSCRIPTION_QUEUE_PATH",
            str(_working_dir() / "transcription_queue.json"),
        )
    )


def _default_chat_history_path() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_TELEGRAM_CONTROL_CHAT_HISTORY_PATH",
            str(_working_dir() / "telegram_control" / "chat_history.json"),
        )
    )


def _default_memory_store_path() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_TELEGRAM_CONTROL_MEMORY_PATH",
            str(_working_dir() / "telegram_control" / "personal_memory.json"),
        )
    )


def _default_intake_path() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_TELEGRAM_CONTROL_INTAKE_PATH",
            str(_working_dir().parent / "inbox" / "telegram_share_intake.jsonl"),
        )
    )


def _default_terminal_queue_path() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_TELEGRAM_CONTROL_TERMINAL_QUEUE_PATH",
            os.getenv(
                "PERMANENCE_TERMINAL_TASK_QUEUE_PATH",
                str(_working_dir() / "telegram_terminal_tasks.jsonl"),
            ),
        )
    )


def _default_brain_vault_path() -> Path:
    return Path(
        os.getenv(
            "PERMANENCE_OPHTXN_BRAIN_PATH",
            str(_working_dir() / "ophtxn_brain_vault.json"),
        )
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _redaction_enabled() -> bool:
    return _is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_REDACT_SENSITIVE", "1"))


def _payment_link_redaction_enabled() -> bool:
    return _is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_REDACT_PAYMENT_LINKS", "1"))


def _luhn_valid(number: str) -> bool:
    digits = [int(ch) for ch in str(number or "") if ch.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    parity = len(digits) % 2
    for idx, digit in enumerate(digits):
        value = digit
        if idx % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _redact_sensitive_text(text: str) -> tuple[str, list[str]]:
    payload = str(text or "")
    if not payload:
        return "", []
    if not _redaction_enabled():
        return payload, []

    reasons: list[str] = []

    def _card_replacer(match: re.Match[str]) -> str:
        token = match.group(0)
        digits = "".join(ch for ch in token if ch.isdigit())
        if _luhn_valid(digits):
            if "card_number" not in reasons:
                reasons.append("card_number")
            return "[REDACTED_CARD_NUMBER]"
        return token

    scrubbed = CARD_CANDIDATE_RE.sub(_card_replacer, payload)

    if _payment_link_redaction_enabled():
        urls = list(dict.fromkeys(URL_RE.findall(scrubbed or "")))
        for url in urls:
            lowered = url.lower()
            if not any(hint in lowered for hint in PAYMENT_URL_HINTS):
                continue
            scrubbed = scrubbed.replace(url, "[REDACTED_PAYMENT_LINK]")
            if "payment_link" not in reasons:
                reasons.append("payment_link")

    return scrubbed, reasons


def _int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _imessage_mirror_enabled() -> bool:
    return _is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_MIRROR", "0"))


def _imessage_target() -> str:
    return str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_TARGET", "")).strip()


def _imessage_service() -> str:
    raw = str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_SERVICE", "iMessage")).strip().lower()
    if raw in {"sms", "text", "textmessage"}:
        return "SMS"
    return "iMessage"


def _send_imessage(
    *,
    target: str,
    text: str,
    service: str = "iMessage",
    timeout: int = 20,
) -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "iMessage/SMS mirror requires macOS"
    handle = str(target or "").strip()
    payload = str(text or "").strip()
    if not handle:
        return False, "iMessage target is empty"
    if not payload:
        return False, "iMessage payload is empty"
    service_name = "SMS" if str(service or "").strip().upper() == "SMS" else "iMessage"
    script = (
        "on run argv\n"
        "set targetHandle to item 1 of argv\n"
        "set messageText to item 2 of argv\n"
        "set preferredService to item 3 of argv\n"
        "tell application \"Messages\"\n"
        "set targetService to missing value\n"
        "if preferredService is \"SMS\" then\n"
        "try\n"
        "set targetService to first service whose service type = SMS\n"
        "end try\n"
        "end if\n"
        "if targetService is missing value then\n"
        "try\n"
        "set targetService to first service whose service type = iMessage\n"
        "end try\n"
        "end if\n"
        "if targetService is missing value then error \"No available Messages service\"\n"
        "set targetBuddy to buddy targetHandle of targetService\n"
        "send messageText to targetBuddy\n"
        "end tell\n"
        "return \"sent\"\n"
        "end run\n"
    )
    try:
        proc = subprocess.run(
            ["osascript", "-e", script, handle, payload, service_name],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(3, int(timeout)),
        )
    except Exception as exc:  # noqa: BLE001
        return False, str(exc).strip() or exc.__class__.__name__
    if proc.returncode != 0:
        return False, (proc.stderr or "").strip() or f"osascript exited {proc.returncode}"
    return True, (proc.stdout or "").strip() or "sent"


def _mirror_ack_to_imessage(text: str, timeout: int = 20) -> None:
    if not _imessage_mirror_enabled():
        return
    target = _imessage_target()
    if not target:
        return
    prefix = str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_PREFIX", "[Ophtxn]")).strip()
    payload = str(text or "").strip()
    if not payload:
        return
    if prefix:
        payload = f"{prefix} {payload}".strip()
    max_chars = max(120, _int_env("PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_MAX_CHARS", 1200))
    if len(payload) > max_chars:
        payload = payload[: max_chars - 3].rstrip() + "..."
    _ok, _detail = _send_imessage(
        target=target,
        text=payload,
        service=_imessage_service(),
        timeout=timeout,
    )


def _parse_id_allowlist(raw: str) -> set[str]:
    out: set[str] = set()
    for token in ID_SPLIT_RE.split(str(raw or "").strip()):
        value = token.strip()
        if not value:
            continue
        if value.lstrip("-").isdigit():
            out.add(value)
    return out


def _is_command_user_allowed(sender_user_id: str, allowed_user_ids: set[str]) -> bool:
    if not allowed_user_ids:
        return True
    token = str(sender_user_id or "").strip()
    return bool(token and token in allowed_user_ids)


def _is_command_chat_allowed(chat_id: str, allowed_chat_ids: set[str]) -> bool:
    if not allowed_chat_ids:
        return True
    token = str(chat_id or "").strip()
    return bool(token and token in allowed_chat_ids)


def _configured_target_chat_ids(cli_chat_id: str = "") -> set[str]:
    out: set[str] = set()
    control_scope_raw = os.getenv("PERMANENCE_TELEGRAM_CONTROL_TARGET_CHAT_IDS")
    if control_scope_raw is not None:
        out |= _parse_id_allowlist(control_scope_raw)
    else:
        env_multi = _parse_id_allowlist(os.getenv("PERMANENCE_TELEGRAM_CHAT_IDS", ""))
        env_single = str(os.getenv("PERMANENCE_TELEGRAM_CHAT_ID", "")).strip()
        out |= env_multi
        if env_single.lstrip("-").isdigit():
            out.add(env_single)
    out |= _parse_id_allowlist(str(cli_chat_id or ""))
    return out


def _is_public_command(command: str) -> bool:
    cmd = str(command or "").strip().lower()
    return cmd in {
        "help",
        "start",
        "comms-help",
        "whoami",
        "comms-whoami",
        "mode",
        "comms-mode",
        "memory-help",
        "memory",
        "remember",
        "share",
        "intake",
        "brain-dump",
        "recall",
        "profile",
        "profile-set",
        "profile-get",
        "profile-history",
        "profile-conflicts",
        "personality",
        "personality-modes",
        "habit-help",
        "habit-add",
        "habit-plan",
        "habit-done",
        "habit-nudge",
        "habit-list",
        "habit-drop",
        "forget-last",
        "terminal",
        "terminal-task",
        "task",
        "todo",
        "terminal-list",
        "task-list",
        "todo-list",
        "improve-status",
        "improve-pitch",
        "improve-list",
        "improve-approve",
        "improve-reject",
        "improve-defer",
        "platform-watch",
        "brain-status",
        "brain-sync",
        "brain-recall",
        "provider-status",
    }


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"offset": 0, "updated_at": "", "processed_updates": 0}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"offset": 0, "updated_at": "", "processed_updates": 0}
    if not isinstance(payload, dict):
        return {"offset": 0, "updated_at": "", "processed_updates": 0}
    return payload


def _save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _save_json_array(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def _load_chat_history(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for key, value in payload.items():
        if not isinstance(value, list):
            continue
        out[str(key)] = [row for row in value if isinstance(row, dict)]
    return out


def _save_chat_history(path: Path, payload: dict[str, list[dict[str, Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_memory_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"profiles": {}, "updated_at": ""}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"profiles": {}, "updated_at": ""}
    if not isinstance(payload, dict):
        return {"profiles": {}, "updated_at": ""}
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    out_profiles: dict[str, dict[str, Any]] = {}
    for key, value in profiles.items():
        if not isinstance(value, dict):
            continue
        notes = value.get("notes")
        if not isinstance(notes, list):
            notes = []
        habits = value.get("habits")
        if not isinstance(habits, list):
            habits = []
        profile_fields = value.get("profile_fields")
        if not isinstance(profile_fields, dict):
            profile_fields = {}
        profile_history = value.get("profile_history")
        if not isinstance(profile_history, list):
            profile_history = []
        profile_conflicts = value.get("profile_conflicts")
        if not isinstance(profile_conflicts, list):
            profile_conflicts = []
        out_profiles[str(key)] = {
            "chat_id": str(value.get("chat_id") or "").strip(),
            "sender_user_id": str(value.get("sender_user_id") or "").strip(),
            "sender": str(value.get("sender") or "").strip(),
            "notes": [row for row in notes if isinstance(row, dict)],
            "habits": [row for row in habits if isinstance(row, dict)],
            "profile_fields": {str(k): str(v) for k, v in profile_fields.items() if isinstance(k, str)},
            "profile_history": [row for row in profile_history if isinstance(row, dict)],
            "profile_conflicts": [row for row in profile_conflicts if isinstance(row, dict)],
            "updated_at": str(value.get("updated_at") or "").strip(),
        }
    return {
        "profiles": out_profiles,
        "updated_at": str(payload.get("updated_at") or "").strip(),
    }


def _save_memory_store(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _memory_key(chat_id: str, sender_user_id: str, sender_name: str) -> str:
    uid = str(sender_user_id or "").strip()
    if uid.lstrip("-").isdigit():
        return f"user:{uid}"
    base = f"{chat_id.strip()}|{sender_name.strip().lower()}"
    return "anon:" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _memory_profile(store: dict[str, Any], key: str) -> dict[str, Any]:
    profiles = store.setdefault("profiles", {})
    profile = profiles.get(key)
    if not isinstance(profile, dict):
        profile = {
            "chat_id": "",
            "sender_user_id": "",
            "sender": "",
            "notes": [],
            "habits": [],
            "profile_fields": {},
            "profile_history": [],
            "profile_conflicts": [],
            "updated_at": "",
        }
        profiles[key] = profile
    notes = profile.get("notes")
    if not isinstance(notes, list):
        notes = []
        profile["notes"] = notes
    profile_history = profile.get("profile_history")
    if not isinstance(profile_history, list):
        profile["profile_history"] = []
    profile_conflicts = profile.get("profile_conflicts")
    if not isinstance(profile_conflicts, list):
        profile["profile_conflicts"] = []
    return profile


def _default_personality_mode() -> str:
    raw = str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_CHAT_PERSONALITY_DEFAULT", "adaptive")).strip().lower()
    if raw in {"default", "balanced"}:
        raw = "adaptive"
    if raw in PERSONALITY_MODES:
        return raw
    return "adaptive"


def _profile_fields(profile: dict[str, Any]) -> dict[str, str]:
    raw = profile.get("profile_fields")
    fields = raw if isinstance(raw, dict) else {}
    out: dict[str, str] = {}
    for key in PROFILE_FIELDS_ORDER:
        value = str(fields.get(key) or "").strip()
        out[key] = value
    if out["personality_mode"] not in PERSONALITY_MODES:
        out["personality_mode"] = _default_personality_mode()
    profile["profile_fields"] = out
    return out


def _profile_history_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    raw = profile.get("profile_history")
    rows = raw if isinstance(raw, list) else []
    cleaned = [row for row in rows if isinstance(row, dict)]
    profile["profile_history"] = cleaned
    return cleaned


def _profile_conflict_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    raw = profile.get("profile_conflicts")
    rows = raw if isinstance(raw, list) else []
    cleaned = [row for row in rows if isinstance(row, dict)]
    profile["profile_conflicts"] = cleaned
    return cleaned


def _profile_field_label(field_key: str) -> str:
    labels = {
        "name": "Name",
        "mission": "Mission",
        "goals": "Goals",
        "strengths": "Strengths",
        "growth_edges": "Growth Edges",
        "work_style": "Work Style",
        "values": "Values",
        "taste": "Taste",
        "personality_mode": "Personality",
    }
    return labels.get(str(field_key or "").strip(), str(field_key or "").strip())


def _profile_log_change(profile: dict[str, Any], field_key: str, previous: str, new_value: str) -> None:
    rows = _profile_history_rows(profile)
    rows.append(
        {
            "id": "PH-" + hashlib.sha1(f"{field_key}|{_now_iso()}|{new_value}".encode("utf-8")).hexdigest()[:12],
            "field": str(field_key or "").strip(),
            "previous": str(previous or "").strip(),
            "value": str(new_value or "").strip(),
            "timestamp": _now_iso(),
        }
    )
    if len(rows) > PROFILE_HISTORY_MAX_ROWS:
        del rows[:-PROFILE_HISTORY_MAX_ROWS]


def _profile_log_conflict(profile: dict[str, Any], field_key: str, previous: str, new_value: str) -> None:
    if not str(previous or "").strip():
        return
    if str(previous or "").strip() == str(new_value or "").strip():
        return
    rows = _profile_conflict_rows(profile)
    rows.append(
        {
            "id": "PC-" + hashlib.sha1(f"{field_key}|{_now_iso()}|{new_value}".encode("utf-8")).hexdigest()[:12],
            "field": str(field_key or "").strip(),
            "previous": str(previous or "").strip(),
            "current": str(new_value or "").strip(),
            "status": "open",
            "timestamp": _now_iso(),
        }
    )
    if len(rows) > PROFILE_CONFLICT_MAX_ROWS:
        del rows[:-PROFILE_CONFLICT_MAX_ROWS]


def _profile_history_text(profile: dict[str, Any], field_alias: str = "", prefix: str = "/") -> str:
    rows = _profile_history_rows(profile)
    if not rows:
        return f"No profile history yet. Update a field with `{prefix}profile-set`."
    target = ""
    alias = str(field_alias or "").strip().lower().replace("_", "-")
    if alias:
        mapped = PROFILE_FIELD_ALIASES.get(alias)
        if not mapped:
            available = ", ".join(sorted(set(PROFILE_FIELD_ALIASES.keys())))
            return f"Unknown field `{field_alias}`. Available: {available}"
        target = mapped
    filtered = [
        row for row in rows
        if (not target) or (str(row.get("field") or "").strip() == target)
    ]
    if not filtered:
        return f"No profile history for `{target}`."
    lines = ["Profile history:"]
    for row in filtered[-12:]:
        item_id = str(row.get("id") or "-").strip()
        field = _profile_field_label(str(row.get("field") or "").strip())
        previous = str(row.get("previous") or "").strip() or "-"
        value = str(row.get("value") or "").strip() or "-"
        lines.append(f"- {item_id} | {field}: `{previous}` -> `{value}`")
    lines.append(f"Tip: use `{prefix}profile-conflicts` to review contradictory updates.")
    return "\n".join(lines)


def _profile_conflicts_text(profile: dict[str, Any], prefix: str = "/") -> str:
    rows = _profile_conflict_rows(profile)
    open_rows = [row for row in rows if str(row.get("status") or "").strip().lower() != "resolved"]
    if not open_rows:
        return (
            "No open profile conflicts.\n"
            f"Use `{prefix}profile-set <field> <value>` to keep profile current."
        )
    lines = ["Open profile conflicts:"]
    for row in open_rows[-10:]:
        item_id = str(row.get("id") or "-").strip()
        field = _profile_field_label(str(row.get("field") or "").strip())
        previous = str(row.get("previous") or "").strip() or "-"
        current = str(row.get("current") or "").strip() or "-"
        lines.append(f"- {item_id} | {field}: `{previous}` vs `{current}`")
    lines.append(f"Use `{prefix}profile-history` to audit field changes and set the final value.")
    return "\n".join(lines)


def _memory_habits(profile: dict[str, Any]) -> list[dict[str, Any]]:
    raw = profile.get("habits")
    rows = raw if isinstance(raw, list) else []
    cleaned = [row for row in rows if isinstance(row, dict)]
    profile["habits"] = cleaned
    return cleaned


def _habit_key(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def _habit_find_index(habits: list[dict[str, Any]], name: str) -> int:
    needle = _habit_key(name)
    if not needle:
        return -1
    for idx, row in enumerate(habits):
        if _habit_key(str(row.get("name") or "")) == needle:
            return idx
    return -1


def _habit_days_since_last_done(habit: dict[str, Any], today: datetime | None = None) -> int:
    current = (today or _now()).date()
    last_raw = str(habit.get("last_done_date") or "").strip()
    if not last_raw:
        return 9999
    try:
        last_date = datetime.fromisoformat(last_raw).date()
    except ValueError:
        return 9999
    delta = current.toordinal() - last_date.toordinal()
    return max(0, delta)


def _parse_habit_spec(raw: str) -> dict[str, str]:
    text = str(raw or "").strip()
    if not text:
        return {"name": "", "cue": "", "plan": "", "window": ""}
    segments = [segment.strip() for segment in text.split("|") if segment.strip()]
    if not segments:
        return {"name": "", "cue": "", "plan": "", "window": ""}
    out = {"name": " ".join(segments[0].split()), "cue": "", "plan": "", "window": ""}
    for segment in segments[1:]:
        key = ""
        value = segment
        if ":" in segment:
            key, value = segment.split(":", 1)
        elif "=" in segment:
            key, value = segment.split("=", 1)
        key_norm = str(key or "").strip().lower().replace("_", "-")
        payload = " ".join(str(value or "").strip().split())
        if not payload:
            continue
        if key_norm in {"cue", "trigger"}:
            out["cue"] = payload
            continue
        if key_norm in {"plan", "if-then", "ifthen", "implementation-intention"}:
            out["plan"] = payload
            continue
        if key_norm in {"window", "time", "cadence"}:
            out["window"] = payload
            continue
    if len(out["name"]) > 100:
        out["name"] = out["name"][:97].rstrip() + "..."
    if len(out["cue"]) > 140:
        out["cue"] = out["cue"][:137].rstrip() + "..."
    if len(out["plan"]) > 220:
        out["plan"] = out["plan"][:217].rstrip() + "..."
    if len(out["window"]) > 80:
        out["window"] = out["window"][:77].rstrip() + "..."
    return out


def _habit_add(profile: dict[str, Any], habit_name: str) -> tuple[bool, str]:
    parsed = _parse_habit_spec(habit_name)
    name = str(parsed.get("name") or "").strip()
    if not name:
        return False, "Usage: /habit-add <habit name>"
    habits = _memory_habits(profile)
    if _habit_find_index(habits, name) >= 0:
        return False, f"Habit already exists: {name}"
    habits.append(
        {
            "name": name,
            "cue": str(parsed.get("cue") or "").strip(),
            "plan": str(parsed.get("plan") or "").strip(),
            "window": str(parsed.get("window") or "").strip(),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "last_done_date": "",
            "streak": 0,
            "best_streak": 0,
            "total_checkins": 0,
        }
    )
    segments: list[str] = [f"Habit added: {name}"]
    cue = str(parsed.get("cue") or "").strip()
    plan = str(parsed.get("plan") or "").strip()
    window = str(parsed.get("window") or "").strip()
    if cue:
        segments.append(f"cue={cue}")
    if plan:
        segments.append(f"plan={plan}")
    if window:
        segments.append(f"window={window}")
    return True, " | ".join(segments)


def _habit_update_plan(profile: dict[str, Any], habit_spec: str, prefix: str = "/") -> tuple[bool, str]:
    parsed = _parse_habit_spec(habit_spec)
    name = str(parsed.get("name") or "").strip()
    if not name:
        return False, f"Usage: {prefix}habit-plan <habit name> | cue: <trigger> | plan: <if-then>"
    habits = _memory_habits(profile)
    idx = _habit_find_index(habits, name)
    if idx < 0:
        return False, f"Habit not found: {name}"
    habit = habits[idx]
    changed = False
    for key in ("cue", "plan", "window"):
        incoming = str(parsed.get(key) or "").strip()
        if not incoming:
            continue
        current = str(habit.get(key) or "").strip()
        if current == incoming:
            continue
        habit[key] = incoming
        changed = True
    if not changed:
        return False, "No habit plan changes detected."
    habit["updated_at"] = _now_iso()
    cue = str(habit.get("cue") or "").strip() or "-"
    plan = str(habit.get("plan") or "").strip() or "-"
    window = str(habit.get("window") or "").strip() or "-"
    return True, f"Updated `{habit.get('name')}` plan. cue={cue} | plan={plan} | window={window}"


def _habit_mark_done(profile: dict[str, Any], habit_name: str, today_iso: str = "") -> tuple[bool, str]:
    name = " ".join(str(habit_name or "").strip().split())
    if not name:
        return False, "Usage: /habit-done <habit name>"
    habits = _memory_habits(profile)
    idx = _habit_find_index(habits, name)
    if idx < 0:
        return False, f"Habit not found: {name}"
    habit = habits[idx]
    if str(today_iso or "").strip():
        try:
            today = datetime.fromisoformat(str(today_iso).strip()).date()
        except ValueError:
            today = _now().date()
    else:
        today = _now().date()
    yesterday = today.fromordinal(today.toordinal() - 1)
    last_raw = str(habit.get("last_done_date") or "").strip()
    if last_raw:
        try:
            last_date = datetime.fromisoformat(last_raw).date()
        except ValueError:
            last_date = None
    else:
        last_date = None
    if last_date == today:
        streak = max(1, _safe_int(habit.get("streak"), 0))
        habit["streak"] = streak
        habit["best_streak"] = max(streak, _safe_int(habit.get("best_streak"), 0))
        habit["updated_at"] = _now_iso()
        return False, f"Already checked today. Current streak: {streak}"
    if last_date == yesterday:
        streak = max(1, _safe_int(habit.get("streak"), 0)) + 1
    else:
        streak = 1
    habit["streak"] = streak
    habit["best_streak"] = max(streak, _safe_int(habit.get("best_streak"), 0))
    habit["last_done_date"] = today.isoformat()
    habit["updated_at"] = _now_iso()
    habit["total_checkins"] = max(0, _safe_int(habit.get("total_checkins"), 0)) + 1
    return True, f"Logged `{habit.get('name')}`. Streak: {streak}"


def _habit_drop(profile: dict[str, Any], habit_name: str) -> tuple[bool, str]:
    name = " ".join(str(habit_name or "").strip().split())
    if not name:
        return False, "Usage: /habit-drop <habit name>"
    habits = _memory_habits(profile)
    idx = _habit_find_index(habits, name)
    if idx < 0:
        return False, f"Habit not found: {name}"
    removed = str((habits.pop(idx) or {}).get("name") or "").strip() or name
    return True, f"Habit removed: {removed}"


def _habit_list_text(profile: dict[str, Any], prefix: str = "/") -> str:
    habits = _memory_habits(profile)
    if not habits:
        return (
            "No habits tracked yet.\n"
            f"Add one with `{prefix}habit-add <habit name>`."
        )
    ordered = sorted(
        habits,
        key=lambda row: (
            -_safe_int(row.get("streak"), 0),
            str(row.get("last_done_date") or ""),
            str(row.get("name") or "").lower(),
        ),
    )
    lines = ["Habit tracker:"]
    for row in ordered[:20]:
        name = str(row.get("name") or "-").strip()
        streak = max(0, _safe_int(row.get("streak"), 0))
        best_streak = max(0, _safe_int(row.get("best_streak"), 0))
        last_done = str(row.get("last_done_date") or "-").strip() or "-"
        total = max(0, _safe_int(row.get("total_checkins"), 0))
        cue = str(row.get("cue") or "").strip()
        plan = str(row.get("plan") or "").strip()
        window = str(row.get("window") or "").strip()
        row_text = f"- {name} | streak={streak} | best={best_streak} | last={last_done} | total={total}"
        if cue:
            row_text += f" | cue={cue}"
        if plan:
            row_text += f" | plan={plan}"
        if window:
            row_text += f" | window={window}"
        lines.append(row_text)
    lines.append(f"Tip: add/refresh cue-plan with `{prefix}habit-plan <habit> | cue: ... | plan: ...`.")
    return "\n".join(lines)


def _habit_nudge_text(profile: dict[str, Any], prefix: str = "/") -> str:
    habits = _memory_habits(profile)
    if not habits:
        return (
            "No habits to nudge yet.\n"
            f"Create one with `{prefix}habit-add <name> | cue: ... | plan: ...`."
        )
    ordered = sorted(
        habits,
        key=lambda row: (
            -_habit_days_since_last_done(row),
            -_safe_int(row.get("streak"), 0),
            str(row.get("name") or "").lower(),
        ),
    )
    lines = ["Habit nudges:"]
    for row in ordered[:8]:
        name = str(row.get("name") or "").strip() or "habit"
        days = _habit_days_since_last_done(row)
        cue = str(row.get("cue") or "").strip()
        plan = str(row.get("plan") or "").strip()
        window = str(row.get("window") or "").strip()
        if days == 0:
            status = "already checked today"
        elif days >= 9999:
            status = "not started yet"
        else:
            status = f"{days} day(s) since last check-in"
        action = plan or f"If this cue happens, do one rep of `{name}` now."
        text = f"- {name}: {status} | next={action}"
        if cue:
            text += f" | cue={cue}"
        if window:
            text += f" | window={window}"
        lines.append(text)
    return "\n".join(lines)


def _profile_set_field(profile: dict[str, Any], field_alias: str, value: str) -> tuple[bool, str]:
    alias = str(field_alias or "").strip().lower().replace("_", "-")
    target = PROFILE_FIELD_ALIASES.get(alias)
    if not target:
        available = ", ".join(sorted(set(PROFILE_FIELD_ALIASES.keys())))
        return False, f"Unknown profile field `{field_alias}`. Available: {available}"
    cleaned = " ".join(str(value or "").strip().split())
    if not cleaned:
        return False, f"Usage: /profile-set {target} <value>"
    fields = _profile_fields(profile)
    if target == "personality_mode":
        normalized = cleaned.lower().replace("_", "-").strip()
        if normalized in {"default", "balanced"}:
            normalized = "adaptive"
        if normalized not in PERSONALITY_MODES:
            modes = ", ".join(sorted(PERSONALITY_MODES.keys()))
            return False, f"Unknown personality mode `{cleaned}`. Available: {modes}"
        cleaned = normalized
    if len(cleaned) > 300:
        cleaned = cleaned[:297].rstrip() + "..."
    previous = str(fields.get(target) or "").strip()
    fields[target] = cleaned
    profile["profile_fields"] = fields
    if previous == cleaned:
        return False, f"Profile `{target}` unchanged."
    _profile_log_change(profile, field_key=target, previous=previous, new_value=cleaned)
    _profile_log_conflict(profile, field_key=target, previous=previous, new_value=cleaned)
    return True, f"Profile `{target}` updated."


def _profile_lines(profile: dict[str, Any]) -> list[str]:
    fields = _profile_fields(profile)
    lines: list[str] = []
    for key in PROFILE_FIELDS_ORDER:
        value = str(fields.get(key) or "").strip()
        if not value:
            continue
        lines.append(f"- {_profile_field_label(key)}: {value}")
    return lines


def _profile_view_text(profile: dict[str, Any], prefix: str = "/") -> str:
    lines = _profile_lines(profile)
    if not lines:
        return (
            "Profile fields are empty.\n"
            f"Set values with `{prefix}profile-set goals <value>`."
        )
    return "Profile snapshot:\n" + "\n".join(lines)


def _keyword_set(text: str) -> set[str]:
    out: set[str] = set()
    for token in WORD_RE.findall(str(text or "")):
        word = token.casefold()
        if len(word) < 3 or word in STOP_WORDS:
            continue
        out.add(word)
    return out


def _expanded_keyword_set(text: str) -> set[str]:
    base = _keyword_set(text)
    if not base:
        return set()
    expanded = set(base)
    for token in list(base):
        for synonym in MEMORY_SYNONYM_MAP.get(token, set()):
            expanded.add(synonym)
        for root, values in MEMORY_SYNONYM_MAP.items():
            if token in values:
                expanded.add(root)
                expanded |= values
    return expanded


def _memory_similarity_score(query: str, note_text: str) -> float:
    query_fold = str(query or "").strip().casefold()
    text_fold = str(note_text or "").strip().casefold()
    if not query_fold or not text_fold:
        return 0.0
    query_tokens = _expanded_keyword_set(query_fold)
    note_tokens = _expanded_keyword_set(text_fold)
    overlap = float(len(query_tokens & note_tokens))
    denom = float(len(query_tokens | note_tokens) or 1)
    jaccard = overlap / denom
    fuzzy = difflib.SequenceMatcher(None, query_fold, text_fold).ratio()
    phrase_bonus = 0.0
    if query_fold in text_fold:
        phrase_bonus += 1.0
    if any(token and token in text_fold for token in query_tokens):
        phrase_bonus += 0.35
    return (overlap * 2.5) + (jaccard * 1.8) + (fuzzy * 1.2) + phrase_bonus


def _select_memory_notes(notes: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    cap = max(1, int(limit))
    if not notes:
        return []
    query_text = " ".join(str(query or "").strip().split())
    query_tokens = _expanded_keyword_set(query_text)
    selected_indexes: list[int] = []
    if query_text:
        scored: list[tuple[float, int]] = []
        total = max(1, len(notes))
        for idx, row in enumerate(notes):
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            overlap = len(query_tokens & _expanded_keyword_set(text))
            semantic = _memory_similarity_score(query_text, text)
            if overlap <= 0 and semantic < 0.65:
                continue
            recency = float(idx + 1) / float(total)
            source = str(row.get("source") or "").strip().lower()
            source_bonus = {
                "manual": 0.45,
                "profile": 0.55,
                "chat": 0.2,
            }.get(source, 0.1)
            score = float(overlap * 2.0) + semantic + (recency * 0.8) + source_bonus
            scored.append((score, idx))
        for _score, idx in sorted(scored, key=lambda item: (-item[0], -item[1]))[:cap]:
            selected_indexes.append(idx)
    selected = set(selected_indexes)
    if len(selected_indexes) < cap:
        for idx in range(len(notes) - 1, -1, -1):
            if idx in selected:
                continue
            selected_indexes.append(idx)
            selected.add(idx)
            if len(selected_indexes) >= cap:
                break
    return [notes[idx] for idx in sorted(selected_indexes)]


def _memory_context_notes(store: dict[str, Any], key: str, query: str, limit: int) -> list[dict[str, Any]]:
    profile = _memory_profile(store, key)
    notes = profile.get("notes")
    rows = [row for row in notes if isinstance(row, dict)] if isinstance(notes, list) else []
    return _select_memory_notes(rows, query=query, limit=limit)


def _habit_prompt_lines(profile: dict[str, Any], limit: int = 8) -> list[str]:
    habits = _memory_habits(profile)
    if not habits:
        return []
    ordered = sorted(
        habits,
        key=lambda row: (
            -_safe_int(row.get("streak"), 0),
            str(row.get("last_done_date") or ""),
            str(row.get("name") or "").lower(),
        ),
    )
    out: list[str] = []
    for row in ordered[: max(1, int(limit))]:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        streak = max(0, _safe_int(row.get("streak"), 0))
        last_done = str(row.get("last_done_date") or "-").strip() or "-"
        cue = str(row.get("cue") or "").strip()
        plan = str(row.get("plan") or "").strip()
        row_text = f"- {name} (streak={streak}, last_done={last_done})"
        if cue:
            row_text += f" cue={cue}"
        if plan:
            row_text += f" plan={plan}"
        out.append(row_text)
    return out


def _memory_add_note(
    *,
    store: dict[str, Any],
    key: str,
    chat_id: str,
    sender_user_id: str,
    sender_name: str,
    text: str,
    source: str,
    max_notes: int,
) -> bool:
    scrubbed, _reasons = _redact_sensitive_text(str(text or ""))
    payload = " ".join(scrubbed.strip().split())
    if not payload:
        return False
    if len(payload) > 600:
        payload = payload[:597].rstrip() + "..."
    profile = _memory_profile(store, key)
    profile["chat_id"] = str(chat_id or "").strip()
    profile["sender_user_id"] = str(sender_user_id or "").strip()
    profile["sender"] = str(sender_name or "").strip()
    notes = profile.get("notes")
    if not isinstance(notes, list):
        notes = []
        profile["notes"] = notes
    folded = payload.casefold()
    recent = [str(row.get("text") or "").strip().casefold() for row in notes[-25:] if isinstance(row, dict)]
    if folded in recent:
        profile["updated_at"] = _now_iso()
        store["updated_at"] = _now_iso()
        return False
    notes.append(
        {
            "text": payload,
            "source": str(source or "manual").strip() or "manual",
            "timestamp": _now_iso(),
        }
    )
    cap = max(20, int(max_notes))
    if len(notes) > cap:
        del notes[:-cap]
    profile["updated_at"] = _now_iso()
    store["updated_at"] = _now_iso()
    return True


def _append_intake_entry(
    *,
    intake_path: Path,
    chat_id: str,
    sender_user_id: str,
    sender_name: str,
    text: str,
    source: str = "telegram-share",
) -> tuple[bool, str]:
    scrubbed, reasons = _redact_sensitive_text(str(text or ""))
    payload = scrubbed.strip()
    if not payload:
        return False, "intake text is empty"
    entry = {
        "intake_id": "INT-" + hashlib.sha1(f"{_now_iso()}|{chat_id}|{sender_user_id}|{payload}".encode("utf-8")).hexdigest()[:12],
        "timestamp": _now_iso(),
        "chat_id": str(chat_id or "").strip(),
        "sender_user_id": str(sender_user_id or "").strip(),
        "sender": str(sender_name or "").strip(),
        "source": str(source or "telegram-share").strip() or "telegram-share",
        "text": payload,
        "char_count": len(payload),
        "sanitized": bool(reasons),
        "sanitize_reasons": reasons,
    }
    try:
        intake_path.parent.mkdir(parents=True, exist_ok=True)
        with intake_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    except OSError as exc:
        return False, str(exc)
    return True, str(entry["intake_id"])


def _append_terminal_task(
    *,
    queue_path: Path,
    chat_id: str,
    sender_user_id: str,
    sender_name: str,
    text: str,
    source: str = "telegram-terminal",
) -> tuple[bool, str]:
    scrubbed, reasons = _redact_sensitive_text(str(text or ""))
    payload = " ".join(scrubbed.split())
    if not payload:
        return False, "terminal task text is empty"
    task_id = "TERM-" + hashlib.sha1(f"{_now_iso()}|{chat_id}|{sender_user_id}|{payload}".encode("utf-8")).hexdigest()[:12]
    entry = {
        "task_id": task_id,
        "timestamp": _now_iso(),
        "status": "PENDING",
        "chat_id": str(chat_id or "").strip(),
        "sender_user_id": str(sender_user_id or "").strip(),
        "sender": str(sender_name or "").strip(),
        "source": str(source or "telegram-terminal").strip() or "telegram-terminal",
        "text": payload,
        "char_count": len(payload),
        "sanitized": bool(reasons),
        "sanitize_reasons": reasons,
    }
    try:
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        with queue_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    except OSError as exc:
        return False, str(exc)
    return True, task_id


def _terminal_queue_recent(queue_path: Path, limit: int = 5) -> list[dict[str, Any]]:
    if not queue_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        raw_lines = queue_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    for raw in raw_lines[-400:]:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    if not rows:
        return []
    cap = max(1, int(limit))
    return rows[-cap:]


def _memory_recent_notes(store: dict[str, Any], key: str, limit: int) -> list[dict[str, Any]]:
    profile = _memory_profile(store, key)
    notes = profile.get("notes")
    if not isinstance(notes, list):
        return []
    cap = max(0, int(limit))
    if cap <= 0:
        return []
    return [row for row in notes[-cap:] if isinstance(row, dict)]


def _memory_help_text(prefix: str = "/") -> str:
    return (
        "Memory commands:\n"
        f"- {prefix}memory\n"
        f"- {prefix}remember <note>\n"
        f"- {prefix}share <long note>\n"
        f"- {prefix}recall\n"
        f"- {prefix}profile\n"
        f"- {prefix}profile-set <field> <value>\n"
        f"- {prefix}profile-get\n"
        f"- {prefix}profile-history [field]\n"
        f"- {prefix}profile-conflicts\n"
        f"- {prefix}personality [mode]\n"
        f"- {prefix}personality-modes\n"
        f"- {prefix}habit-add <name> | cue: <trigger> | plan: <if-then>\n"
        f"- {prefix}habit-plan <name> | cue: <trigger> | plan: <if-then>\n"
        f"- {prefix}habit-done <name>\n"
        f"- {prefix}habit-nudge\n"
        f"- {prefix}habit-list\n"
        f"- {prefix}habit-drop <name>\n"
        f"- {prefix}terminal <task>\n"
        f"- {prefix}terminal-list\n"
        f"- {prefix}provider-status\n"
        f"- {prefix}provider-set <anthropic|openai|xai|ollama>\n"
        f"- {prefix}forget-last"
    )


def _load_brain_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    chunks = payload.get("chunks")
    if not isinstance(chunks, list):
        return []
    return [row for row in chunks if isinstance(row, dict)]


def _brain_note_text(row: dict[str, Any]) -> str:
    source = str(row.get("source") or "").strip()
    text = str(row.get("text") or "").strip()
    if not text:
        return ""
    if source:
        return f"[{source}] {text}"
    return text


def _brain_context_notes(
    chunks: list[dict[str, Any]],
    *,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    query_text = " ".join(str(query or "").strip().split()).lower()
    if not query_text:
        return []
    query_tokens = {token.casefold() for token in WORD_RE.findall(query_text)}
    if not query_tokens and not query_text:
        return []
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in chunks:
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        lowered = text.lower()
        source = str(row.get("source") or "").lower()
        row_tokens = row.get("tokens")
        token_set = {
            str(token).casefold() for token in row_tokens
            if isinstance(row_tokens, list) and str(token).strip()
        }
        if not token_set:
            token_set = {token.casefold() for token in WORD_RE.findall(lowered)}
        overlap = len(query_tokens & token_set)
        score = float(overlap)
        if query_text and query_text in lowered:
            score += 3.0
        if query_text and query_text in source:
            score += 1.0
        if score <= 0:
            continue
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    cap = max(0, int(limit))
    if cap <= 0:
        return []
    return [dict(item[1]) for item in scored[:cap]]


def _memory_recall_text(
    store: dict[str, Any],
    key: str,
    query: str = "",
    limit: int = 8,
    prefix: str = "/",
) -> str:
    query_text = " ".join(str(query or "").strip().split())
    if query_text:
        notes = _memory_context_notes(store, key, query=query_text, limit=max(1, int(limit)))
    else:
        notes = _memory_recent_notes(store, key, limit=max(1, int(limit)))
    if not notes:
        return f"No memory notes yet. Save one with `{prefix}remember <note>`."
    title = "Matching memory notes:" if query_text else "Recent memory notes:"
    lines = [title]
    for idx, row in enumerate(notes, start=1):
        text = str(row.get("text") or "").strip()
        source = str(row.get("source") or "manual").strip()
        lines.append(f"{idx}. {text} ({source})")
    return "\n".join(lines)


def _memory_profile_text(store: dict[str, Any], key: str, prefix: str = "/") -> str:
    profile = _memory_profile(store, key)
    notes = _memory_recent_notes(store, key, limit=400)
    profile_history = _profile_history_rows(profile)
    profile_conflicts = _profile_conflict_rows(profile)
    open_conflicts = [
        row for row in profile_conflicts
        if str(row.get("status") or "").strip().lower() != "resolved"
    ]
    counts: dict[str, int] = {}
    for row in notes:
        text = str(row.get("text") or "").strip()
        for token in WORD_RE.findall(text):
            word = token.casefold()
            if word in STOP_WORDS or len(word) < 3:
                continue
            counts[word] = counts.get(word, 0) + 1
    top = [word for word, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8]]
    latest = [str(row.get("text") or "").strip() for row in notes[-3:]]
    profile_lines = _profile_lines(profile)
    habits = _memory_habits(profile)
    lines = [
        "Memory profile:",
        f"- Notes stored: {len(notes)}",
        f"- Habits tracked: {len(habits)}",
        f"- Profile updates logged: {len(profile_history)}",
        f"- Open profile conflicts: {len(open_conflicts)}",
        f"- Top themes: {', '.join(top) if top else '-'}",
        f"- Personality: {_profile_fields(profile).get('personality_mode') or _default_personality_mode()}",
    ]
    if profile_lines:
        lines.append("- Profile fields:")
        lines.extend(profile_lines)
    if latest:
        lines.append("- Latest notes:")
        for row in latest:
            lines.append(f"  - {row}")
    if not notes and (not profile_lines) and (not habits):
        lines.append(f"- Empty profile. Start with `{prefix}remember <note>`.")
        lines.append(f"- Set identity with `{prefix}profile-set goals <value>`.")
        lines.append(f"- Track routines with `{prefix}habit-add <habit name>`.")
    if open_conflicts:
        lines.append(f"- Review conflicts with `{prefix}profile-conflicts`.")
    return "\n".join(lines)


def _execute_memory_command(
    *,
    command: str,
    command_args: str,
    store: dict[str, Any],
    memory_key: str,
    chat_id: str,
    sender_user_id: str,
    sender_name: str,
    max_notes: int,
    intake_path: Path | None = None,
    terminal_queue_path: Path | None = None,
    prefix: str = "/",
) -> dict[str, Any]:
    cmd = str(command or "").strip().lower()
    args = str(command_args or "").strip()
    resolved_intake_path = intake_path if intake_path is not None else _default_intake_path()
    resolved_terminal_queue_path = (
        terminal_queue_path
        if terminal_queue_path is not None
        else _default_terminal_queue_path()
    )
    profile = _memory_profile(store, memory_key)
    if cmd in {"memory-help", "habit-help"}:
        return {"handled": True, "command": command, "ok": True, "summary": _memory_help_text(prefix=prefix), "changed": False}
    if cmd in {"memory", "recall", "memory-recall"}:
        return {
            "handled": True,
            "command": command,
            "ok": True,
            "summary": _memory_recall_text(store, memory_key, query=args, prefix=prefix),
            "changed": False,
        }
    if cmd in {"remember", "memory-remember"}:
        if not args:
            return {
                "handled": True,
                "command": command,
                "ok": False,
                "summary": f"Usage: `{prefix}remember <note>`",
                "changed": False,
            }
        changed = _memory_add_note(
            store=store,
            key=memory_key,
            chat_id=chat_id,
            sender_user_id=sender_user_id,
            sender_name=sender_name,
            text=args,
            source="manual",
            max_notes=max_notes,
        )
        if changed:
            profile["updated_at"] = _now_iso()
            store["updated_at"] = _now_iso()
        notes_count = len(_memory_recent_notes(store, memory_key, limit=max(1, int(max_notes))))
        if changed:
            summary = f"Saved memory note. Total notes: {notes_count}"
        else:
            summary = f"Memory already had that note. Total notes: {notes_count}"
        return {"handled": True, "command": command, "ok": True, "summary": summary, "changed": changed}
    if cmd in {"share", "intake", "brain-dump", "system-intake"}:
        if not args:
            return {
                "handled": True,
                "command": command,
                "ok": False,
                "summary": f"Usage: `{prefix}share <long note>`",
                "changed": False,
            }
        intake_ok, intake_result = _append_intake_entry(
            intake_path=resolved_intake_path,
            chat_id=chat_id,
            sender_user_id=sender_user_id,
            sender_name=sender_name,
            text=args,
            source="telegram-share",
        )
        changed = _memory_add_note(
            store=store,
            key=memory_key,
            chat_id=chat_id,
            sender_user_id=sender_user_id,
            sender_name=sender_name,
            text=args,
            source="share",
            max_notes=max_notes,
        )
        if changed:
            profile["updated_at"] = _now_iso()
            store["updated_at"] = _now_iso()
        if not intake_ok:
            return {
                "handled": True,
                "command": command,
                "ok": False,
                "summary": f"Failed to save intake note: {intake_result}",
                "changed": changed,
            }
        summary = (
            f"Shared with Ophtxn intake as `{intake_result}` "
            f"(chars={len(args)}). Saved to {resolved_intake_path}."
        )
        return {"handled": True, "command": command, "ok": True, "summary": summary, "changed": True}
    if cmd in {"terminal", "terminal-task", "task", "todo"}:
        if not args:
            return {
                "handled": True,
                "command": command,
                "ok": False,
                "summary": f"Usage: `{prefix}terminal <task>`",
                "changed": False,
            }
        task_ok, task_result = _append_terminal_task(
            queue_path=resolved_terminal_queue_path,
            chat_id=chat_id,
            sender_user_id=sender_user_id,
            sender_name=sender_name,
            text=args,
        )
        changed = _memory_add_note(
            store=store,
            key=memory_key,
            chat_id=chat_id,
            sender_user_id=sender_user_id,
            sender_name=sender_name,
            text=f"[terminal-task] {args}",
            source="terminal",
            max_notes=max_notes,
        )
        if changed:
            profile["updated_at"] = _now_iso()
            store["updated_at"] = _now_iso()
        if not task_ok:
            return {
                "handled": True,
                "command": command,
                "ok": False,
                "summary": f"Failed to queue terminal task: {task_result}",
                "changed": changed,
            }
        return {
            "handled": True,
            "command": command,
            "ok": True,
            "summary": f"Queued terminal task `{task_result}`. Queue: {resolved_terminal_queue_path}",
            "changed": True,
        }
    if cmd in {"terminal-list", "task-list", "todo-list"}:
        rows = _terminal_queue_recent(resolved_terminal_queue_path, limit=6)
        if not rows:
            return {
                "handled": True,
                "command": command,
                "ok": True,
                "summary": f"No queued terminal tasks yet. Use `{prefix}terminal <task>`.",
                "changed": False,
            }
        lines = [f"Recent terminal tasks ({len(rows)}):"]
        for idx, row in enumerate(rows, start=1):
            task_id = str(row.get("task_id") or "TERM-UNKNOWN").strip()
            status = str(row.get("status") or "PENDING").strip().upper()
            text = " ".join(str(row.get("text") or "").split())
            snippet = text if len(text) <= 120 else (text[:117].rstrip() + "...")
            lines.append(f"{idx}. {task_id} [{status}] {snippet}")
        lines.append(f"Queue path: {resolved_terminal_queue_path}")
        return {
            "handled": True,
            "command": command,
            "ok": True,
            "summary": "\n".join(lines),
            "changed": False,
        }
    if cmd in {"provider-status", "model-provider-status"}:
        return {
            "handled": True,
            "command": command,
            "ok": True,
            "summary": _provider_status_text(prefix=prefix),
            "changed": False,
        }
    if cmd in {"provider-set", "model-provider-set"}:
        if not args:
            return {
                "handled": True,
                "command": command,
                "ok": False,
                "summary": f"Usage: `{prefix}provider-set <anthropic|openai|xai|ollama>`",
                "changed": False,
            }
        ok, summary = _set_model_provider(args.split()[0])
        return {
            "handled": True,
            "command": command,
            "ok": bool(ok),
            "summary": summary,
            "changed": bool(ok),
        }
    if cmd in {"provider", "model-provider"}:
        if not args:
            return {
                "handled": True,
                "command": command,
                "ok": True,
                "summary": _provider_status_text(prefix=prefix),
                "changed": False,
            }
        tokens = [token.strip() for token in args.split() if token.strip()]
        if not tokens:
            return {
                "handled": True,
                "command": command,
                "ok": True,
                "summary": _provider_status_text(prefix=prefix),
                "changed": False,
            }
        action = tokens[0].lower()
        if action in {"status", "show", "list"}:
            return {
                "handled": True,
                "command": command,
                "ok": True,
                "summary": _provider_status_text(prefix=prefix),
                "changed": False,
            }
        if action in {"set", "use"} and len(tokens) >= 2:
            ok, summary = _set_model_provider(tokens[1])
            return {
                "handled": True,
                "command": command,
                "ok": bool(ok),
                "summary": summary,
                "changed": bool(ok),
            }
        ok, summary = _set_model_provider(tokens[0])
        return {
            "handled": True,
            "command": command,
            "ok": bool(ok),
            "summary": summary if ok else (summary + f" Use `{prefix}provider-status`."),
            "changed": bool(ok),
        }
    if cmd in {"profile", "memory-profile", "profile-get"}:
        return {
            "handled": True,
            "command": command,
            "ok": True,
            "summary": _memory_profile_text(store, memory_key, prefix=prefix),
            "changed": False,
        }
    if cmd in {"profile-history"}:
        return {
            "handled": True,
            "command": command,
            "ok": True,
            "summary": _profile_history_text(profile, field_alias=args, prefix=prefix),
            "changed": False,
        }
    if cmd in {"profile-conflicts"}:
        return {
            "handled": True,
            "command": command,
            "ok": True,
            "summary": _profile_conflicts_text(profile, prefix=prefix),
            "changed": False,
        }
    if cmd in {"profile-set"}:
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            return {
                "handled": True,
                "command": command,
                "ok": False,
                "summary": f"Usage: `{prefix}profile-set <field> <value>`",
                "changed": False,
            }
        changed, summary = _profile_set_field(profile, field_alias=parts[0], value=parts[1])
        if changed:
            profile["updated_at"] = _now_iso()
            store["updated_at"] = _now_iso()
        return {
            "handled": True,
            "command": command,
            "ok": bool(changed),
            "summary": summary,
            "changed": changed,
        }
    if cmd in {"personality"}:
        if not args:
            mode = str(_profile_fields(profile).get("personality_mode") or _default_personality_mode())
            prompt = PERSONALITY_MODES.get(mode, "-")
            return {
                "handled": True,
                "command": command,
                "ok": True,
                "summary": f"Personality mode: {mode}\nStyle: {prompt}",
                "changed": False,
            }
        changed, summary = _profile_set_field(profile, field_alias="personality", value=args)
        if changed:
            profile["updated_at"] = _now_iso()
            store["updated_at"] = _now_iso()
        return {"handled": True, "command": command, "ok": bool(changed), "summary": summary, "changed": changed}
    if cmd in {"personality-modes"}:
        rows = [f"- {name}: {desc}" for name, desc in sorted(PERSONALITY_MODES.items())]
        return {
            "handled": True,
            "command": command,
            "ok": True,
            "summary": "Available personality modes:\n" + "\n".join(rows),
            "changed": False,
        }
    if cmd in {"habit-add"}:
        changed, summary = _habit_add(profile, args)
        if changed:
            profile["updated_at"] = _now_iso()
            store["updated_at"] = _now_iso()
        return {"handled": True, "command": command, "ok": bool(changed), "summary": summary, "changed": changed}
    if cmd in {"habit-plan"}:
        changed, summary = _habit_update_plan(profile, args, prefix=prefix)
        if changed:
            profile["updated_at"] = _now_iso()
            store["updated_at"] = _now_iso()
        return {"handled": True, "command": command, "ok": bool(changed), "summary": summary, "changed": changed}
    if cmd in {"habit-done"}:
        changed, summary = _habit_mark_done(profile, args)
        if changed:
            profile["updated_at"] = _now_iso()
            store["updated_at"] = _now_iso()
        return {"handled": True, "command": command, "ok": bool(changed), "summary": summary, "changed": changed}
    if cmd in {"habit-nudge"}:
        return {
            "handled": True,
            "command": command,
            "ok": True,
            "summary": _habit_nudge_text(profile, prefix=prefix),
            "changed": False,
        }
    if cmd in {"habit-list"}:
        return {
            "handled": True,
            "command": command,
            "ok": True,
            "summary": _habit_list_text(profile, prefix=prefix),
            "changed": False,
        }
    if cmd in {"habit-drop"}:
        changed, summary = _habit_drop(profile, args)
        if changed:
            profile["updated_at"] = _now_iso()
            store["updated_at"] = _now_iso()
        return {"handled": True, "command": command, "ok": bool(changed), "summary": summary, "changed": changed}
    if cmd in {"forget-last", "memory-forget-last"}:
        notes = profile.get("notes")
        if not isinstance(notes, list) or not notes:
            return {"handled": True, "command": command, "ok": False, "summary": "No memory notes to remove.", "changed": False}
        removed = str((notes.pop() or {}).get("text") or "").strip()
        profile["updated_at"] = _now_iso()
        store["updated_at"] = _now_iso()
        snippet = removed if len(removed) <= 120 else (removed[:117].rstrip() + "...")
        return {"handled": True, "command": command, "ok": True, "summary": f"Removed last memory note: {snippet}", "changed": True}
    return {"handled": False, "command": command, "ok": False, "summary": "unknown memory command", "changed": False}


def _chat_history_entry(role: str, text: str, sender: str = "") -> dict[str, Any]:
    return {
        "role": str(role or "user").strip().lower(),
        "text": str(text or "").strip(),
        "sender": str(sender or "").strip(),
        "timestamp": _now_iso(),
    }


def _trim_chat_history(rows: list[dict[str, Any]], max_messages: int) -> list[dict[str, Any]]:
    if max_messages <= 0:
        return []
    return rows[-max_messages:]


def _compose_chat_prompt(
    *,
    user_text: str,
    sender: str,
    chat_id: str,
    history_rows: list[dict[str, Any]],
    memory_rows: list[dict[str, Any]],
    profile_lines: list[str],
    habit_lines: list[str],
    max_history_messages: int,
    brain_rows: list[dict[str, Any]] | None = None,
) -> str:
    lines: list[str] = [
        f"Chat ID: {chat_id or '-'}",
        f"Sender: {sender or 'telegram-user'}",
        "Recent conversation:",
    ]
    for row in _trim_chat_history(history_rows, max_messages=max_history_messages):
        role = str(row.get("role") or "user").strip().lower()
        text = str(row.get("text") or "").strip().replace("\n", " ")
        if not text:
            continue
        if len(text) > 280:
            text = text[:277].rstrip() + "..."
        label = "Assistant" if role == "assistant" else "User"
        lines.append(f"- {label}: {text}")
    memory_notes = [str(row.get("text") or "").strip() for row in memory_rows if isinstance(row, dict)]
    brain_notes = [_brain_note_text(row) for row in (brain_rows or []) if isinstance(row, dict)]
    if profile_lines:
        lines.append("")
        lines.append("User profile:")
        lines.extend(profile_lines)
    if habit_lines:
        lines.append("")
        lines.append("Habit tracker:")
        lines.extend(habit_lines)
    if memory_notes:
        lines.append("")
        lines.append("Long-term memory notes:")
        for note in memory_notes:
            if not note:
                continue
            row = note if len(note) <= 220 else (note[:217].rstrip() + "...")
            lines.append(f"- {row}")
    if brain_notes:
        lines.append("")
        lines.append("System brain context:")
        for note in brain_notes:
            if not note:
                continue
            row = note if len(note) <= 240 else (note[:237].rstrip() + "...")
            lines.append(f"- {row}")
    lines.extend(
        [
            "",
            "Latest user message:",
            str(user_text or "").strip(),
            "",
            "Reply directly, concise, and action-oriented.",
        ]
    )
    return "\n".join(lines).strip()


def _trim_reply_text(text: str, max_chars: int) -> str:
    payload = str(text or "").strip()
    if not payload:
        return ""
    cap = max(120, int(max_chars))
    if len(payload) <= cap:
        return payload
    return payload[: cap - 3].rstrip() + "..."


def _chat_system_prompt(
    *,
    personality_mode: str = "",
    profile_lines: list[str] | None = None,
) -> str:
    raw = str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_CHAT_SYSTEM_PROMPT", "")).strip()
    base = raw or (
        "You are the Telegram-facing assistant for Permanence OS. "
        "Be concise, practical, and truthful. "
        "Do not claim actions were completed unless explicitly confirmed in context. "
        "If user asks for system execution, suggest slash commands when appropriate."
    )
    mode = str(personality_mode or "").strip().lower()
    if mode in {"default", "balanced"}:
        mode = "adaptive"
    if mode not in PERSONALITY_MODES:
        mode = _default_personality_mode()
    style_line = PERSONALITY_MODES.get(mode, PERSONALITY_MODES["adaptive"])
    extras = [
        f"Personality mode: {mode}.",
        f"Style guidance: {style_line}",
        "Use profile and habit context when relevant, but do not fabricate details.",
    ]
    if profile_lines:
        extras.append("Keep responses consistent with the user's stated goals and values.")
    return base + " " + " ".join(extras)


def _chat_fallback_reply_text(user_text: str, command_prefix: str = "/") -> str:
    snippet = str(user_text or "").strip().replace("\n", " ")
    if len(snippet) > 200:
        snippet = snippet[:197].rstrip() + "..."
    return (
        "I got your message and logged it to your system intake.\n"
        f"Message: \"{snippet or '...'}\"\n\n"
        "I can still run updates and checks right now:\n"
        f"- {command_prefix}comms-status\n"
        f"- {command_prefix}comms-doctor\n"
        f"- {command_prefix}comms-run\n"
        f"- {command_prefix}memory-help"
    )


def _generate_chat_reply(
    *,
    prompt: str,
    task_type: str,
    model_router: Any,
    system_prompt: str = "",
) -> tuple[str, str]:
    if not model_router:
        return "", "model router unavailable"
    try:
        model = model_router.get_model(task_type)
    except Exception as exc:  # noqa: BLE001
        return "", f"chat model unavailable: {exc.__class__.__name__}"
    if not model:
        return "", "chat model unavailable"
    try:
        response = model.generate(prompt=prompt, system=(system_prompt or _chat_system_prompt()))
    except Exception as exc:  # noqa: BLE001
        detail = str(exc).strip().replace("\n", " ")
        if len(detail) > 180:
            detail = detail[:177].rstrip() + "..."
        if not detail:
            detail = exc.__class__.__name__
        return "", f"chat generation failed: {detail}"
    text = str(getattr(response, "text", "")).strip()
    if not text:
        return "", "empty chat response"
    return text, ""


def _curl_json(url: str, params: dict[str, Any] | None = None, timeout: int = 20) -> dict[str, Any]:
    cmd = ["curl", "-sS", "--max-time", str(max(1, timeout)), "--get", url]
    for key, value in (params or {}).items():
        cmd.extend(["--data-urlencode", f"{key}={value}"])
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"curl exited {proc.returncode}")
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise RuntimeError(f"Invalid JSON response from Telegram API: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Telegram API payload shape")
    return payload


def _curl_download(url: str, dest: Path, timeout: int = 30) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "curl",
        "-fsSL",
        "--max-time",
        str(max(1, timeout)),
        url,
        "-o",
        str(dest),
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"curl exited {proc.returncode}")


def _api(token: str, method: str, params: dict[str, Any] | None = None, timeout: int = 20) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    return _curl_json(url=url, params=params, timeout=timeout)


def _file_url(token: str, file_path: str) -> str:
    return f"https://api.telegram.org/file/bot{token}/{file_path}"


def _extract_update_message(update: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("message", "channel_post", "edited_message", "edited_channel_post"):
        obj = update.get(key)
        if isinstance(obj, dict):
            return obj
    return None


def _extract_sender(msg: dict[str, Any]) -> str:
    from_user = msg.get("from")
    if isinstance(from_user, dict):
        username = str(from_user.get("username") or "").strip()
        if username:
            return username
        first = str(from_user.get("first_name") or "").strip()
        last = str(from_user.get("last_name") or "").strip()
        full = " ".join(item for item in (first, last) if item).strip()
        if full:
            return full
    chat = msg.get("chat")
    if isinstance(chat, dict):
        title = str(chat.get("title") or chat.get("username") or "").strip()
        if title:
            return title
    return "telegram"


def _extract_text(msg: dict[str, Any]) -> str:
    text = str(msg.get("text") or msg.get("caption") or "").strip()
    if text:
        return text
    media_tokens: list[str] = []
    for key in ("photo", "video", "audio", "voice", "document"):
        if msg.get(key):
            media_tokens.append(key)
    if media_tokens:
        return f"Telegram media message ({', '.join(media_tokens)})."
    return "Telegram event."


def _message_media_types(msg: dict[str, Any]) -> list[str]:
    types: list[str] = []
    for key in ("photo", "video", "audio", "voice", "document"):
        value = msg.get(key)
        if value:
            types.append(key)
    document = msg.get("document") if isinstance(msg.get("document"), dict) else {}
    mime_type = str(document.get("mime_type") or "").strip().lower()
    if mime_type.startswith("audio/") and "audio" not in types:
        types.append("audio")
    return sorted(set(types))


def _is_voice_note_message(msg: dict[str, Any]) -> bool:
    if isinstance(msg.get("voice"), dict):
        return True
    if isinstance(msg.get("audio"), dict):
        return True
    document = msg.get("document") if isinstance(msg.get("document"), dict) else {}
    mime_type = str(document.get("mime_type") or "").strip().lower()
    if mime_type.startswith("audio/"):
        return True
    file_name = str(document.get("file_name") or "").strip().lower()
    return file_name.endswith((".m4a", ".mp3", ".wav", ".ogg", ".flac"))


def _extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for candidate in URL_RE.findall(text or ""):
        cleaned = candidate.rstrip(".,);]")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
    return urls


def _media_specs(msg: dict[str, Any]) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    photo = msg.get("photo")
    if isinstance(photo, list) and photo:
        rows = [row for row in photo if isinstance(row, dict) and row.get("file_id")]
        if rows:
            rows.sort(key=lambda row: _safe_int(row.get("file_size"), 0), reverse=True)
            top = rows[0]
            specs.append({"file_id": str(top.get("file_id")), "name": f"telegram_photo_{top.get('file_unique_id', 'x')}.jpg"})

    for key, default_ext in (("video", ".mp4"), ("audio", ".mp3"), ("voice", ".ogg"), ("document", "")):
        payload = msg.get(key)
        if not isinstance(payload, dict):
            continue
        file_id = str(payload.get("file_id") or "").strip()
        if not file_id:
            continue
        name = str(payload.get("file_name") or "").strip()
        if not name:
            unique = str(payload.get("file_unique_id") or file_id)[:16]
            name = f"telegram_{key}_{unique}{default_ext}"
        specs.append({"file_id": file_id, "name": name})
    return specs


def _download_media(token: str, specs: list[dict[str, str]], dest_dir: Path, timeout: int = 30) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    warnings: list[str] = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        file_id = str(spec.get("file_id") or "").strip()
        if not file_id:
            continue
        try:
            meta = _api(token=token, method="getFile", params={"file_id": file_id}, timeout=timeout)
            if not meta.get("ok"):
                warnings.append(f"getFile failed for {file_id}")
                continue
            result = meta.get("result") or {}
            file_path = str(result.get("file_path") or "").strip()
            if not file_path:
                warnings.append(f"empty file_path for {file_id}")
                continue
            suggested = Path(str(spec.get("name") or Path(file_path).name)).name
            out = dest_dir / suggested.replace(" ", "_")
            if out.exists():
                out = dest_dir / f"{out.stem}_{int(_now().timestamp())}{out.suffix}"
            _curl_download(_file_url(token=token, file_path=file_path), out, timeout=timeout)
            paths.append(str(out))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"download failed for {file_id}: {exc}")
    return paths, warnings


def _build_event(
    update: dict[str, Any],
    msg: dict[str, Any],
    source: str,
    channel: str,
    media_paths: list[str],
    *,
    priority: str | None = None,
    media_types: list[str] | None = None,
    voice_note: bool = False,
) -> dict[str, Any]:
    timestamp = _safe_int(msg.get("date"), 0)
    if timestamp > 0:
        event_time = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    else:
        event_time = _now_iso()
    chat = msg.get("chat") if isinstance(msg.get("chat"), dict) else {}
    return {
        "source": source,
        "channel": channel,
        "sender": _extract_sender(msg),
        "message": _extract_text(msg),
        "urls": _extract_urls(_extract_text(msg)),
        "timestamp": event_time,
        "media_paths": media_paths,
        "media_types": media_types or [],
        "voice_note": bool(voice_note),
        "priority": str(priority or "normal").strip().lower(),
        "telegram_update_id": _safe_int(update.get("update_id"), 0),
        "telegram_message_id": _safe_int(msg.get("message_id"), 0),
        "telegram_chat_id": _safe_int(chat.get("id"), 0),
    }


def _enqueue_transcription_items(
    *,
    queue_path: Path,
    media_paths: list[str],
    source: str,
    channel: str,
    sender: str,
    message: str,
    event_time: str,
) -> int:
    rows = _load_json_array(queue_path)
    by_source: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_path = str(row.get("source_path") or "").strip()
        if source_path:
            by_source[source_path] = row

    queued = 0
    for source_path in media_paths:
        path = str(source_path or "").strip()
        if not path:
            continue
        ext = Path(path).suffix.lower()
        if ext not in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aiff", ".mp4", ".mov", ".mkv", ".webm"}:
            continue
        existing = by_source.get(path)
        if existing:
            existing["updated_at"] = _now_iso()
            continue
        queued += 1
        by_source[path] = {
            "queue_id": "TQ-" + hashlib.sha1(path.encode("utf-8")).hexdigest()[:12],
            "source_path": path,
            "kind": "audio" if ext in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aiff"} else "video",
            "status": "pending_manual_transcribe",
            "notes": "Queued from telegram voice-note ingest.",
            "source": source,
            "channel": channel,
            "sender": sender,
            "message": message,
            "event_time": event_time,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }

    updated_rows = sorted(by_source.values(), key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    _save_json_array(queue_path, updated_rows)
    return queued


def _extract_command(text: str, prefix: str = "/") -> str:
    payload = str(text or "").strip()
    if not payload:
        return ""
    token = payload.split()[0].strip()
    if not token.startswith(prefix):
        return ""
    command = token[len(prefix) :].strip().lower()
    if "@" in command:
        command = command.split("@", 1)[0].strip()
    return command.replace("_", "-")


def _extract_command_args(text: str, prefix: str = "/") -> str:
    payload = str(text or "").strip()
    if not payload:
        return ""
    token = payload.split()[0].strip()
    if not token.startswith(prefix):
        return ""
    parts = payload.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def _parse_improve_decision_args(command_args: str) -> tuple[str, str]:
    proposal_id = ""
    decision_code = ""
    tokens = [token.strip() for token in str(command_args or "").split() if token.strip()]
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"id", "proposal", "proposal-id"} and (not proposal_id):
                proposal_id = value.upper()
                continue
            if key in {"code", "pin", "decision-code"} and (not decision_code):
                decision_code = value
                continue
        upper = token.upper()
        if (not proposal_id) and upper.startswith("IMP-"):
            proposal_id = upper
            continue
        if not decision_code:
            decision_code = token
    return proposal_id, decision_code


def _parse_x_watch_args(command_args: str) -> tuple[str, bool]:
    handle = ""
    include_replies = False
    tokens = [token.strip() for token in str(command_args or "").split() if token.strip()]
    for token in tokens:
        lowered = token.lower()
        if lowered in {"--include-replies", "replies=1", "include-replies=1", "include_replies=1"}:
            include_replies = True
            continue
        if "=" in token:
            key, value = token.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"handle", "user", "username", "account"} and (not handle):
                handle = value
                continue
        if not handle:
            handle = token
    return handle, include_replies


def _command_argv(command: str, command_args: str = "") -> list[str]:
    cmd = str(command or "").strip().lower()
    if cmd in {"help", "start", "comms-help", "whoami", "comms-whoami", "mode", "comms-mode"}:
        return []
    if cmd in {"comms-status", "status"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-status"]
    if cmd in {"comms-doctor", "doctor"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-doctor", "--allow-warnings"]
    if cmd in {"comms-doctor-fix", "doctor-fix"}:
        return [
            sys.executable,
            str(BASE_DIR / "cli.py"),
            "comms-doctor",
            "--allow-warnings",
            "--auto-repair",
        ]
    if cmd in {"comms-digest", "digest"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-digest"]
    if cmd in {"comms-digest-send", "digest-send"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-digest", "--send"]
    if cmd in {"comms-escalations", "comms-escalation-digest", "escalations"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-escalation-digest", "--hours", "24"]
    if cmd in {"comms-escalations-send", "comms-escalation-digest-send", "escalations-send"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-escalation-digest", "--hours", "24", "--send"]
    if cmd in {"comms-escalation-status", "escalation-status"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-automation", "--action", "escalation-status"]
    if cmd in {"comms-escalation-enable", "escalation-enable"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-automation", "--action", "escalation-enable"]
    if cmd in {"comms-escalation-disable", "escalation-disable"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-automation", "--action", "escalation-disable"]
    if cmd in {"comms-run", "run", "comms-loop"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-automation", "--action", "run-now"]
    if cmd in {"comms-auto-status", "comms-automation-status", "automation-status"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "comms-automation", "--action", "status"]
    if cmd in {"learn-status", "governed-learning-status"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "governed-learning", "--action", "status"]
    if cmd in {"learn-run", "governed-learning-run"}:
        return [
            sys.executable,
            str(BASE_DIR / "cli.py"),
            "governed-learning",
            "--action",
            "run",
            "--approved-by",
            "telegram",
            "--approval-note",
            "telegram-command",
        ]
    if cmd in {"improve-status", "self-improvement-status"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "self-improvement", "--action", "status"]
    if cmd in {"improve-pitch", "self-improvement-pitch"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "self-improvement", "--action", "pitch"]
    if cmd in {"improve-list", "self-improvement-list"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "self-improvement", "--action", "list"]
    if cmd in {"improve-approve", "self-improvement-approve"}:
        proposal_id, decision_code = _parse_improve_decision_args(command_args)
        argv = [
            sys.executable,
            str(BASE_DIR / "cli.py"),
            "self-improvement",
            "--action",
            "decide",
            "--decision",
            "approve",
            "--decided-by",
            "telegram",
        ]
        if proposal_id:
            argv.extend(["--proposal-id", proposal_id])
        if decision_code:
            argv.extend(["--decision-code", decision_code])
        return argv
    if cmd in {"improve-reject", "self-improvement-reject"}:
        proposal_id, decision_code = _parse_improve_decision_args(command_args)
        argv = [
            sys.executable,
            str(BASE_DIR / "cli.py"),
            "self-improvement",
            "--action",
            "decide",
            "--decision",
            "reject",
            "--decided-by",
            "telegram",
        ]
        if proposal_id:
            argv.extend(["--proposal-id", proposal_id])
        if decision_code:
            argv.extend(["--decision-code", decision_code])
        return argv
    if cmd in {"improve-defer", "self-improvement-defer"}:
        proposal_id, decision_code = _parse_improve_decision_args(command_args)
        argv = [
            sys.executable,
            str(BASE_DIR / "cli.py"),
            "self-improvement",
            "--action",
            "decide",
            "--decision",
            "defer",
            "--decided-by",
            "telegram",
        ]
        if proposal_id:
            argv.extend(["--proposal-id", proposal_id])
        if decision_code:
            argv.extend(["--decision-code", decision_code])
        return argv
    if cmd in {"brain-status", "ophtxn-brain-status"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "ophtxn-brain", "--action", "status"]
    if cmd in {"brain-sync", "ophtxn-brain-sync"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "ophtxn-brain", "--action", "sync"]
    if cmd in {"brain-recall", "ophtxn-brain-recall"}:
        argv = [sys.executable, str(BASE_DIR / "cli.py"), "ophtxn-brain", "--action", "recall"]
        query = " ".join(str(command_args or "").split())
        if query:
            argv.extend(["--query", query])
        return argv
    if cmd in {"x-watch", "x-account-watch-add"}:
        handle, include_replies = _parse_x_watch_args(command_args)
        argv = [sys.executable, str(BASE_DIR / "cli.py"), "x-account-watch", "--action", "add"]
        if handle:
            argv.extend(["--handle", handle])
        if include_replies:
            argv.append("--include-replies")
        return argv
    if cmd in {"x-unwatch", "x-account-watch-remove"}:
        handle, _include_replies = _parse_x_watch_args(command_args)
        argv = [sys.executable, str(BASE_DIR / "cli.py"), "x-account-watch", "--action", "remove"]
        if handle:
            argv.extend(["--handle", handle])
        return argv
    if cmd in {"x-watch-list", "x-account-watch-list"}:
        return [sys.executable, str(BASE_DIR / "cli.py"), "x-account-watch", "--action", "list"]
    if cmd in {"platform-watch", "platform-change-watch"}:
        argv = [sys.executable, str(BASE_DIR / "cli.py"), "platform-change-watch"]
        tokens = {
            token.strip().lower()
            for token in str(command_args or "").replace(",", " ").split()
            if token.strip()
        }
        if "strict" in tokens or "--strict" in tokens:
            argv.append("--strict")
        if "no-queue" in tokens or "--no-queue" in tokens:
            argv.append("--no-queue")
        return argv
    return [""]


def _compact_output(text: str, max_lines: int = 8, max_chars: int = 800) -> str:
    rows = [row for row in str(text or "").splitlines() if row.strip()]
    if not rows:
        return "-"
    clipped = rows[: max(1, int(max_lines))]
    out = "\n".join(clipped).strip()
    if len(out) > max(80, int(max_chars)):
        out = out[: max(80, int(max_chars)) - 3].rstrip() + "..."
    return out


def _command_help_text(prefix: str = "/") -> str:
    commands = [
        f"{prefix}comms-mode",
        f"{prefix}comms-whoami",
        f"{prefix}memory-help",
        f"{prefix}memory",
        f"{prefix}remember <note>",
        f"{prefix}share <long note>",
        f"{prefix}recall",
        f"{prefix}profile",
        f"{prefix}profile-set <field> <value>",
        f"{prefix}profile-get",
        f"{prefix}profile-history [field]",
        f"{prefix}profile-conflicts",
        f"{prefix}personality [mode]",
        f"{prefix}personality-modes",
        f"{prefix}habit-add <name> | cue: ... | plan: ...",
        f"{prefix}habit-plan <name> | cue: ... | plan: ...",
        f"{prefix}habit-done <name>",
        f"{prefix}habit-nudge",
        f"{prefix}habit-list",
        f"{prefix}habit-drop <name>",
        f"{prefix}forget-last",
        f"{prefix}terminal <task>",
        f"{prefix}terminal-list",
        f"{prefix}provider-status",
        f"{prefix}provider-set <anthropic|openai|xai|ollama>",
        f"{prefix}comms-status",
        f"{prefix}comms-doctor",
        f"{prefix}comms-doctor-fix",
        f"{prefix}comms-digest",
        f"{prefix}comms-digest-send",
        f"{prefix}comms-escalations",
        f"{prefix}comms-escalations-send",
        f"{prefix}comms-escalation-status",
        f"{prefix}comms-escalation-enable",
        f"{prefix}comms-escalation-disable",
        f"{prefix}comms-run",
        f"{prefix}comms-auto-status",
        f"{prefix}learn-status",
        f"{prefix}learn-run",
        f"{prefix}improve-status",
        f"{prefix}improve-pitch",
        f"{prefix}improve-list",
        f"{prefix}improve-approve [proposal-id] [decision-code]",
        f"{prefix}improve-reject [proposal-id] [decision-code]",
        f"{prefix}improve-defer [proposal-id] [decision-code]",
        f"{prefix}brain-status",
        f"{prefix}brain-sync",
        f"{prefix}brain-recall <query>",
        f"{prefix}x-watch <handle|url>",
        f"{prefix}x-unwatch <handle|url>",
        f"{prefix}x-watch-list",
        f"{prefix}platform-watch [strict] [no-queue]",
    ]
    return "Available commands:\n" + "\n".join(f"- {row}" for row in commands)


def _command_mode_text(prefix: str = "/") -> str:
    return (
        "Telegram routing mode:\n"
        f"- Commands starting with `{prefix}` run local terminal workflows.\n"
        "- Plain text/voice/media messages are ingested to the agent intake pipeline.\n"
        f"- Personal memory commands: `{prefix}remember`, `{prefix}recall`, `{prefix}profile`, `{prefix}profile-history`.\n"
        f"- Long-form context share: `{prefix}share <long note>`.\n"
        f"- Habit + personality controls: `{prefix}habit-list`, `{prefix}habit-nudge`, `{prefix}personality`.\n"
        f"- Model provider controls: `{prefix}provider-status`, `{prefix}provider-set` (supports anthropic/openai/xai/ollama).\n"
        f"- Terminal queue controls: `{prefix}terminal <task>`, `{prefix}terminal-list`.\n"
        f"- Governed learning controls: `{prefix}learn-status`, `{prefix}learn-run`.\n"
        f"- Improvement pitch controls: `{prefix}improve-pitch`, `{prefix}improve-list`, `{prefix}improve-approve`.\n"
        f"- Brain controls: `{prefix}brain-sync`, `{prefix}brain-recall <query>`.\n"
        f"- Read-only X watch controls: `{prefix}x-watch`, `{prefix}x-unwatch`, `{prefix}x-watch-list`.\n"
        f"- Platform drift watch: `{prefix}platform-watch` (add `strict` for fail-on-critical mode).\n"
        f"- Use `{prefix}comms-help` for command list."
    )


def _run_local_command(argv: list[str], timeout: int) -> dict[str, Any]:
    proc = subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        cwd=str(BASE_DIR),
        timeout=max(3, int(timeout)),
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": int(proc.returncode),
        "stdout": _compact_output(proc.stdout or ""),
        "stderr": _compact_output(proc.stderr or ""),
    }


def _execute_control_command(command: str, timeout: int, prefix: str = "/", command_args: str = "") -> dict[str, Any]:
    cmd = str(command or "").strip().lower()
    if cmd in {"mode", "comms-mode"}:
        return {"handled": True, "command": command, "ok": True, "summary": _command_mode_text(prefix=prefix)}
    argv = _command_argv(command, command_args=command_args)
    if argv == [""]:
        return {"handled": False, "command": command, "ok": False, "summary": "unknown command"}
    if not argv:
        if cmd in {"whoami", "comms-whoami"}:
            return {"handled": True, "command": command, "ok": True, "summary": "use this command in chat to see user_id"}
        return {"handled": True, "command": command, "ok": True, "summary": _command_help_text(prefix=prefix)}
    try:
        result = _run_local_command(argv, timeout=max(3, int(timeout)))
    except subprocess.TimeoutExpired:
        return {
            "handled": True,
            "command": command,
            "ok": False,
            "summary": f"command timed out after {max(3, int(timeout))}s",
        }
    output = result["stdout"] if result["ok"] else result["stderr"]
    summary = f"rc={result['returncode']}\n{output}"
    return {
        "handled": True,
        "command": command,
        "ok": bool(result.get("ok")),
        "summary": summary,
    }


def _write_report(
    *,
    action: str,
    target_chat_ids: list[str],
    updates_count: int,
    ingested_count: int,
    voice_notes_ingested: int,
    voice_transcribe_queued: int,
    ignored_count: int,
    commands_executed: int,
    commands_failed: int,
    commands_unauthorized: int,
    command_allowlist_user_ids: list[str],
    command_allowlist_chat_ids: list[str],
    chat_agent_enabled: bool,
    chat_replies_sent: int,
    chat_replies_failed: int,
    chat_replies_fallback_sent: int,
    command_runs: list[dict[str, Any]],
    warnings: list[str],
    state_path: Path,
    next_offset: int,
) -> tuple[Path, Path]:
    output_dir = _output_dir()
    tool_dir = _tool_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    tool_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = output_dir / f"telegram_control_{stamp}.md"
    latest_md = output_dir / "telegram_control_latest.md"
    json_path = tool_dir / f"telegram_control_{stamp}.json"

    lines = [
        "# Telegram Control",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        "",
        "## Summary",
        f"- Telegram updates fetched: {updates_count}",
        f"- Events ingested: {ingested_count}",
        f"- Voice notes ingested: {voice_notes_ingested}",
        f"- Voice transcribe queued: {voice_transcribe_queued}",
        f"- Updates ignored: {ignored_count}",
        f"- Commands executed: {commands_executed}",
        f"- Commands failed: {commands_failed}",
        f"- Commands unauthorized: {commands_unauthorized}",
        f"- Chat agent enabled: {chat_agent_enabled}",
        f"- Chat replies sent: {chat_replies_sent}",
        f"- Chat replies failed: {chat_replies_failed}",
        f"- Chat fallback replies sent: {chat_replies_fallback_sent}",
        f"- Target chat ids: {', '.join(target_chat_ids) if target_chat_ids else '(all chats)'}",
        (
            f"- Command allowlist user ids: {', '.join(command_allowlist_user_ids)}"
            if command_allowlist_user_ids
            else "- Command allowlist user ids: -"
        ),
        (
            f"- Command allowlist chat ids: {', '.join(command_allowlist_chat_ids)}"
            if command_allowlist_chat_ids
            else "- Command allowlist chat ids: -"
        ),
        f"- Warnings: {len(warnings)}",
        f"- State path: {state_path}",
        f"- Next offset: {next_offset}",
        "",
    ]
    if command_runs:
        lines.append("## Command Runs")
        for row in command_runs[:20]:
            cmd = str(row.get("command") or "unknown")
            ok = bool(row.get("ok"))
            summary = str(row.get("summary") or "-").replace("\n", " | ")
            lines.append(f"- {cmd}: {'ok' if ok else 'failed'} | {summary}")
        lines.append("")
    if warnings:
        lines.append("## Warnings")
        for item in warnings[:50]:
            lines.append(f"- {item}")
        lines.append("")
    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "target_chat_ids": target_chat_ids,
        "updates_count": updates_count,
        "ingested_count": ingested_count,
        "voice_notes_ingested": voice_notes_ingested,
        "voice_transcribe_queued": voice_transcribe_queued,
        "ignored_count": ignored_count,
        "commands_executed": commands_executed,
        "commands_failed": commands_failed,
        "commands_unauthorized": commands_unauthorized,
        "command_allowlist_user_ids": command_allowlist_user_ids,
        "command_allowlist_chat_ids": command_allowlist_chat_ids,
        "chat_agent_enabled": chat_agent_enabled,
        "chat_replies_sent": chat_replies_sent,
        "chat_replies_failed": chat_replies_failed,
        "chat_replies_fallback_sent": chat_replies_fallback_sent,
        "command_runs": command_runs,
        "warnings": warnings,
        "state_path": str(state_path),
        "next_offset": next_offset,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def _send_ack(token: str, chat_id: str, text: str, timeout: int = 20) -> None:
    _api(token=token, method="sendMessage", params={"chat_id": chat_id, "text": text}, timeout=timeout)
    _mirror_ack_to_imessage(text=text, timeout=timeout)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Poll Telegram bot updates into glasses/research/reception pipelines.")
    parser.add_argument("--action", choices=["status", "poll"], default="status")
    parser.add_argument(
        "--chat-id",
        help="Target Telegram chat id or comma-separated ids (also reads PERMANENCE_TELEGRAM_CHAT_ID(S))",
    )
    parser.add_argument("--source", default="telegram-control", help="Source label for ingested events")
    parser.add_argument("--channel", default="telegram", help="Channel label for ingested events")
    parser.add_argument("--limit", type=int, default=50, help="Max updates to fetch per poll")
    parser.add_argument("--state-path", help="Offset state path")
    parser.add_argument("--download-dir", help="Media download directory")
    parser.add_argument("--timeout", type=int, default=20, help="Network timeout seconds")
    parser.add_argument("--skip-media", action="store_true", help="Skip media download from Telegram")
    parser.add_argument(
        "--include-bot-messages",
        action="store_true",
        help="Include messages where Telegram marks sender as a bot",
    )
    parser.add_argument("--no-commit-offset", action="store_true", help="Do not persist next update offset")
    parser.add_argument("--ack", action="store_true", help="Send summary acknowledgment message to chat")
    parser.add_argument("--enable-commands", action="store_true", help="Execute allowed slash commands from chat")
    parser.add_argument(
        "--command-prefix",
        default=str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_COMMAND_PREFIX", "/")).strip() or "/",
        help="Command prefix token",
    )
    parser.add_argument(
        "--command-timeout",
        type=int,
        default=_int_env("PERMANENCE_TELEGRAM_CONTROL_COMMAND_TIMEOUT", 90),
        help="Max seconds per command execution",
    )
    parser.add_argument(
        "--max-commands",
        type=int,
        default=_int_env("PERMANENCE_TELEGRAM_CONTROL_MAX_COMMANDS", 3),
        help="Max commands to execute per poll",
    )
    parser.add_argument(
        "--command-allow-user-id",
        action="append",
        default=[],
        help="Allowed Telegram user id for command execution (repeatable)",
    )
    parser.add_argument(
        "--command-allow-chat-id",
        action="append",
        default=[],
        help="Allowed Telegram chat id for command execution (repeatable)",
    )
    parser.add_argument(
        "--require-command-allowlist",
        action="store_true",
        default=_is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_REQUIRE_COMMAND_ALLOWLIST", "0")),
        help="Require configured command allowlist before executing commands",
    )
    parser.add_argument("--no-command-ack", action="store_true", help="Do not send per-command ack responses")
    parser.add_argument("--chat-agent", action="store_true", help="Reply to non-command messages using model assistant")
    parser.add_argument("--no-chat-agent", action="store_true", help="Disable chat-agent replies for this run")
    parser.add_argument(
        "--chat-task-type",
        default=str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_CHAT_TASK_TYPE", "execution")).strip() or "execution",
        help="Model routing task type for chat replies",
    )
    parser.add_argument(
        "--max-chat-replies",
        type=int,
        default=_int_env("PERMANENCE_TELEGRAM_CONTROL_CHAT_MAX_REPLIES", 3),
        help="Max non-command chat replies per poll",
    )
    parser.add_argument(
        "--chat-max-history",
        type=int,
        default=_int_env("PERMANENCE_TELEGRAM_CONTROL_CHAT_MAX_HISTORY", 12),
        help="Max history messages retained per chat",
    )
    parser.add_argument(
        "--chat-reply-max-chars",
        type=int,
        default=_int_env("PERMANENCE_TELEGRAM_CONTROL_CHAT_REPLY_MAX_CHARS", 1400),
        help="Max characters per chat reply",
    )
    parser.add_argument("--chat-history-path", help="Chat history JSON path")
    parser.add_argument(
        "--chat-memory-max-notes",
        type=int,
        default=_int_env("PERMANENCE_TELEGRAM_CONTROL_CHAT_MEMORY_MAX_NOTES", 8),
        help="Max personal-memory notes included in chat prompt",
    )
    parser.add_argument(
        "--chat-brain-max-notes",
        type=int,
        default=_int_env("PERMANENCE_TELEGRAM_CONTROL_CHAT_BRAIN_MAX_NOTES", 4),
        help="Max system-brain notes included in chat prompt",
    )
    parser.add_argument(
        "--chat-auto-memory",
        action="store_true",
        help="Store non-command user chat messages into personal memory",
    )
    parser.add_argument(
        "--no-chat-auto-memory",
        action="store_true",
        help="Disable automatic personal-memory capture for non-command chat messages",
    )
    parser.add_argument("--memory-path", help="Personal memory JSON path")
    parser.add_argument("--intake-path", help="Long-form shared intake JSONL path")
    parser.add_argument("--terminal-queue-path", help="Terminal task queue JSONL path")
    parser.add_argument("--brain-vault-path", help="Ophtxn brain vault JSON path")
    parser.add_argument(
        "--memory-max-notes",
        type=int,
        default=_int_env("PERMANENCE_TELEGRAM_CONTROL_MEMORY_MAX_NOTES", 500),
        help="Max memory notes retained per user profile",
    )
    parser.add_argument(
        "--voice-priority",
        choices=["urgent", "high", "normal", "low"],
        default=str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_VOICE_PRIORITY", "high")).strip().lower() or "high",
        help="Priority assigned to voice-note events",
    )
    parser.add_argument(
        "--voice-channel",
        default=str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_VOICE_CHANNEL", "telegram-voice")).strip() or "telegram-voice",
        help="Channel label used for voice-note events",
    )
    parser.add_argument(
        "--voice-source",
        default=str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_VOICE_SOURCE", "")).strip(),
        help="Optional source override for voice-note events",
    )
    parser.add_argument(
        "--voice-text-prefix",
        default=str(os.getenv("PERMANENCE_TELEGRAM_CONTROL_VOICE_TEXT_PREFIX", "[Voice Note]")).strip(),
        help="Prefix text prepended to voice-note messages",
    )
    parser.add_argument(
        "--voice-transcribe-queue",
        help="Transcription queue JSON path for voice-note media",
    )
    parser.add_argument(
        "--no-voice-transcribe-queue",
        action="store_true",
        help="Do not queue voice-note media into transcription queue",
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse only; do not ingest into glasses-bridge")
    args = parser.parse_args(argv)

    token = str(os.getenv("PERMANENCE_TELEGRAM_BOT_TOKEN", "")).strip()
    if not token:
        print("Missing PERMANENCE_TELEGRAM_BOT_TOKEN")
        return 1
    target_chat_ids = _configured_target_chat_ids(args.chat_id or "")

    state_path = Path(args.state_path).expanduser() if args.state_path else _default_state_path()
    download_dir = Path(args.download_dir).expanduser() if args.download_dir else _default_download_dir()
    transcription_queue_path = (
        Path(args.voice_transcribe_queue).expanduser()
        if args.voice_transcribe_queue
        else _default_transcription_queue_path()
    )
    chat_history_path = Path(args.chat_history_path).expanduser() if args.chat_history_path else _default_chat_history_path()
    memory_path = Path(args.memory_path).expanduser() if args.memory_path else _default_memory_store_path()
    intake_path = Path(args.intake_path).expanduser() if args.intake_path else _default_intake_path()
    terminal_queue_path = (
        Path(args.terminal_queue_path).expanduser()
        if args.terminal_queue_path
        else _default_terminal_queue_path()
    )
    brain_vault_path = Path(args.brain_vault_path).expanduser() if args.brain_vault_path else _default_brain_vault_path()

    if args.action == "status":
        info = _api(token=token, method="getMe", timeout=max(1, int(args.timeout)))
        ok = bool(info.get("ok"))
        username = ((info.get("result") or {}).get("username") or "") if ok else ""
        print(f"Bot reachable: {'yes' if ok else 'no'}")
        if username:
            print(f"Bot username: @{username}")
        print(f"Target chat configured: {'yes' if bool(target_chat_ids) else 'no'}")
        if target_chat_ids:
            print(f"Target chat ids: {', '.join(sorted(target_chat_ids))}")
        else:
            print("Target chat ids: (all chats)")
        mirror_enabled = _imessage_mirror_enabled()
        print(f"iMessage mirror enabled: {'yes' if mirror_enabled else 'no'}")
        if mirror_enabled:
            print(f"iMessage target configured: {'yes' if bool(_imessage_target()) else 'no'}")
            print(f"iMessage service: {_imessage_service()}")
        return 0 if ok else 1

    state = _load_state(state_path)
    offset = _safe_int(state.get("offset"), 0)
    updates_payload = _api(
        token=token,
        method="getUpdates",
        params={"offset": offset, "limit": max(1, int(args.limit))},
        timeout=max(1, int(args.timeout)),
    )
    updates = updates_payload.get("result") if isinstance(updates_payload.get("result"), list) else []
    warnings: list[str] = []
    events: list[dict[str, Any]] = []
    command_runs: list[dict[str, Any]] = []
    ignored = 0
    commands_executed = 0
    commands_failed = 0
    commands_unauthorized = 0
    voice_notes_ingested = 0
    voice_transcribe_queued = 0
    chat_replies_sent = 0
    chat_replies_failed = 0
    chat_replies_fallback_sent = 0
    max_update_id = offset - 1
    commands_enabled_default = _is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_ENABLE_COMMANDS", "0"))
    commands_enabled = bool(args.enable_commands or commands_enabled_default)
    command_ack_default = _is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_COMMAND_ACK", "1"))
    command_ack_enabled = bool(command_ack_default and (not args.no_command_ack))
    max_commands = max(0, int(args.max_commands))
    command_prefix = str(args.command_prefix or "/")
    env_allowed_user_ids = _parse_id_allowlist(os.getenv("PERMANENCE_TELEGRAM_CONTROL_COMMAND_USER_IDS", ""))
    cli_allowed_user_ids = _parse_id_allowlist(",".join(str(item) for item in (args.command_allow_user_id or [])))
    allowed_user_ids = env_allowed_user_ids | cli_allowed_user_ids
    env_allowed_chat_ids = _parse_id_allowlist(os.getenv("PERMANENCE_TELEGRAM_CONTROL_COMMAND_CHAT_IDS", ""))
    cli_allowed_chat_ids = _parse_id_allowlist(",".join(str(item) for item in (args.command_allow_chat_id or [])))
    allowed_chat_ids = env_allowed_chat_ids | cli_allowed_chat_ids
    if commands_enabled and args.require_command_allowlist and (not allowed_user_ids) and (not allowed_chat_ids):
        warnings.append(
            "commands disabled: require-command-allowlist is enabled but no command user/chat ids are configured"
        )
        commands_enabled = False
    chat_agent_enabled_default = _is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_CHAT_AGENT_ENABLED", "0"))
    chat_agent_enabled = bool((args.chat_agent or chat_agent_enabled_default) and (not args.no_chat_agent))
    chat_task_type = str(args.chat_task_type or "execution").strip() or "execution"
    max_chat_replies = max(0, int(args.max_chat_replies))
    chat_max_history = max(0, int(args.chat_max_history))
    chat_memory_max_notes = max(0, int(args.chat_memory_max_notes))
    chat_brain_max_notes = max(0, int(args.chat_brain_max_notes))
    chat_reply_max_chars = max(120, int(args.chat_reply_max_chars))
    auto_memory_default = _is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_CHAT_AUTO_MEMORY", "1"))
    chat_auto_memory_enabled = bool((args.chat_auto_memory or auto_memory_default) and (not args.no_chat_auto_memory))
    memory_max_notes = max(20, int(args.memory_max_notes))
    memory_store = _load_memory_store(memory_path)
    memory_store_changed = False
    brain_chunks = _load_brain_chunks(brain_vault_path) if chat_agent_enabled else []
    if chat_agent_enabled and (not brain_chunks):
        warnings.append(
            f"brain vault empty/missing at {brain_vault_path}; run `python cli.py ophtxn-brain --action sync`."
        )
    chat_history_by_chat = _load_chat_history(chat_history_path) if chat_agent_enabled else {}
    chat_model_router = ModelRouter() if (chat_agent_enabled and ModelRouter) else None
    chat_fallback_enabled = _is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_CHAT_FALLBACK_ACK", "1"))
    if chat_agent_enabled and (chat_model_router is None):
        warnings.append("chat-agent enabled but model router unavailable.")
    if chat_agent_enabled and args.dry_run:
        warnings.append("chat-agent skipped during dry-run.")
    if commands_enabled and (not target_chat_ids) and (not allowed_user_ids) and (not allowed_chat_ids):
        print(
            "Commands mode requires target chat ids (--chat-id/PERMANENCE_TELEGRAM_CHAT_ID(S)) "
            "or command allowlist ids."
        )
        return 1

    for update in updates:
        if not isinstance(update, dict):
            ignored += 1
            continue
        update_id = _safe_int(update.get("update_id"), 0)
        max_update_id = max(max_update_id, update_id)
        msg = _extract_update_message(update)
        if not msg:
            ignored += 1
            continue
        chat = msg.get("chat") if isinstance(msg.get("chat"), dict) else {}
        current_chat_id = str(chat.get("id") or "").strip()
        if target_chat_ids and current_chat_id not in target_chat_ids:
            ignored += 1
            continue
        from_user = msg.get("from") if isinstance(msg.get("from"), dict) else {}
        if (not args.include_bot_messages) and bool(from_user.get("is_bot")):
            ignored += 1
            continue
        text = str(msg.get("text") or msg.get("caption") or "").strip()
        sender_user_id = str(from_user.get("id") or "").strip()
        sender_name = _extract_sender(msg)
        memory_key = _memory_key(chat_id=current_chat_id, sender_user_id=sender_user_id, sender_name=sender_name)
        if commands_enabled:
            command = _extract_command(text=text, prefix=command_prefix)
            if command:
                user_allowed = _is_command_user_allowed(sender_user_id=sender_user_id, allowed_user_ids=allowed_user_ids)
                chat_allowed = _is_command_chat_allowed(chat_id=current_chat_id, allowed_chat_ids=allowed_chat_ids)
                if (not _is_public_command(command)) and (not user_allowed) and (not chat_allowed):
                    commands_unauthorized += 1
                    warnings.append(
                        "unauthorized command "
                        f"`{command}` from user_id={sender_user_id or 'unknown'} chat_id={current_chat_id or 'unknown'}"
                    )
                    ignored += 1
                    continue
                if command in {"whoami", "comms-whoami"}:
                    sender_chat = msg.get("sender_chat") if isinstance(msg.get("sender_chat"), dict) else {}
                    sender_chat_id = str(sender_chat.get("id") or "").strip()
                    chat_type = str(chat.get("type") or "").strip()
                    run = {
                        "handled": True,
                        "command": command,
                        "ok": True,
                        "summary": (
                            f"user_id={sender_user_id or '-'} "
                            f"sender_chat_id={sender_chat_id or '-'} "
                            f"chat_id={current_chat_id or '-'} "
                            f"chat_type={chat_type or '-'}"
                        ),
                    }
                    command_runs.append(run)
                    commands_executed += 1
                    if command_ack_enabled and current_chat_id:
                        try:
                            _send_ack(
                                token=token,
                                chat_id=current_chat_id,
                                text=f"command `{command}`: ok\n{run.get('summary')}",
                                timeout=max(1, int(args.timeout)),
                            )
                        except Exception as exc:  # noqa: BLE001
                            warnings.append(f"command ack failed for `{command}`: {exc}")
                    ignored += 1
                    continue
                command_args = _extract_command_args(text=text, prefix=command_prefix)
                memory_run = _execute_memory_command(
                    command=command,
                    command_args=command_args,
                    store=memory_store,
                    memory_key=memory_key,
                    chat_id=current_chat_id,
                    sender_user_id=sender_user_id,
                    sender_name=sender_name,
                    max_notes=memory_max_notes,
                    intake_path=intake_path,
                    terminal_queue_path=terminal_queue_path,
                    prefix=command_prefix,
                )
                if memory_run.get("handled"):
                    command_runs.append(memory_run)
                    commands_executed += 1
                    if not bool(memory_run.get("ok")):
                        commands_failed += 1
                    if bool(memory_run.get("changed")):
                        memory_store_changed = True
                    if command_ack_enabled and current_chat_id:
                        try:
                            _send_ack(
                                token=token,
                                chat_id=current_chat_id,
                                text=(
                                    f"command `{command}`: "
                                    f"{'ok' if bool(memory_run.get('ok')) else 'failed'}\n"
                                    f"{memory_run.get('summary')}"
                                ),
                                timeout=max(1, int(args.timeout)),
                            )
                        except Exception as exc:  # noqa: BLE001
                            warnings.append(f"command ack failed for `{command}`: {exc}")
                    ignored += 1
                    continue
                if commands_executed >= max_commands:
                    warnings.append(f"command limit reached; skipped `{command}`")
                    ignored += 1
                    continue
                run = _execute_control_command(
                    command=command,
                    timeout=max(3, int(args.command_timeout)),
                    prefix=command_prefix,
                    command_args=command_args,
                )
                if run.get("handled"):
                    command_runs.append(run)
                    commands_executed += 1
                    if not bool(run.get("ok")):
                        commands_failed += 1
                    if command_ack_enabled and current_chat_id:
                        try:
                            _send_ack(
                                token=token,
                                chat_id=current_chat_id,
                                text=f"command `{command}`: {'ok' if bool(run.get('ok')) else 'failed'}\n{run.get('summary')}",
                                timeout=max(1, int(args.timeout)),
                            )
                        except Exception as exc:  # noqa: BLE001
                            warnings.append(f"command ack failed for `{command}`: {exc}")
                    ignored += 1
                    continue
        media_paths: list[str] = []
        media_types = _message_media_types(msg)
        is_voice_note = _is_voice_note_message(msg)
        if not args.skip_media:
            specs = _media_specs(msg)
            downloaded, media_warnings = _download_media(
                token=token,
                specs=specs,
                dest_dir=download_dir,
                timeout=max(5, int(args.timeout)),
            )
            media_paths.extend(downloaded)
            warnings.extend(media_warnings)
        event = _build_event(
            update=update,
            msg=msg,
            source=(str(args.voice_source).strip() if is_voice_note and str(args.voice_source).strip() else args.source),
            channel=(args.voice_channel if is_voice_note else args.channel),
            media_paths=media_paths,
            priority=(args.voice_priority if is_voice_note else "normal"),
            media_types=media_types,
            voice_note=is_voice_note,
        )
        if is_voice_note:
            voice_notes_ingested += 1
            prefix = str(args.voice_text_prefix or "").strip()
            body = str(event.get("message") or "").strip()
            if prefix:
                event["message"] = f"{prefix} {body}".strip()
            queue_enabled_env = _is_true(os.getenv("PERMANENCE_TELEGRAM_CONTROL_VOICE_QUEUE_ENABLED", "1"))
            queue_enabled = bool(queue_enabled_env and (not args.no_voice_transcribe_queue))
            if queue_enabled and media_paths:
                voice_transcribe_queued += _enqueue_transcription_items(
                    queue_path=transcription_queue_path,
                    media_paths=media_paths,
                    source=str(event.get("source") or args.source),
                    channel=str(event.get("channel") or args.channel),
                    sender=str(event.get("sender") or "telegram"),
                    message=str(event.get("message") or ""),
                    event_time=str(event.get("timestamp") or _now_iso()),
                )
        events.append(event)

        if chat_agent_enabled and (not args.dry_run) and current_chat_id:
            if chat_replies_sent >= max_chat_replies:
                if f"chat reply limit reached ({max_chat_replies})" not in warnings:
                    warnings.append(f"chat reply limit reached ({max_chat_replies})")
                continue
            user_text = text or str(event.get("message") or "").strip()
            if not user_text:
                continue
            if chat_auto_memory_enabled:
                added = _memory_add_note(
                    store=memory_store,
                    key=memory_key,
                    chat_id=current_chat_id,
                    sender_user_id=sender_user_id,
                    sender_name=sender_name,
                    text=user_text,
                    source="chat",
                    max_notes=memory_max_notes,
                )
                memory_store_changed = bool(memory_store_changed or added)
            profile = _memory_profile(memory_store, memory_key)
            fields = _profile_fields(profile)
            profile_prompt_lines = _profile_lines(profile)
            habit_prompt_lines = _habit_prompt_lines(profile, limit=6)
            prompt_memory_rows = _memory_context_notes(
                memory_store,
                memory_key,
                query=user_text,
                limit=chat_memory_max_notes,
            )
            prompt_brain_rows = _brain_context_notes(
                brain_chunks,
                query=user_text,
                limit=chat_brain_max_notes,
            )
            history_rows = list(chat_history_by_chat.get(current_chat_id) or [])
            history_rows.append(_chat_history_entry(role="user", text=user_text, sender=sender_name))
            prompt = _compose_chat_prompt(
                user_text=user_text,
                sender=sender_name,
                chat_id=current_chat_id,
                history_rows=history_rows,
                memory_rows=prompt_memory_rows,
                profile_lines=profile_prompt_lines,
                habit_lines=habit_prompt_lines,
                max_history_messages=chat_max_history,
                brain_rows=prompt_brain_rows,
            )
            system_prompt = _chat_system_prompt(
                personality_mode=str(fields.get("personality_mode") or _default_personality_mode()),
                profile_lines=profile_prompt_lines,
            )
            reply_text, reply_error = _generate_chat_reply(
                prompt=prompt,
                task_type=chat_task_type,
                model_router=chat_model_router,
                system_prompt=system_prompt,
            )
            if reply_error:
                chat_replies_failed += 1
                warnings.append(reply_error)
                if chat_fallback_enabled:
                    fallback = _chat_fallback_reply_text(user_text=user_text, command_prefix=command_prefix)
                    try:
                        _send_ack(
                            token=token,
                            chat_id=current_chat_id,
                            text=fallback,
                            timeout=max(1, int(args.timeout)),
                        )
                        chat_replies_fallback_sent += 1
                    except Exception as exc:  # noqa: BLE001
                        warnings.append(f"chat fallback send failed: {exc}")
                chat_history_by_chat[current_chat_id] = _trim_chat_history(history_rows, max_messages=chat_max_history)
                continue
            reply_text = _trim_reply_text(reply_text, max_chars=chat_reply_max_chars)
            if not reply_text:
                chat_replies_failed += 1
                warnings.append("chat response empty after trim")
                chat_history_by_chat[current_chat_id] = _trim_chat_history(history_rows, max_messages=chat_max_history)
                continue
            try:
                _send_ack(
                    token=token,
                    chat_id=current_chat_id,
                    text=reply_text,
                    timeout=max(1, int(args.timeout)),
                )
            except Exception as exc:  # noqa: BLE001
                chat_replies_failed += 1
                warnings.append(f"chat reply send failed: {exc}")
                chat_history_by_chat[current_chat_id] = _trim_chat_history(history_rows, max_messages=chat_max_history)
                continue
            history_rows.append(_chat_history_entry(role="assistant", text=reply_text, sender="assistant"))
            chat_history_by_chat[current_chat_id] = _trim_chat_history(history_rows, max_messages=chat_max_history)
            chat_replies_sent += 1

    if events and not args.dry_run:
        import scripts.glasses_bridge as bridge_mod  # noqa: WPS433

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            temp_json = Path(handle.name)
            handle.write(json.dumps(events, indent=2))
            handle.write("\n")
        try:
            bridge_mod.main(["--action", "ingest", "--from-json", str(temp_json)])
        finally:
            try:
                temp_json.unlink()
            except OSError:
                pass

    if chat_agent_enabled and (not args.dry_run):
        try:
            _save_chat_history(chat_history_path, chat_history_by_chat)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"failed to save chat history: {exc}")
    if memory_store_changed and (not args.dry_run):
        try:
            _save_memory_store(memory_path, memory_store)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"failed to save memory store: {exc}")

    next_offset = max(offset, max_update_id + 1) if updates else offset
    if not args.no_commit_offset and not args.dry_run:
        _save_state(
            state_path,
            {
                "offset": next_offset,
                "updated_at": _now_iso(),
                "processed_updates": _safe_int(state.get("processed_updates"), 0) + len(events) + commands_executed,
            },
        )

    md_path, json_path = _write_report(
        action=args.action,
        target_chat_ids=sorted(target_chat_ids),
        updates_count=len(updates),
        ingested_count=len(events),
        voice_notes_ingested=voice_notes_ingested,
        voice_transcribe_queued=voice_transcribe_queued,
        ignored_count=ignored,
        commands_executed=commands_executed,
        commands_failed=commands_failed,
        commands_unauthorized=commands_unauthorized,
        command_allowlist_user_ids=sorted(allowed_user_ids),
        command_allowlist_chat_ids=sorted(allowed_chat_ids),
        chat_agent_enabled=chat_agent_enabled,
        chat_replies_sent=chat_replies_sent,
        chat_replies_failed=chat_replies_failed,
        chat_replies_fallback_sent=chat_replies_fallback_sent,
        command_runs=command_runs,
        warnings=warnings,
        state_path=state_path,
        next_offset=next_offset,
    )
    print(f"Telegram control written: {md_path}")
    print(f"Telegram control latest: {_output_dir() / 'telegram_control_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Updates fetched: {len(updates)}")
    print(f"Events ingested: {len(events)}")
    print(f"Voice notes ingested: {voice_notes_ingested}")
    print(f"Voice transcribe queued: {voice_transcribe_queued}")
    print(f"Commands executed: {commands_executed}")
    print(f"Commands unauthorized: {commands_unauthorized}")
    print(f"Chat replies sent: {chat_replies_sent}")
    print(f"Chat replies failed: {chat_replies_failed}")
    print(f"Chat fallback replies sent: {chat_replies_fallback_sent}")
    if warnings:
        print(f"Warnings: {len(warnings)}")

    summary_chat_id = sorted(target_chat_ids)[0] if target_chat_ids else ""
    if args.ack and summary_chat_id:
        try:
            _send_ack(
                token=token,
                chat_id=summary_chat_id,
                text=f"telegram-control: updates={len(updates)} ingested={len(events)} ignored={ignored}",
                timeout=max(1, int(args.timeout)),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Ack failed: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
