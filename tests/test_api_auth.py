"""Tests for scripts/api_auth.py -- API key management and rate limiting."""

import json
import os
import sys
import tempfile
import time

import pytest

# Ensure scripts/ is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import api_auth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_keys(tmp_path, monkeypatch):
    """Use a temp keys file and clear rate limit state between tests."""
    keys_file = str(tmp_path / "api_keys.json")
    monkeypatch.setattr(api_auth, "KEYS_FILE", keys_file)
    # Clear in-memory rate windows
    api_auth._windows.clear()
    yield


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

class TestKeyManagement:
    def test_create_key_returns_raw_key(self):
        result = api_auth.create_api_key("test@example.com", "free", "test key")
        assert result["key"].startswith("perm_")
        assert result["key_id"] == result["key"][:12]
        assert result["tier"] == "free"
        assert result["owner"] == "test@example.com"

    def test_created_key_appears_in_list(self):
        api_auth.create_api_key("alice@example.com", "starter")
        keys = api_auth.list_api_keys()
        assert len(keys) == 1
        assert keys[0]["owner"] == "alice@example.com"
        assert keys[0]["tier"] == "starter"
        assert keys[0]["revoked"] is False

    def test_validate_valid_key(self):
        result = api_auth.create_api_key("bob@example.com")
        info = api_auth.validate_key(result["key"])
        assert info is not None
        assert info["key_id"] == result["key_id"]

    def test_validate_invalid_key(self):
        assert api_auth.validate_key("not_a_real_key") is None
        assert api_auth.validate_key("perm_fake12345678") is None
        assert api_auth.validate_key("") is None

    def test_revoke_key(self):
        result = api_auth.create_api_key("carol@example.com")
        assert api_auth.revoke_api_key(result["key_id"]) is True
        # Revoked key should not validate
        assert api_auth.validate_key(result["key"]) is None
        # Should show as revoked in list
        keys = api_auth.list_api_keys()
        assert keys[0]["revoked"] is True

    def test_revoke_nonexistent_key(self):
        assert api_auth.revoke_api_key("nonexistent") is False

    def test_multiple_keys(self):
        api_auth.create_api_key("user1@example.com", "free")
        api_auth.create_api_key("user2@example.com", "starter")
        api_auth.create_api_key("user3@example.com", "pro")
        keys = api_auth.list_api_keys()
        assert len(keys) == 3
        tiers = {k["tier"] for k in keys}
        assert tiers == {"free", "starter", "pro"}

    def test_increment_usage(self):
        result = api_auth.create_api_key("counter@example.com")
        api_auth.increment_usage(result["key_id"])
        api_auth.increment_usage(result["key_id"])
        keys = api_auth.list_api_keys()
        assert keys[0]["requests_total"] == 2

    def test_key_hash_stored_not_plaintext(self):
        result = api_auth.create_api_key("secure@example.com")
        data = api_auth._load_keys()
        stored = data["keys"][result["key_id"]]
        # Hash should not contain the raw key
        assert result["key"] not in json.dumps(stored)
        assert stored["hash"] == api_auth._hash_key(result["key"])


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_under_limit_allowed(self):
        rl = api_auth.check_rate_limit("test_key", "free")
        assert rl["allowed"] is True
        assert rl["remaining"] == 30  # free tier = 30/min

    def test_record_decrements_remaining(self):
        api_auth.record_request("test_key")
        api_auth.record_request("test_key")
        rl = api_auth.check_rate_limit("test_key", "free")
        assert rl["remaining"] == 28

    def test_exceed_limit_blocked(self):
        # Set a very low tier for testing
        original = api_auth.RATE_TIERS.copy()
        api_auth.RATE_TIERS["test_tier"] = 3
        try:
            for _ in range(3):
                api_auth.record_request("limited_key")
            rl = api_auth.check_rate_limit("limited_key", "test_tier")
            assert rl["allowed"] is False
            assert rl["remaining"] == 0
        finally:
            api_auth.RATE_TIERS.update(original)

    def test_different_tiers_different_limits(self):
        rl_free = api_auth.check_rate_limit("k1", "free")
        rl_pro = api_auth.check_rate_limit("k2", "pro")
        assert rl_free["limit"] == 30
        assert rl_pro["limit"] == 600

    def test_unknown_tier_defaults_to_free(self):
        rl = api_auth.check_rate_limit("k", "nonexistent_tier")
        assert rl["limit"] == 30

    def test_window_isolation_between_keys(self):
        api_auth.record_request("key_a")
        api_auth.record_request("key_a")
        rl_a = api_auth.check_rate_limit("key_a", "free")
        rl_b = api_auth.check_rate_limit("key_b", "free")
        assert rl_a["remaining"] == 28
        assert rl_b["remaining"] == 30


# ---------------------------------------------------------------------------
# Flask decorator
# ---------------------------------------------------------------------------

class TestFlaskDecorator:
    @pytest.fixture
    def app(self):
        """Create a minimal Flask app with auth-protected route."""
        try:
            from flask import Flask, jsonify
        except ImportError:
            pytest.skip("Flask not installed")

        test_app = Flask(__name__)
        test_app.config["TESTING"] = True

        @test_app.route("/protected")
        @api_auth.require_api_key(tier="free")
        def protected():
            return jsonify({"status": "ok"})

        return test_app

    def test_local_request_bypasses_auth(self, app):
        with app.test_client() as client:
            resp = client.get("/protected")
            assert resp.status_code == 200

    def test_external_without_key_returns_401(self, app):
        with app.test_client() as client:
            # Simulate external request
            resp = client.get("/protected", environ_base={"REMOTE_ADDR": "203.0.113.1"})
            assert resp.status_code == 401
            data = resp.get_json()
            assert "API key required" in data["error"]

    def test_external_with_invalid_key_returns_403(self, app):
        with app.test_client() as client:
            resp = client.get(
                "/protected",
                headers={"X-API-Key": "perm_invalidkey123"},
                environ_base={"REMOTE_ADDR": "203.0.113.1"},
            )
            assert resp.status_code == 403

    def test_external_with_valid_key_succeeds(self, app):
        result = api_auth.create_api_key("ext@example.com", "free")
        with app.test_client() as client:
            resp = client.get(
                "/protected",
                headers={"X-API-Key": result["key"]},
                environ_base={"REMOTE_ADDR": "203.0.113.1"},
            )
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "ok"

    def test_external_rate_limit_enforced(self, app):
        original = api_auth.RATE_TIERS.copy()
        api_auth.RATE_TIERS["free"] = 2
        try:
            result = api_auth.create_api_key("ratelimited@example.com", "free")
            with app.test_client() as client:
                # First two succeed
                for _ in range(2):
                    resp = client.get(
                        "/protected",
                        headers={"X-API-Key": result["key"]},
                        environ_base={"REMOTE_ADDR": "203.0.113.1"},
                    )
                    assert resp.status_code == 200
                # Third is blocked
                resp = client.get(
                    "/protected",
                    headers={"X-API-Key": result["key"]},
                    environ_base={"REMOTE_ADDR": "203.0.113.1"},
                )
                assert resp.status_code == 429
                assert "Retry-After" in resp.headers
        finally:
            api_auth.RATE_TIERS.update(original)

    def test_query_param_key_works(self, app):
        result = api_auth.create_api_key("qp@example.com", "free")
        with app.test_client() as client:
            resp = client.get(
                f"/protected?api_key={result['key']}",
                environ_base={"REMOTE_ADDR": "203.0.113.1"},
            )
            assert resp.status_code == 200

    def test_revoked_key_rejected(self, app):
        result = api_auth.create_api_key("revoked@example.com", "free")
        api_auth.revoke_api_key(result["key_id"])
        with app.test_client() as client:
            resp = client.get(
                "/protected",
                headers={"X-API-Key": result["key"]},
                environ_base={"REMOTE_ADDR": "203.0.113.1"},
            )
            assert resp.status_code == 403
