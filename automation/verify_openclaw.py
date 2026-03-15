#!/usr/bin/env python3
"""
Verify OpenClaw provider integration through the governed model registry.

Usage:
    python3 automation/verify_openclaw.py
    python3 automation/verify_openclaw.py --tier haiku --prompt "say OK"
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", default="haiku", choices=["opus", "sonnet", "haiku"])
    parser.add_argument("--prompt", default="Reply with OK and one short sentence confirming OpenClaw is reachable.")
    args = parser.parse_args()

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
        response = model.generate(args.prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"OpenClaw request failed: {exc}", file=sys.stderr)
        return 4

    payload = {
        "ok": True,
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
