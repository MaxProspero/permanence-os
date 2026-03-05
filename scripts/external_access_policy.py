#!/usr/bin/env python3
"""
Create a secure external-access policy report for agent connectors.

The report is advisory. It does not activate or deactivate any integration directly.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]


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


_load_local_env()
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
POLICY_PATH = Path(
    os.getenv("PERMANENCE_AGENT_ACCESS_POLICY_PATH", str(WORKING_DIR / "agent_access_policy.json"))
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _default_policy() -> dict[str, Any]:
    return {
        "version": "1.0",
        "created_at": _now_iso(),
        "model": "staged_external_access",
        "principles": [
            "Least privilege by default.",
            "Read-only connectors in phase one.",
            "Manual approval before any external write/publish action.",
            "Short-lived tokens and routine rotation.",
            "Per-connector kill switch and logging.",
        ],
        "connectors": {
            "github_read": {
                "enabled": True,
                "mode": "read_only",
                "recommended_auth": "GitHub App installation token or fine-grained PAT",
                "permissions": [
                    "metadata:read",
                    "contents:read",
                    "issues:read",
                    "pull_requests:read",
                    "actions:read",
                ],
                "allowed_repos": [],
            },
            "github_write": {
                "enabled": False,
                "mode": "manual_approval_only",
                "permissions": [
                    "contents:write",
                    "pull_requests:write",
                    "issues:write",
                ],
                "daily_write_limit": 10,
            },
            "social_research": {
                "enabled": True,
                "mode": "read_only",
                "platforms": ["x", "youtube", "reddit"],
                "notes": "Use public/feed analytics and trend collection only.",
            },
            "social_publish": {
                "enabled": False,
                "mode": "manual_approval_only",
                "platforms": ["x", "linkedin", "youtube"],
                "daily_publish_limit": 6,
            },
        },
        "guardrails": {
            "require_manual_approval_for_write": True,
            "require_human_review_for_money_actions": True,
            "require_action_logs": True,
            "auto_disable_on_policy_violation": True,
        },
    }


def _ensure_policy_template(path: Path, force: bool) -> tuple[dict[str, Any], str]:
    if path.exists() and not force:
        payload = _read_json(path, {})
        if isinstance(payload, dict) and payload:
            return payload, "existing"
    payload = _default_policy()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload, "written"


def _collect_connector_state() -> dict[str, Any]:
    keys = {
        "github_read_token": any(
            bool(str(os.getenv(name, "")).strip())
            for name in ("PERMANENCE_GITHUB_READ_TOKEN",)
        ),
        "github_generic_token": any(
            bool(str(os.getenv(name, "")).strip())
            for name in ("GH_TOKEN", "GITHUB_TOKEN")
        ),
        "github_write_token": any(
            bool(str(os.getenv(name, "")).strip())
            for name in ("PERMANENCE_GITHUB_WRITE_TOKEN",)
        ),
        "social_read_token": any(
            bool(str(os.getenv(name, "")).strip())
            for name in ("PERMANENCE_SOCIAL_READ_TOKEN", "PERMANENCE_X_READ_TOKEN")
        ),
        "social_publish_token": any(
            bool(str(os.getenv(name, "")).strip())
            for name in ("PERMANENCE_SOCIAL_PUBLISH_TOKEN", "PERMANENCE_X_PUBLISH_TOKEN")
        ),
        "discord_alert_webhook": bool(str(os.getenv("PERMANENCE_DISCORD_ALERT_WEBHOOK_URL", "")).strip()),
        "telegram_alert_token": bool(str(os.getenv("PERMANENCE_TELEGRAM_BOT_TOKEN", "")).strip()),
        "telegram_alert_chat": bool(str(os.getenv("PERMANENCE_TELEGRAM_CHAT_ID", "")).strip()),
        "external_write_enabled": _bool_env("PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE", default=False),
    }
    return keys


def _evaluate_risk(state: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    actions: list[str] = []

    write_tokens_present = bool(state.get("github_write_token") or state.get("social_publish_token"))
    write_enabled = bool(state.get("external_write_enabled"))

    if write_tokens_present and not write_enabled:
        warnings.append(
            "Write/publish token(s) are configured while write mode is disabled. Keep tokens removed until needed."
        )
    if write_enabled and not write_tokens_present:
        warnings.append(
            "External write mode is enabled but no write token is configured. Disable write mode unless actively needed."
        )
    if state.get("github_generic_token"):
        warnings.append(
            "Generic GitHub token detected (GH_TOKEN/GITHUB_TOKEN). Scope granularity may be broader than intended."
        )
    if not state.get("github_read_token"):
        actions.append("Set PERMANENCE_GITHUB_READ_TOKEN using repo-scoped read-only permissions.")
    if not state.get("social_read_token"):
        actions.append("Set PERMANENCE_SOCIAL_READ_TOKEN (or PERMANENCE_X_READ_TOKEN) for read-only trend ingest.")
    if state.get("telegram_alert_token") and not state.get("telegram_alert_chat"):
        warnings.append("Telegram bot token is set but PERMANENCE_TELEGRAM_CHAT_ID is missing.")
    if state.get("telegram_alert_chat") and not state.get("telegram_alert_token"):
        warnings.append("PERMANENCE_TELEGRAM_CHAT_ID is set but Telegram bot token is missing.")
    if not state.get("discord_alert_webhook"):
        actions.append("Set PERMANENCE_DISCORD_ALERT_WEBHOOK_URL to receive world-watch alerts in Discord.")
    if not state.get("telegram_alert_token"):
        actions.append("Set PERMANENCE_TELEGRAM_BOT_TOKEN if you want Telegram alert delivery.")
    if state.get("telegram_alert_token") and not state.get("telegram_alert_chat"):
        actions.append("Set PERMANENCE_TELEGRAM_CHAT_ID for Telegram alert delivery.")
    actions.append("Keep PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE=0 during research phase.")
    actions.append("Only create write tokens when publish workflows are ready and approval queue is active.")

    if write_enabled and write_tokens_present:
        return "high", warnings, actions
    if warnings:
        return "medium", warnings, actions
    return "low", warnings, actions


def _write_outputs(
    policy: dict[str, Any],
    policy_status: str,
    state: dict[str, Any],
    risk_level: str,
    warnings: list[str],
    actions: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"external_access_policy_{stamp}.md"
    latest_md = OUTPUT_DIR / "external_access_policy_latest.md"
    json_path = TOOL_DIR / f"external_access_policy_{stamp}.json"

    lines = [
        "# External Access Policy",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Policy file: {POLICY_PATH}",
        f"Policy status: {policy_status}",
        "",
        "## Risk Summary",
        f"- Risk level: {risk_level.upper()}",
        f"- External write enabled: {bool(state.get('external_write_enabled'))}",
        f"- GitHub read token present: {bool(state.get('github_read_token'))}",
        f"- GitHub generic token present: {bool(state.get('github_generic_token'))}",
        f"- GitHub write token present: {bool(state.get('github_write_token'))}",
        f"- Social read token present: {bool(state.get('social_read_token'))}",
        f"- Social publish token present: {bool(state.get('social_publish_token'))}",
        f"- Discord alert webhook present: {bool(state.get('discord_alert_webhook'))}",
        f"- Telegram alert token present: {bool(state.get('telegram_alert_token'))}",
        f"- Telegram alert chat configured: {bool(state.get('telegram_alert_chat'))}",
    ]

    if warnings:
        lines.extend(["", "## Warnings"])
        for row in warnings:
            lines.append(f"- {row}")

    lines.extend(["", "## Recommended Actions"])
    for row in actions:
        lines.append(f"- {row}")

    lines.extend(
        [
            "",
            "## Deployment Stages",
            "1. Research-only: read connectors only, no external writes.",
            "2. Supervised write: approval queue required for every outbound action.",
            "3. Limited autopilot: only pre-approved low-risk actions with hard caps.",
            "",
        ]
    )

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "policy_path": str(POLICY_PATH),
        "policy_status": policy_status,
        "risk_level": risk_level,
        "state": state,
        "warnings": warnings,
        "actions": actions,
        "policy": policy,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate external connector access policy report.")
    parser.add_argument("--force-template", action="store_true", help="Overwrite policy template file")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when risk level is high")
    args = parser.parse_args(argv)

    policy, policy_status = _ensure_policy_template(POLICY_PATH, force=args.force_template)
    state = _collect_connector_state()
    risk_level, warnings, actions = _evaluate_risk(state)
    md_path, json_path = _write_outputs(policy, policy_status, state, risk_level, warnings, actions)

    print(f"External access policy written: {md_path}")
    print(f"External access policy latest: {OUTPUT_DIR / 'external_access_policy_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Risk level: {risk_level.upper()}")
    if args.strict and risk_level == "high":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
