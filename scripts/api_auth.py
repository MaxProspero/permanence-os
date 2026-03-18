"""
PERMANENCE OS -- API Authentication and Rate Limiting

Provides:
  - API key generation, validation, and revocation
  - Sliding-window rate limiting per key
  - Flask decorator for protected endpoints
  - Local bypass for 127.0.0.1 requests (owner's machine)

Keys are stored in a JSON file under memory/working/api_keys.json.
Rate limit state is in-memory (resets on restart -- acceptable for v1).

Usage in dashboard_api.py:
  from scripts.api_auth import require_api_key, create_api_key

  @app.route("/api/markets/snapshot")
  @require_api_key(tier="free")
  def get_markets_snapshot():
      ...
"""

import hashlib
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = os.environ.get(
    "PERMANENCE_BASE_DIR",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
KEYS_FILE = os.path.join(BASE_DIR, "memory", "working", "api_keys.json")

# Rate limit tiers: requests per minute
RATE_TIERS = {
    "free":       30,
    "starter":    120,
    "pro":        600,
    "unlimited":  999_999,
    "local":      999_999,   # localhost bypass
}

# Sliding window size in seconds
WINDOW_SIZE = 60

# ---------------------------------------------------------------------------
# In-memory rate limit tracking
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_windows: dict[str, list[float]] = {}   # key_id -> list of timestamps


def _prune_window(key_id: str) -> list[float]:
    """Remove timestamps older than WINDOW_SIZE. Must hold _lock."""
    now = time.time()
    cutoff = now - WINDOW_SIZE
    bucket = _windows.get(key_id, [])
    bucket = [t for t in bucket if t > cutoff]
    _windows[key_id] = bucket
    return bucket


# ---------------------------------------------------------------------------
# Key storage
# ---------------------------------------------------------------------------

def _load_keys() -> dict:
    """Load API keys from disk."""
    try:
        with open(KEYS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"keys": {}}


def _save_keys(data: dict) -> None:
    """Persist API keys to disk."""
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    with open(KEYS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of raw key for storage (never store plaintext)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Public API: key management
# ---------------------------------------------------------------------------

def create_api_key(
    owner: str,
    tier: str = "free",
    label: str = "",
) -> dict:
    """
    Generate a new API key.

    Returns dict with:
      - key: the raw key (shown once, never stored)
      - key_id: short identifier for the key
      - tier: rate limit tier
      - owner: who owns it
    """
    raw_key = f"perm_{secrets.token_urlsafe(32)}"
    key_id = raw_key[:12]
    hashed = _hash_key(raw_key)

    data = _load_keys()
    data["keys"][key_id] = {
        "hash": hashed,
        "tier": tier,
        "owner": owner,
        "label": label,
        "created": datetime.now(timezone.utc).isoformat(),
        "revoked": False,
        "requests_total": 0,
    }
    _save_keys(data)

    return {
        "key": raw_key,
        "key_id": key_id,
        "tier": tier,
        "owner": owner,
    }


def revoke_api_key(key_id: str) -> bool:
    """Revoke a key by its ID prefix."""
    data = _load_keys()
    if key_id in data["keys"]:
        data["keys"][key_id]["revoked"] = True
        _save_keys(data)
        return True
    return False


def list_api_keys() -> list[dict]:
    """List all keys (without hashes)."""
    data = _load_keys()
    result = []
    for kid, info in data["keys"].items():
        result.append({
            "key_id": kid,
            "tier": info.get("tier", "free"),
            "owner": info.get("owner", ""),
            "label": info.get("label", ""),
            "created": info.get("created", ""),
            "revoked": info.get("revoked", False),
            "requests_total": info.get("requests_total", 0),
        })
    return result


def validate_key(raw_key: str) -> Optional[dict]:
    """
    Validate a raw API key.

    Returns key info dict if valid, None if invalid/revoked.
    """
    if not raw_key or not raw_key.startswith("perm_"):
        return None
    key_id = raw_key[:12]
    hashed = _hash_key(raw_key)
    data = _load_keys()
    info = data["keys"].get(key_id)
    if not info:
        return None
    if info.get("revoked", False):
        return None
    if info["hash"] != hashed:
        return None
    return {"key_id": key_id, **info}


def increment_usage(key_id: str) -> None:
    """Bump total request count for a key."""
    data = _load_keys()
    if key_id in data["keys"]:
        data["keys"][key_id]["requests_total"] = (
            data["keys"][key_id].get("requests_total", 0) + 1
        )
        _save_keys(data)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def check_rate_limit(key_id: str, tier: str = "free") -> dict:
    """
    Check if a key is within its rate limit.

    Returns:
      {"allowed": bool, "remaining": int, "limit": int, "reset_in": float}
    """
    limit = RATE_TIERS.get(tier, RATE_TIERS["free"])
    with _lock:
        bucket = _prune_window(key_id)
        remaining = max(0, limit - len(bucket))
        # Time until oldest entry expires
        reset_in = 0.0
        if bucket:
            reset_in = max(0.0, WINDOW_SIZE - (time.time() - bucket[0]))
        return {
            "allowed": len(bucket) < limit,
            "remaining": remaining,
            "limit": limit,
            "reset_in": round(reset_in, 1),
        }


def record_request(key_id: str) -> None:
    """Record a request timestamp for rate limiting."""
    with _lock:
        if key_id not in _windows:
            _windows[key_id] = []
        _windows[key_id].append(time.time())


# ---------------------------------------------------------------------------
# Flask decorator
# ---------------------------------------------------------------------------

def require_api_key(tier: str = "free"):
    """
    Flask route decorator that enforces API key auth + rate limiting.

    Local requests (127.0.0.1) bypass auth but still get rate-limited
    under the "local" tier (effectively unlimited).

    Usage:
      @app.route("/api/something")
      @require_api_key(tier="free")
      def my_endpoint():
          ...
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import request as req, jsonify as jfy

            remote = req.remote_addr or ""
            is_local = remote in ("127.0.0.1", "::1", "localhost")

            if is_local:
                # Local bypass -- no key needed, unlimited rate
                record_request("__local__")
                return fn(*args, **kwargs)

            # Extract key from header or query param
            raw_key = req.headers.get("X-API-Key", "") or req.args.get("api_key", "")
            if not raw_key:
                return jfy({
                    "error": "API key required",
                    "hint": "Set X-API-Key header or ?api_key= param",
                }), 401

            info = validate_key(raw_key)
            if not info:
                return jfy({"error": "Invalid or revoked API key"}), 403

            key_id = info["key_id"]
            key_tier = info.get("tier", "free")

            # Check rate limit using key's tier
            rl = check_rate_limit(key_id, key_tier)
            if not rl["allowed"]:
                resp = jfy({
                    "error": "Rate limit exceeded",
                    "limit": rl["limit"],
                    "reset_in": rl["reset_in"],
                })
                resp.status_code = 429
                resp.headers["Retry-After"] = str(int(rl["reset_in"]) + 1)
                resp.headers["X-RateLimit-Limit"] = str(rl["limit"])
                resp.headers["X-RateLimit-Remaining"] = "0"
                return resp

            # Record and proceed
            record_request(key_id)
            increment_usage(key_id)

            # Add rate limit headers to response
            result = fn(*args, **kwargs)
            # If result is a tuple (response, status), handle both
            if isinstance(result, tuple):
                resp_obj = result[0]
                status = result[1] if len(result) > 1 else 200
            else:
                resp_obj = result
                status = None

            try:
                rl_after = check_rate_limit(key_id, key_tier)
                if hasattr(resp_obj, "headers"):
                    resp_obj.headers["X-RateLimit-Limit"] = str(rl_after["limit"])
                    resp_obj.headers["X-RateLimit-Remaining"] = str(rl_after["remaining"])
            except Exception:
                pass

            if status is not None:
                return resp_obj, status
            return resp_obj

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Permanence OS API Key Manager")
    sub = parser.add_subparsers(dest="action")

    create_p = sub.add_parser("create", help="Create a new API key")
    create_p.add_argument("--owner", required=True)
    create_p.add_argument("--tier", default="free", choices=list(RATE_TIERS.keys()))
    create_p.add_argument("--label", default="")

    sub.add_parser("list", help="List all API keys")

    revoke_p = sub.add_parser("revoke", help="Revoke an API key")
    revoke_p.add_argument("--key-id", required=True)

    args = parser.parse_args()

    if args.action == "create":
        result = create_api_key(args.owner, args.tier, args.label)
        print(f"API Key created (save this -- shown once):")
        print(f"  Key:   {result['key']}")
        print(f"  ID:    {result['key_id']}")
        print(f"  Tier:  {result['tier']}")
        print(f"  Owner: {result['owner']}")
    elif args.action == "list":
        keys = list_api_keys()
        if not keys:
            print("No API keys found.")
        for k in keys:
            status = "REVOKED" if k["revoked"] else "active"
            print(f"  [{status}] {k['key_id']}  tier={k['tier']}  owner={k['owner']}  requests={k['requests_total']}")
    elif args.action == "revoke":
        if revoke_api_key(args.key_id):
            print(f"Key {args.key_id} revoked.")
        else:
            print(f"Key {args.key_id} not found.")
    else:
        parser.print_help()
