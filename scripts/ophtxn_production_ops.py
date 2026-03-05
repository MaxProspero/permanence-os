#!/usr/bin/env python3
"""
Ophtxn production deployment operations (domain + hosting + analytics + lead capture).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))

CONFIG_PATH_DEFAULT = WORKING_DIR / "ophtxn_production_config.json"
RUNTIME_CONFIG_PATH = BASE_DIR / "site" / "foundation" / "runtime.config.js"
SITE_INDEX_PATH = BASE_DIR / "site" / "foundation" / "index.html"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _config_template() -> dict[str, Any]:
    return {
        "updated_at": _now_iso(),
        "profile": "no_spend",
        "hosting": {
            "provider": "cloudflare_pages",
            "project_name": "ophtxn-official",
            "deploy_dir": "site/foundation",
            "primary_url": "https://ophtxn.pages.dev",
            "api_base_url": "http://127.0.0.1:8000",
            "deploy_command": "npx wrangler pages deploy site/foundation --project-name ophtxn-official",
        },
        "domain": {
            "primary_domain": "",
            "api_domain": "",
            "registrar": "",
            "annual_cost_usd": 12.0,
        },
        "analytics": {
            "strategy": "first_party_site_event",
            "site_event_endpoint": "/api/revenue/site-event",
            "cloudflare_web_analytics_enabled": False,
            "cloudflare_web_analytics_token": "",
        },
        "lead_capture": {
            "strategy": "dashboard_api_revenue_intake",
            "endpoint": "/api/revenue/intake",
            "fallback_email": "paybhicks7@gmail.com",
            "create_lead_default": True,
        },
        "budget": {
            "monthly_hosting_usd": 0.0,
            "monthly_analytics_usd": 0.0,
            "monthly_lead_capture_usd": 0.0,
            "monthly_monitoring_usd": 0.0,
            "monthly_contingency_usd": 0.0,
        },
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return payload


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_config(path: Path, force_template: bool = False) -> dict[str, Any]:
    template = _config_template()
    if force_template or (not path.exists()):
        _save_json(path, template)
        return template
    payload = _load_json(path, {})
    if not isinstance(payload, dict):
        _save_json(path, template)
        return template

    merged = dict(template)
    for key in ("hosting", "domain", "analytics", "lead_capture", "budget"):
        value = payload.get(key)
        if isinstance(value, dict):
            section = dict(template.get(key) or {})
            section.update(value)
            merged[key] = section
    for key in ("profile", "updated_at"):
        if key in payload:
            merged[key] = payload[key]
    return merged


def _runtime_config_text(config: dict[str, Any]) -> str:
    hosting = config.get("hosting") if isinstance(config.get("hosting"), dict) else {}
    analytics = config.get("analytics") if isinstance(config.get("analytics"), dict) else {}
    lead_capture = config.get("lead_capture") if isinstance(config.get("lead_capture"), dict) else {}

    site_url = str(hosting.get("primary_url") or "").strip() or "http://127.0.0.1:8787"
    api_base = str(hosting.get("api_base_url") or "").strip() or "http://127.0.0.1:8000"
    source = "foundation_site"
    site_event_endpoint = str(analytics.get("site_event_endpoint") or "/api/revenue/site-event").strip()
    lead_capture_endpoint = str(lead_capture.get("endpoint") or "/api/revenue/intake").strip()
    fallback_email = str(lead_capture.get("fallback_email") or "paybhicks7@gmail.com").strip()

    lines = [
        "window.__OPHTXN_RUNTIME = {",
        f'  siteUrl: "{site_url}",',
        f'  apiBase: "{api_base}",',
        f'  source: "{source}",',
        "  analyticsEnabled: true,",
        "  trackPageViews: true,",
        "  trackCtas: true,",
        "  leadCaptureEnabled: true,",
        f'  leadCaptureEndpoint: "{lead_capture_endpoint}",',
        f'  siteEventEndpoint: "{site_event_endpoint}",',
        f'  fallbackEmail: "{fallback_email}",',
        "};",
        "",
    ]
    return "\n".join(lines)


def _render_runtime_config(config: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_runtime_config_text(config), encoding="utf-8")


def _contains_token(path: Path, token: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return token in text


def _api_reachable(url: str, timeout: int = 6) -> tuple[bool, str]:
    token = str(url or "").strip()
    if not token:
        return False, "missing"
    try:
        proc = subprocess.run(
            ["curl", "-fsS", "--max-time", str(max(2, int(timeout))), token],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False, "curl-unavailable"
    if proc.returncode == 0:
        return True, "ok"
    detail = (proc.stderr or proc.stdout or "curl-failed").strip()
    return False, detail[:160]


def _wrangler_status() -> dict[str, Any]:
    wrangler_available = bool(shutil.which("npx"))
    if not wrangler_available:
        return {"npx_available": False, "wrangler_auth": False, "detail": "npx missing"}
    proc = subprocess.run(
        ["npx", "--yes", "wrangler", "whoami"],
        check=False,
        capture_output=True,
        text=True,
    )
    detail = (proc.stdout or proc.stderr or "").strip()
    lowered = detail.lower()
    ok = proc.returncode == 0 and ("not authenticated" not in lowered) and ("run `wrangler login`" not in lowered)
    return {"npx_available": True, "wrangler_auth": ok, "detail": detail[:300]}


def _status(config: dict[str, Any], check_api: bool, check_wrangler: bool) -> dict[str, Any]:
    hosting = config.get("hosting") if isinstance(config.get("hosting"), dict) else {}
    domain = config.get("domain") if isinstance(config.get("domain"), dict) else {}

    deploy_dir = BASE_DIR / str(hosting.get("deploy_dir") or "site/foundation")
    api_base = str(hosting.get("api_base_url") or "").strip()
    primary_domain = str(domain.get("primary_domain") or "").strip()
    api_domain = str(domain.get("api_domain") or "").strip()
    primary_url = str(hosting.get("primary_url") or "").strip()
    api_base_url = str(hosting.get("api_base_url") or "").strip()

    checks: list[dict[str, Any]] = [
        {"name": "foundation_index_exists", "ok": SITE_INDEX_PATH.exists(), "path": str(SITE_INDEX_PATH)},
        {
            "name": "runtime_config_exists",
            "ok": RUNTIME_CONFIG_PATH.exists(),
            "path": str(RUNTIME_CONFIG_PATH),
        },
        {"name": "deploy_dir_exists", "ok": deploy_dir.exists(), "path": str(deploy_dir)},
        {
            "name": "lead_form_present",
            "ok": _contains_token(SITE_INDEX_PATH, 'id="leadForm"'),
            "path": str(SITE_INDEX_PATH),
        },
        {
            "name": "site_event_tracking_present",
            "ok": _contains_token(SITE_INDEX_PATH, "intake_captured") and _contains_token(SITE_INDEX_PATH, "cta_click"),
            "path": str(SITE_INDEX_PATH),
        },
        {
            "name": "revenue_intake_endpoint_present",
            "ok": _contains_token(BASE_DIR / "dashboard_api.py", '"/api/revenue/intake"'),
            "path": str(BASE_DIR / "dashboard_api.py"),
        },
        {
            "name": "site_event_endpoint_present",
            "ok": _contains_token(BASE_DIR / "dashboard_api.py", '"/api/revenue/site-event"'),
            "path": str(BASE_DIR / "dashboard_api.py"),
        },
        {
            "name": "domain_primary_configured",
            "ok": bool(primary_domain or primary_url),
            "value": primary_domain or primary_url or "",
        },
        {
            "name": "domain_api_configured",
            "ok": bool(api_domain or api_base_url),
            "value": api_domain or api_base_url or "",
        },
    ]

    api_probe = {"url": f"{api_base.rstrip('/')}/api/status" if api_base else "", "ok": False, "detail": "skipped"}
    if check_api and api_base:
        ok, detail = _api_reachable(api_probe["url"])
        api_probe = {"url": api_probe["url"], "ok": ok, "detail": detail}

    wrangler = {"npx_available": False, "wrangler_auth": False, "detail": "skipped"}
    if check_wrangler:
        wrangler = _wrangler_status()

    passed = sum(1 for row in checks if bool(row.get("ok")))
    score = round((passed / len(checks)) * 100.0, 1) if checks else 0.0
    return {
        "generated_at": _now_iso(),
        "checks": checks,
        "score": score,
        "api_probe": api_probe,
        "wrangler": wrangler,
    }


def _configure(
    *,
    config: dict[str, Any],
    site_url: str,
    api_base: str,
    primary_domain: str,
    api_domain: str,
    fallback_email: str,
    monthly_hosting: float | None,
    monthly_analytics: float | None,
    monthly_lead_capture: float | None,
    monthly_monitoring: float | None,
    monthly_contingency: float | None,
    annual_domain_cost: float | None,
    no_spend: bool,
) -> dict[str, Any]:
    out = dict(config)
    hosting = out.get("hosting") if isinstance(out.get("hosting"), dict) else {}
    domain = out.get("domain") if isinstance(out.get("domain"), dict) else {}
    lead_capture = out.get("lead_capture") if isinstance(out.get("lead_capture"), dict) else {}
    budget = out.get("budget") if isinstance(out.get("budget"), dict) else {}

    hosting = dict(hosting)
    domain = dict(domain)
    lead_capture = dict(lead_capture)
    budget = dict(budget)

    if site_url:
        hosting["primary_url"] = site_url
    if api_base:
        hosting["api_base_url"] = api_base
    if primary_domain:
        domain["primary_domain"] = primary_domain
    if api_domain:
        domain["api_domain"] = api_domain
    if fallback_email:
        lead_capture["fallback_email"] = fallback_email

    if monthly_hosting is not None:
        budget["monthly_hosting_usd"] = max(0.0, float(monthly_hosting))
    if monthly_analytics is not None:
        budget["monthly_analytics_usd"] = max(0.0, float(monthly_analytics))
    if monthly_lead_capture is not None:
        budget["monthly_lead_capture_usd"] = max(0.0, float(monthly_lead_capture))
    if monthly_monitoring is not None:
        budget["monthly_monitoring_usd"] = max(0.0, float(monthly_monitoring))
    if monthly_contingency is not None:
        budget["monthly_contingency_usd"] = max(0.0, float(monthly_contingency))
    if annual_domain_cost is not None:
        domain["annual_cost_usd"] = max(0.0, float(annual_domain_cost))
    if no_spend:
        budget["monthly_hosting_usd"] = 0.0
        budget["monthly_analytics_usd"] = 0.0
        budget["monthly_lead_capture_usd"] = 0.0
        budget["monthly_monitoring_usd"] = 0.0
        budget["monthly_contingency_usd"] = 0.0

    out["hosting"] = hosting
    out["domain"] = domain
    out["lead_capture"] = lead_capture
    out["budget"] = budget
    if no_spend:
        out["profile"] = "no_spend"
    out["updated_at"] = _now_iso()
    return out


def _estimate(config: dict[str, Any]) -> dict[str, Any]:
    domain = config.get("domain") if isinstance(config.get("domain"), dict) else {}
    budget = config.get("budget") if isinstance(config.get("budget"), dict) else {}

    domain_annual = max(0.0, _safe_float(domain.get("annual_cost_usd"), 12.0))
    monthly_hosting = max(0.0, _safe_float(budget.get("monthly_hosting_usd"), 0.0))
    monthly_analytics = max(0.0, _safe_float(budget.get("monthly_analytics_usd"), 0.0))
    monthly_lead_capture = max(0.0, _safe_float(budget.get("monthly_lead_capture_usd"), 0.0))
    monthly_monitoring = max(0.0, _safe_float(budget.get("monthly_monitoring_usd"), 0.0))
    monthly_contingency = max(0.0, _safe_float(budget.get("monthly_contingency_usd"), 0.0))

    monthly_total = round(
        monthly_hosting
        + monthly_analytics
        + monthly_lead_capture
        + monthly_monitoring
        + monthly_contingency,
        2,
    )
    annual_total = round((monthly_total * 12.0) + domain_annual, 2)

    return {
        "generated_at": _now_iso(),
        "monthly": {
            "hosting_usd": monthly_hosting,
            "analytics_usd": monthly_analytics,
            "lead_capture_usd": monthly_lead_capture,
            "monitoring_usd": monthly_monitoring,
            "contingency_usd": monthly_contingency,
            "total_usd": monthly_total,
        },
        "annual": {
            "domain_usd": domain_annual,
            "runrate_usd": round(monthly_total * 12.0, 2),
            "total_usd": annual_total,
        },
        "mode": "no_spend" if monthly_total == 0.0 else "spend",
    }


def _deploy_plan(config: dict[str, Any]) -> list[str]:
    hosting = config.get("hosting") if isinstance(config.get("hosting"), dict) else {}
    domain = config.get("domain") if isinstance(config.get("domain"), dict) else {}
    deploy_dir = str(hosting.get("deploy_dir") or "site/foundation").strip() or "site/foundation"
    project = str(hosting.get("project_name") or "ophtxn-official").strip() or "ophtxn-official"
    primary_domain = str(domain.get("primary_domain") or "").strip() or "<your-domain>"

    return [
        "python cli.py ophtxn-production --action preflight --check-wrangler",
        "python cli.py ophtxn-production --action render-runtime",
        "python cli.py ophtxn-production --action status --check-api",
        f"npx wrangler pages project create {project}",
        f"npx wrangler pages deploy {deploy_dir} --project-name {project}",
        f"npx wrangler pages deployment list --project-name {project}",
        f"# In Cloudflare Pages: attach custom domain {primary_domain}",
        "python cli.py ophtxn-production --action estimate",
    ]


def _preflight(check_wrangler: bool) -> dict[str, Any]:
    tools = []
    for name in ("python3", "curl", "node", "npm", "npx"):
        path = shutil.which(name)
        tools.append({"name": name, "ok": bool(path), "path": path or ""})

    wrangler = {"npx_available": False, "wrangler_auth": False, "detail": "skipped"}
    if check_wrangler or bool(shutil.which("npx")):
        wrangler = _wrangler_status()

    recommendations: list[str] = []
    missing = {row["name"] for row in tools if not bool(row.get("ok"))}
    if {"node", "npm", "npx"} & missing:
        recommendations.append("Install Node.js (includes npm+npx): brew install node")
    if "curl" in missing:
        recommendations.append("Install curl and ensure it is available in PATH")
    if bool(shutil.which("npx")) and not bool(wrangler.get("wrangler_auth")):
        recommendations.append("Authenticate Cloudflare CLI: npx wrangler login && npx wrangler whoami")

    return {
        "generated_at": _now_iso(),
        "tools": tools,
        "wrangler": wrangler,
        "recommendations": recommendations,
    }


def _write_outputs(
    *,
    action: str,
    config_path: Path,
    config: dict[str, Any],
    status: dict[str, Any] | None,
    preflight: dict[str, Any] | None,
    estimate: dict[str, Any] | None,
    deploy_plan: list[str] | None,
    output_override: Path | None,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S-%f")
    md_path = output_override if output_override else OUTPUT_DIR / f"ophtxn_production_ops_{stamp}.md"
    latest_md = OUTPUT_DIR / "ophtxn_production_ops_latest.md"
    json_path = TOOL_DIR / f"ophtxn_production_ops_{stamp}.json"

    lines: list[str] = [
        "# Ophtxn Production Ops",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Config: {config_path}",
        "",
        "## Deployment Configuration",
        f"- Profile: {config.get('profile')}",
        f"- Hosting provider: {((config.get('hosting') or {}).get('provider') if isinstance(config.get('hosting'), dict) else '-')}",
        f"- Deploy dir: {((config.get('hosting') or {}).get('deploy_dir') if isinstance(config.get('hosting'), dict) else '-')}",
        f"- Site URL: {((config.get('hosting') or {}).get('primary_url') if isinstance(config.get('hosting'), dict) else '-')}",
        f"- API base URL: {((config.get('hosting') or {}).get('api_base_url') if isinstance(config.get('hosting'), dict) else '-')}",
        f"- Primary domain: {((config.get('domain') or {}).get('primary_domain') if isinstance(config.get('domain'), dict) else '-')}",
        f"- API domain: {((config.get('domain') or {}).get('api_domain') if isinstance(config.get('domain'), dict) else '-')}",
        "",
    ]

    if status:
        lines.extend(["## Status", f"- Readiness score: {status.get('score')}", ""])
        checks = status.get("checks") if isinstance(status.get("checks"), list) else []
        for row in checks:
            lines.append(f"- {row.get('name')}: ok={row.get('ok')} ({row.get('path') or row.get('value') or '-'})")
        api_probe = status.get("api_probe") if isinstance(status.get("api_probe"), dict) else {}
        lines.extend(
            [
                "",
                "## API Probe",
                f"- URL: {api_probe.get('url') or '-'}",
                f"- Reachable: {api_probe.get('ok')}",
                f"- Detail: {api_probe.get('detail') or '-'}",
            ]
        )
        wrangler = status.get("wrangler") if isinstance(status.get("wrangler"), dict) else {}
        lines.extend(
            [
                "",
                "## Wrangler",
                f"- npx available: {wrangler.get('npx_available')}",
                f"- wrangler auth: {wrangler.get('wrangler_auth')}",
                f"- detail: {wrangler.get('detail') or '-'}",
            ]
        )

    if preflight:
        tool_rows = preflight.get("tools") if isinstance(preflight.get("tools"), list) else []
        lines.extend(["", "## Preflight"])
        for row in tool_rows:
            lines.append(f"- tool:{row.get('name')} ok={row.get('ok')} path={row.get('path') or '-'}")
        wrangler = preflight.get("wrangler") if isinstance(preflight.get("wrangler"), dict) else {}
        lines.extend(
            [
                f"- wrangler npx available: {wrangler.get('npx_available')}",
                f"- wrangler auth: {wrangler.get('wrangler_auth')}",
                f"- wrangler detail: {wrangler.get('detail') or '-'}",
            ]
        )
        recs = preflight.get("recommendations") if isinstance(preflight.get("recommendations"), list) else []
        if recs:
            lines.append("- recommendations:")
            for row in recs:
                lines.append(f"  - {row}")

    if estimate:
        monthly = estimate.get("monthly") if isinstance(estimate.get("monthly"), dict) else {}
        annual = estimate.get("annual") if isinstance(estimate.get("annual"), dict) else {}
        lines.extend(
            [
                "",
                "## Cost Estimate",
                f"- Mode: {estimate.get('mode')}",
                f"- Monthly total (USD): {monthly.get('total_usd')}",
                f"- Annual total incl. domain (USD): {annual.get('total_usd')}",
                f"- Monthly hosting: {monthly.get('hosting_usd')}",
                f"- Monthly analytics: {monthly.get('analytics_usd')}",
                f"- Monthly lead capture: {monthly.get('lead_capture_usd')}",
                f"- Monthly monitoring: {monthly.get('monitoring_usd')}",
                f"- Monthly contingency: {monthly.get('contingency_usd')}",
                f"- Domain annual: {annual.get('domain_usd')}",
            ]
        )

    if deploy_plan:
        lines.extend(["", "## Deploy Plan", *[f"{idx}. {step}" for idx, step in enumerate(deploy_plan, start=1)]])

    lines.extend(
        [
            "",
            "## Commands",
            "- `python cli.py ophtxn-production --action init`",
            "- `python cli.py ophtxn-production --action configure --domain ophtxn.<company-domain> --api-domain api.<company-domain> --site-url https://ophtxn.<company-domain> --api-base https://api.<company-domain> --no-spend`",
            "- `python cli.py ophtxn-production --action preflight --check-wrangler`",
            "- `python cli.py ophtxn-production --action render-runtime`",
            "- `python cli.py ophtxn-production --action status --check-api --check-wrangler`",
            "- `python cli.py ophtxn-production --action estimate`",
            "- `python cli.py ophtxn-production --action deploy-plan`",
            "",
        ]
    )

    markdown = "\n".join(lines)
    md_path.write_text(markdown + "\n", encoding="utf-8")
    latest_md.write_text(markdown + "\n", encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "config_path": str(config_path),
        "config": config,
        "status": status,
        "preflight": preflight,
        "estimate": estimate,
        "deploy_plan": deploy_plan,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Ophtxn production deployment operations.")
    parser.add_argument(
        "--action",
        choices=["init", "configure", "preflight", "render-runtime", "status", "estimate", "deploy-plan"],
        default="status",
        help="Action to execute",
    )
    parser.add_argument("--config", help="Config JSON path")
    parser.add_argument("--force-template", action="store_true", help="Overwrite config template on init")
    parser.add_argument("--check-api", action="store_true", help="Probe configured API /api/status endpoint")
    parser.add_argument("--check-wrangler", action="store_true", help="Probe `npx wrangler whoami` auth status")
    parser.add_argument("--strict", action="store_true", help="Fail when required status checks are missing")
    parser.add_argument("--min-score", type=float, default=80.0, help="Strict readiness threshold")
    parser.add_argument("--site-url", default="", help="Set hosting.primary_url")
    parser.add_argument("--api-base", default="", help="Set hosting.api_base_url")
    parser.add_argument("--domain", default="", help="Set domain.primary_domain")
    parser.add_argument("--api-domain", default="", help="Set domain.api_domain")
    parser.add_argument("--fallback-email", default="", help="Set lead_capture.fallback_email")
    parser.add_argument("--monthly-hosting", type=float, help="Set budget.monthly_hosting_usd")
    parser.add_argument("--monthly-analytics", type=float, help="Set budget.monthly_analytics_usd")
    parser.add_argument("--monthly-lead-capture", type=float, help="Set budget.monthly_lead_capture_usd")
    parser.add_argument("--monthly-monitoring", type=float, help="Set budget.monthly_monitoring_usd")
    parser.add_argument("--monthly-contingency", type=float, help="Set budget.monthly_contingency_usd")
    parser.add_argument("--annual-domain-cost", type=float, help="Set domain.annual_cost_usd")
    parser.add_argument(
        "--no-spend",
        action="store_true",
        help="Set all monthly budget fields to zero and mark profile=no_spend",
    )
    parser.add_argument("--output", help="Optional markdown output path")
    args = parser.parse_args(argv)

    config_path = Path(args.config).expanduser() if args.config else CONFIG_PATH_DEFAULT
    config = _load_config(config_path, force_template=bool(args.force_template and args.action == "init"))

    if args.action == "init":
        config["updated_at"] = _now_iso()
        _save_json(config_path, config)
    elif args.action == "configure":
        config = _configure(
            config=config,
            site_url=str(args.site_url or "").strip(),
            api_base=str(args.api_base or "").strip(),
            primary_domain=str(args.domain or "").strip(),
            api_domain=str(args.api_domain or "").strip(),
            fallback_email=str(args.fallback_email or "").strip(),
            monthly_hosting=args.monthly_hosting,
            monthly_analytics=args.monthly_analytics,
            monthly_lead_capture=args.monthly_lead_capture,
            monthly_monitoring=args.monthly_monitoring,
            monthly_contingency=args.monthly_contingency,
            annual_domain_cost=args.annual_domain_cost,
            no_spend=bool(args.no_spend),
        )
        _save_json(config_path, config)

    if args.action in {"render-runtime", "init", "configure"}:
        _render_runtime_config(config, RUNTIME_CONFIG_PATH)

    status_payload: dict[str, Any] | None = None
    preflight_payload: dict[str, Any] | None = None
    estimate_payload: dict[str, Any] | None = None
    deploy_plan_rows: list[str] | None = None

    if args.action in {"preflight"}:
        preflight_payload = _preflight(check_wrangler=bool(args.check_wrangler))
    if args.action in {"status", "init", "configure", "render-runtime"}:
        status_payload = _status(config, check_api=bool(args.check_api), check_wrangler=bool(args.check_wrangler))
    if args.action in {"estimate", "status", "init", "configure", "render-runtime", "deploy-plan", "preflight"}:
        estimate_payload = _estimate(config)
    if args.action in {"deploy-plan", "status", "init", "configure", "render-runtime", "preflight"}:
        deploy_plan_rows = _deploy_plan(config)

    output_override = Path(args.output).expanduser() if args.output else None
    md_path, json_path = _write_outputs(
        action=args.action,
        config_path=config_path,
        config=config,
        status=status_payload,
        preflight=preflight_payload,
        estimate=estimate_payload,
        deploy_plan=deploy_plan_rows,
        output_override=output_override,
    )

    score = _safe_float((status_payload or {}).get("score"), 0.0)
    print(
        f"[ophtxn-production] action={args.action} score={score:g} "
        f"markdown={md_path} json={json_path}"
    )

    if args.strict and status_payload:
        min_score = max(0.0, min(100.0, _safe_float(args.min_score, 80.0)))
        required = {
            "foundation_index_exists",
            "runtime_config_exists",
            "lead_form_present",
            "site_event_tracking_present",
            "revenue_intake_endpoint_present",
            "site_event_endpoint_present",
            "domain_primary_configured",
            "domain_api_configured",
        }
        checks = status_payload.get("checks") if isinstance(status_payload.get("checks"), list) else []
        missing_required = [
            row for row in checks if str(row.get("name") or "") in required and not bool(row.get("ok"))
        ]
        if score < min_score or missing_required:
            print("[ophtxn-production] strict gate failed")
            return 2
    if args.strict and preflight_payload:
        tool_rows = preflight_payload.get("tools") if isinstance(preflight_payload.get("tools"), list) else []
        required = {"curl", "node", "npm", "npx"}
        missing = [
            row for row in tool_rows if str(row.get("name") or "") in required and not bool(row.get("ok"))
        ]
        wrangler = preflight_payload.get("wrangler") if isinstance(preflight_payload.get("wrangler"), dict) else {}
        if missing or (not bool(wrangler.get("wrangler_auth"))):
            print("[ophtxn-production] strict preflight failed")
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
