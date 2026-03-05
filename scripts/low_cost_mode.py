#!/usr/bin/env python3
"""
Apply and report a low-cost operating profile for Permanence OS.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
ENV_PATH = BASE_DIR / ".env"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _load_env() -> dict[str, str]:
    env = dict(os.environ)
    if not ENV_PATH.exists():
        return env
    for raw_line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        env[key] = value
    return env


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _update_env_keys(path: Path, updates: dict[str, str]) -> tuple[bool, str]:
    lines: list[str] = []
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            return False, str(exc)
    merged: list[str] = []
    remaining = dict(updates)
    for raw in lines:
        if "=" in raw and (not raw.lstrip().startswith("#")):
            key, _old = raw.split("=", 1)
            key = key.strip()
            if key in remaining:
                merged.append(f"{key}={remaining.pop(key)}")
                continue
        merged.append(raw)
    if remaining:
        if merged and merged[-1].strip():
            merged.append("")
        merged.append("# Managed by scripts/low_cost_mode.py")
        for key, value in remaining.items():
            merged.append(f"{key}={value}")
    try:
        path.write_text("\n".join(merged).rstrip() + "\n", encoding="utf-8")
    except OSError as exc:
        return False, str(exc)
    return True, ""


def _profile_values(
    *,
    monthly_budget: float,
    milestone_usd: int,
    chat_agent_enabled: bool,
) -> dict[str, str]:
    return {
        "PERMANENCE_LOW_COST_MODE": "1",
        "PERMANENCE_MODEL_PROVIDER": "ollama",
        "PERMANENCE_MODEL_PROVIDER_FALLBACKS": "ollama",
        "PERMANENCE_MODEL_PROVIDER_CAPS_USD": "anthropic=5,openai=2,xai=2,ollama=0",
        "PERMANENCE_MODEL_OPUS": "qwen2.5:3b",
        "PERMANENCE_MODEL_SONNET": "qwen2.5:3b",
        "PERMANENCE_MODEL_HAIKU": "qwen2.5:3b",
        "PERMANENCE_DEFAULT_MODEL": "qwen2.5:3b",
        "PERMANENCE_LLM_MONTHLY_BUDGET_USD": str(max(1.0, float(monthly_budget))),
        "PERMANENCE_MODEL_BUDGET_WARNING_RATIO": "0.5",
        "PERMANENCE_MODEL_BUDGET_CRITICAL_RATIO": "0.75",
        "PERMANENCE_TELEGRAM_CONTROL_CHAT_AGENT_ENABLED": "1" if chat_agent_enabled else "0",
        "PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE": "1",
        "PERMANENCE_FEATURE_GATE_MILESTONE_USD": str(max(1, int(milestone_usd))),
        "PERMANENCE_FEATURE_GATE_MIN_WON_DEALS": "1",
    }


def _status_row(env: dict[str, str]) -> dict[str, Any]:
    mode_enabled = str(env.get("PERMANENCE_LOW_COST_MODE", "0")).strip().lower() in {"1", "true", "yes", "on"}
    provider = str(env.get("PERMANENCE_MODEL_PROVIDER", "anthropic")).strip().lower() or "anthropic"
    caps = str(env.get("PERMANENCE_MODEL_PROVIDER_CAPS_USD", "")).strip() or "-"
    monthly_budget = _safe_float(env.get("PERMANENCE_LLM_MONTHLY_BUDGET_USD"), 50.0)
    gate_enabled = str(env.get("PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    milestone_usd = _safe_int(env.get("PERMANENCE_FEATURE_GATE_MILESTONE_USD"), 500)
    chat_agent_enabled = str(env.get("PERMANENCE_TELEGRAM_CONTROL_CHAT_AGENT_ENABLED", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return {
        "mode_enabled": mode_enabled,
        "provider": provider,
        "provider_caps": caps,
        "monthly_budget_usd": monthly_budget,
        "feature_gate_enabled": gate_enabled,
        "milestone_usd": milestone_usd,
        "telegram_chat_agent_enabled": chat_agent_enabled,
    }


def _write_outputs(action: str, status: dict[str, Any], updates: dict[str, str], warnings: list[str]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"low_cost_mode_{stamp}.md"
    latest_md = OUTPUT_DIR / "low_cost_mode_latest.md"
    json_path = TOOL_DIR / f"low_cost_mode_{stamp}.json"

    lines = [
        "# Low Cost Mode",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Env path: {ENV_PATH}",
        "",
        "## Status",
        f"- Low-cost mode enabled: {status.get('mode_enabled')}",
        f"- Model provider: {status.get('provider')}",
        f"- Provider caps: {status.get('provider_caps')}",
        f"- Monthly budget (USD): {status.get('monthly_budget_usd')}",
        f"- Revenue milestone gate enabled: {status.get('feature_gate_enabled')}",
        f"- Revenue milestone (USD): {status.get('milestone_usd')}",
        f"- Telegram chat agent enabled: {status.get('telegram_chat_agent_enabled')}",
    ]
    if updates:
        lines.extend(["", "## Applied Updates"])
        for key, value in updates.items():
            lines.append(f"- {key}={value}")
    if warnings:
        lines.extend(["", "## Warnings"])
        for row in warnings:
            lines.append(f"- {row}")
    lines.extend(
        [
            "",
            "## Notes",
            "- Low-cost mode routes by default to local Ollama to minimize paid token usage.",
            "- Feature loops can be gated until first revenue milestone is reached.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "env_path": str(ENV_PATH),
        "status": status,
        "applied_updates": updates,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply/status low-cost operating profile.")
    parser.add_argument("--action", choices=["status", "enable", "disable"], default="status")
    parser.add_argument("--monthly-budget", type=float, default=10.0, help="Budget cap used on enable")
    parser.add_argument("--milestone-usd", type=int, default=500, help="Revenue milestone used on enable")
    parser.add_argument(
        "--chat-agent",
        action="store_true",
        help="Keep Telegram chat-agent enabled when enabling low-cost mode",
    )
    args = parser.parse_args(argv)

    warnings: list[str] = []
    updates: dict[str, str] = {}
    if args.action == "enable":
        updates = _profile_values(
            monthly_budget=max(1.0, float(args.monthly_budget)),
            milestone_usd=max(1, int(args.milestone_usd)),
            chat_agent_enabled=bool(args.chat_agent),
        )
        ok, error = _update_env_keys(ENV_PATH, updates)
        if not ok:
            warnings.append(f"failed to update env: {error}")
    elif args.action == "disable":
        updates = {
            "PERMANENCE_LOW_COST_MODE": "0",
            "PERMANENCE_FEATURE_WORK_REQUIRE_REVENUE_MILESTONE": "0",
            "PERMANENCE_TELEGRAM_CONTROL_CHAT_AGENT_ENABLED": "1",
        }
        ok, error = _update_env_keys(ENV_PATH, updates)
        if not ok:
            warnings.append(f"failed to update env: {error}")

    env = _load_env()
    status = _status_row(env)
    md_path, json_path = _write_outputs(action=args.action, status=status, updates=updates, warnings=warnings)
    print(f"Low-cost mode report: {md_path}")
    print(f"Low-cost mode latest: {OUTPUT_DIR / 'low_cost_mode_latest.md'}")
    print(f"Tool payload: {json_path}")
    print(f"Low-cost mode enabled: {status.get('mode_enabled')}")
    if warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
