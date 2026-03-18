"""Tests for scripts/stripe_service.py -- Billing and Stripe integration."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import stripe_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_billing(tmp_path, monkeypatch):
    """Use temp billing files and ensure dry-run mode."""
    monkeypatch.setattr(stripe_service, "BILLING_FILE", str(tmp_path / "billing.json"))
    monkeypatch.setattr(stripe_service, "BILLING_LOG", str(tmp_path / "billing.log"))
    monkeypatch.setattr(stripe_service, "DRY_RUN", True)
    monkeypatch.setattr(stripe_service, "stripe", None)
    yield


# ---------------------------------------------------------------------------
# Customer management
# ---------------------------------------------------------------------------

class TestCustomerManagement:
    def test_create_customer_dry_run(self):
        c = stripe_service.create_customer("test@example.com", "Test User")
        assert c["email"] == "test@example.com"
        assert c["name"] == "Test User"
        assert c["id"].startswith("cus_dry_")
        assert c["dry_run"] is True

    def test_create_customer_persisted(self):
        stripe_service.create_customer("persist@example.com")
        data = stripe_service._load_billing()
        assert len(data["customers"]) == 1

    def test_multiple_customers(self):
        stripe_service.create_customer("a@example.com")
        stripe_service.create_customer("b@example.com")
        data = stripe_service._load_billing()
        assert len(data["customers"]) == 2


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------

class TestSubscriptionManagement:
    def test_create_subscription_dry_run(self):
        c = stripe_service.create_customer("sub@example.com")
        s = stripe_service.create_subscription(c["id"], "starter")
        assert s["plan"] == "starter"
        assert s["status"] == "active"
        assert s["api_tier"] == "starter"
        assert s["customer_id"] == c["id"]
        assert s["id"].startswith("sub_dry_")

    def test_invalid_plan_raises(self):
        c = stripe_service.create_customer("bad@example.com")
        with pytest.raises(ValueError, match="Unknown plan"):
            stripe_service.create_subscription(c["id"], "nonexistent")

    def test_cancel_subscription(self):
        c = stripe_service.create_customer("cancel@example.com")
        s = stripe_service.create_subscription(c["id"], "pro")
        result = stripe_service.cancel_subscription(s["id"])
        assert result["status"] == "canceled"
        assert "canceled_at" in result

    def test_cancel_nonexistent_raises(self):
        with pytest.raises(ValueError, match="not found"):
            stripe_service.cancel_subscription("sub_fake_123")

    def test_get_customer_subscription(self):
        c = stripe_service.create_customer("active@example.com")
        stripe_service.create_subscription(c["id"], "starter")
        sub = stripe_service.get_customer_subscription(c["id"])
        assert sub is not None
        assert sub["plan"] == "starter"

    def test_get_customer_subscription_none_after_cancel(self):
        c = stripe_service.create_customer("gone@example.com")
        s = stripe_service.create_subscription(c["id"], "starter")
        stripe_service.cancel_subscription(s["id"])
        sub = stripe_service.get_customer_subscription(c["id"])
        assert sub is None


# ---------------------------------------------------------------------------
# Billing summary
# ---------------------------------------------------------------------------

class TestBillingSummary:
    def test_empty_summary(self):
        s = stripe_service.get_billing_summary()
        assert s["total_customers"] == 0
        assert s["active_subscriptions"] == 0
        assert s["mrr"] == 0
        assert s["arr"] == 0

    def test_summary_with_subscriptions(self):
        c1 = stripe_service.create_customer("s1@example.com")
        c2 = stripe_service.create_customer("s2@example.com")
        stripe_service.create_subscription(c1["id"], "starter")
        stripe_service.create_subscription(c2["id"], "pro")
        s = stripe_service.get_billing_summary()
        assert s["total_customers"] == 2
        assert s["active_subscriptions"] == 2
        assert s["mrr"] == 49 + 499  # starter + pro
        assert s["arr"] == (49 + 499) * 12

    def test_canceled_sub_not_in_mrr(self):
        c = stripe_service.create_customer("mrr@example.com")
        sub = stripe_service.create_subscription(c["id"], "pro")
        stripe_service.cancel_subscription(sub["id"])
        s = stripe_service.get_billing_summary()
        assert s["mrr"] == 0


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

class TestPlans:
    def test_plans_structure(self):
        for plan_id, info in stripe_service.PLANS.items():
            assert "name" in info
            assert "price_monthly" in info
            assert "api_tier" in info
            assert "features" in info
            assert isinstance(info["features"], list)

    def test_plan_tiers_match_auth_tiers(self):
        """Plan api_tier values should correspond to valid rate limit tiers."""
        import api_auth
        for plan_id, info in stripe_service.PLANS.items():
            assert info["api_tier"] in api_auth.RATE_TIERS, (
                f"Plan {plan_id} tier '{info['api_tier']}' not in RATE_TIERS"
            )


# ---------------------------------------------------------------------------
# Webhook processing
# ---------------------------------------------------------------------------

class TestWebhooks:
    def test_verify_signature_dry_run(self):
        # Dry-run always passes
        assert stripe_service.verify_webhook_signature(b"payload", "sig") is True

    def test_process_known_event(self):
        result = stripe_service.process_webhook_event(
            "invoice.paid", {"invoice_id": "inv_123"}
        )
        assert result["status"] == "processed"

    def test_process_unknown_event(self):
        result = stripe_service.process_webhook_event(
            "unknown.event", {"foo": "bar"}
        )
        assert result["status"] == "unhandled"


# ---------------------------------------------------------------------------
# Billing log
# ---------------------------------------------------------------------------

class TestBillingLog:
    def test_operations_create_log_entries(self, tmp_path):
        stripe_service.create_customer("log@example.com")
        log_file = str(tmp_path / "billing.log")
        assert os.path.exists(log_file)
        with open(log_file) as f:
            lines = f.readlines()
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["event"] == "customer_created"
        assert entry["dry_run"] is True


# ---------------------------------------------------------------------------
# Flask blueprint
# ---------------------------------------------------------------------------

class TestFlaskBlueprint:
    @pytest.fixture
    def app(self):
        try:
            from flask import Flask
        except ImportError:
            pytest.skip("Flask not installed")
        test_app = Flask(__name__)
        test_app.config["TESTING"] = True
        if stripe_service.stripe_bp:
            test_app.register_blueprint(stripe_service.stripe_bp, url_prefix="/api/billing")
        else:
            pytest.skip("stripe_bp not available")
        return test_app

    def test_get_plans(self, app):
        with app.test_client() as client:
            resp = client.get("/api/billing/plans")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "plans" in data
            assert "free" in data["plans"]

    def test_billing_summary_endpoint(self, app):
        with app.test_client() as client:
            resp = client.get("/api/billing/summary")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "mrr" in data

    def test_create_customer_endpoint(self, app):
        with app.test_client() as client:
            resp = client.post(
                "/api/billing/customers",
                json={"email": "api@example.com", "name": "API User"},
            )
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["email"] == "api@example.com"

    def test_create_customer_no_email_400(self, app):
        with app.test_client() as client:
            resp = client.post("/api/billing/customers", json={})
            assert resp.status_code == 400

    def test_create_subscription_endpoint(self, app):
        with app.test_client() as client:
            # Create customer first
            resp = client.post(
                "/api/billing/customers",
                json={"email": "sub_api@example.com"},
            )
            cust_id = resp.get_json()["id"]
            # Create subscription
            resp = client.post(
                "/api/billing/subscriptions",
                json={"customer_id": cust_id, "plan": "starter"},
            )
            assert resp.status_code == 201
            assert resp.get_json()["plan"] == "starter"

    def test_cancel_subscription_endpoint(self, app):
        with app.test_client() as client:
            resp = client.post(
                "/api/billing/customers",
                json={"email": "cancel_api@example.com"},
            )
            cust_id = resp.get_json()["id"]
            resp = client.post(
                "/api/billing/subscriptions",
                json={"customer_id": cust_id, "plan": "pro"},
            )
            sub_id = resp.get_json()["id"]
            resp = client.delete(f"/api/billing/subscriptions/{sub_id}")
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "canceled"

    def test_billing_config_endpoint(self, app):
        with app.test_client() as client:
            resp = client.get("/api/billing/config")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["dry_run"] is True
            assert "plans" in data
