#!/usr/bin/env python3
"""
Verify OpenClaw provider integration through the governed model registry.

Usage:
    python3 automation/verify_openclaw.py
    python3 automation/verify_openclaw.py --tier haiku --prompt "say OK"
    python3 automation/verify_openclaw.py --base-url http://localhost:8000/v1 --expect-substring OK
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.registry import registry  # noqa: E402
from models.openclaw import DEFAULT_BASE_URL, OpenClawModel, REQUESTS_AVAILABLE  # noqa: E402


def _mask_secret(secret: str) -> str:
    token = str(secret or "").strip()
    if not token:
        return ""
    if len(token) <= 8:
        return "*" * len(token)
    return token[:4] + "..." + token[-4:]


def _config_snapshot(tier: str) -> dict[str, object]:
    tier_key = OpenClawModel.ENV_BY_TIER.get(tier, "")
    return {
        "tier": tier,
        "base_url": str(os.getenv("PERMANENCE_OPENCLAW_BASE_URL", DEFAULT_BASE_URL)).rstrip("/"),
        "model_env_var": tier_key,
        "resolved_model": str(os.getenv(tier_key, "")).strip() or OpenClawModel.MODELS.get(tier, OpenClawModel.MODELS["sonnet"]),
        "api_key_present": bool(str(os.getenv("OPENCLAW_API_KEY", "")).strip()),
        "api_key_preview": _mask_secret(str(os.getenv("OPENCLAW_API_KEY", "")).strip()),
        "requests_available": REQUESTS_AVAILABLE,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", default="haiku", choices=["opus", "sonnet", "haiku"])
    parser.add_argument("--prompt", default="Reply with OK and one short sentence confirming OpenClaw is reachable.")
    parser.add_argument("--system", default="", help="Optional system prompt override.")
    parser.add_argument("--base-url", default="", help="Override PERMANENCE_OPENCLAW_BASE_URL for this run.")
    parser.add_argument("--model", default="", help="Override the tier model id for this run.")
    parser.add_argument("--expect-substring", default="", help="Fail unless the response text contains this substring.")
    parser.add_argument("--show-config", action="store_true", help="Print resolved OpenClaw config before the request.")
    args = parser.parse_args()

    if args.base_url:
        os.environ["PERMANENCE_OPENCLAW_BASE_URL"] = args.base_url.strip()
    if args.model:
        tier_key = OpenClawModel.ENV_BY_TIER.get(args.tier, "")
        if tier_key:
            os.environ[tier_key] = args.model.strip()

    config = _config_snapshot(args.tier)
    if args.show_config:
        print(json.dumps({"config": config}, indent=2))

    api_key = str(os.getenv("OPENCLAW_API_KEY", "")).strip()
    if not api_key:
        print("OPENCLAW_API_KEY is not set.", file=sys.stderr)
        return 2

    try:
        model = registry.get_by_tier(args.tier, provider="openclaw")
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to load OpenClaw adapter: {exc}", file=sys.stderr)
        return 3

    try:
        response = model.generate(args.prompt, system=(args.system.strip() or None))
    except Exception as exc:  # noqa: BLE001
        print(f"OpenClaw request failed: {exc}", file=sys.stderr)
        return 4

    if args.expect_substring and args.expect_substring not in response.text:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "expected substring missing",
                    "expected_substring": args.expect_substring,
                    "text": response.text,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 5

    payload = {
        "ok": True,
        "config": config,
        "provider": response.metadata.get("provider"),
        "model": response.metadata.get("model"),
        "tier": response.metadata.get("tier"),
        "input_tokens": response.metadata.get("input_tokens"),
        "output_tokens": response.metadata.get("output_tokens"),
        "elapsed_ms": response.metadata.get("elapsed_ms"),
        "text": response.text,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
