"""
PERMANENCE OS -- Stripe Payment Service

Handles subscription management, one-time payments, and webhook processing
for the Permanence OS revenue streams.

Config via environment variables:
  STRIPE_SECRET_KEY       -- sk_test_... or sk_live_...
  STRIPE_WEBHOOK_SECRET   -- whsec_...
  STRIPE_PUBLISHABLE_KEY  -- pk_test_... or pk_live_...

If STRIPE_SECRET_KEY is not set, the service runs in "dry-run" mode
and returns mock responses. This lets development/testing proceed
without a Stripe account.

Plans/Prices:
  - free:     $0/mo   (rate-limited API access)
  - starter:  $49/mo  (standard API access)
  - pro:      $499/mo (priority API + premium features)

Usage in dashboard_api.py:
  from scripts.stripe_service import stripe_bp
  app.register_blueprint(stripe_bp, url_prefix="/api/billing")
"""

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

try:
    from flask import Blueprint, jsonify, request
except ImportError:
    Blueprint = None

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = os.environ.get(
    "PERMANENCE_BASE_DIR",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
BILLING_FILE = os.path.join(BASE_DIR, "memory", "working", "billing_state.json")
BILLING_LOG = os.path.join(BASE_DIR, "logs", "billing.log")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

DRY_RUN = not STRIPE_SECRET_KEY

# Plan definitions
PLANS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "api_tier": "free",
        "features": ["30 req/min", "Market snapshots", "Basic OHLCV"],
    },
    "starter": {
        "name": "Starter",
        "price_monthly": 49,
        "api_tier": "starter",
        "features": ["120 req/min", "All market data", "Webhook alerts", "Email support"],
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 499,
        "api_tier": "pro",
        "features": ["600 req/min", "All market data", "Trading signals", "Priority support", "Custom watchlists"],
    },
}

# ---------------------------------------------------------------------------
# Stripe SDK (optional import)
# ---------------------------------------------------------------------------

stripe = None
if not DRY_RUN:
    try:
        import stripe as _stripe
        _stripe.api_key = STRIPE_SECRET_KEY
        stripe = _stripe
    except ImportError:
        DRY_RUN = True

# ---------------------------------------------------------------------------
# Billing state persistence
# ---------------------------------------------------------------------------

def _load_billing() -> dict:
    """Load billing state from disk."""
    try:
        with open(BILLING_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"customers": {}, "subscriptions": {}}


def _save_billing(data: dict) -> None:
    """Save billing state to disk."""
    os.makedirs(os.path.dirname(BILLING_FILE), exist_ok=True)
    with open(BILLING_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _log_billing(event_type: str, detail: dict) -> None:
    """Append-only billing event log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "detail": detail,
        "dry_run": DRY_RUN,
    }
    os.makedirs(os.path.dirname(BILLING_LOG), exist_ok=True)
    try:
        with open(BILLING_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Customer management
# ---------------------------------------------------------------------------

def create_customer(email: str, name: str = "") -> dict:
    """Create a Stripe customer (or mock in dry-run)."""
    if not DRY_RUN and stripe:
        try:
            customer = stripe.Customer.create(email=email, name=name)
            result = {
                "id": customer.id,
                "email": email,
                "name": name,
                "created": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            _log_billing("customer_create_error", {"email": email, "error": str(exc)})
            raise
    else:
        # Dry-run mock
        cust_id = f"cus_dry_{hashlib.md5(email.encode()).hexdigest()[:12]}"
        result = {
            "id": cust_id,
            "email": email,
            "name": name,
            "created": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
        }

    data = _load_billing()
    data["customers"][result["id"]] = result
    _save_billing(data)
    _log_billing("customer_created", result)
    return result


def create_subscription(customer_id: str, plan: str = "starter") -> dict:
    """Create a subscription for a customer."""
    if plan not in PLANS:
        raise ValueError(f"Unknown plan: {plan}. Available: {list(PLANS.keys())}")

    plan_info = PLANS[plan]

    if not DRY_RUN and stripe:
        try:
            # In production, this would use Stripe Price IDs
            sub = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": f"price_{plan}"}],  # Map to actual Stripe price IDs
            )
            result = {
                "id": sub.id,
                "customer_id": customer_id,
                "plan": plan,
                "status": sub.status,
                "api_tier": plan_info["api_tier"],
                "created": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            _log_billing("subscription_create_error", {
                "customer_id": customer_id,
                "plan": plan,
                "error": str(exc),
            })
            raise
    else:
        sub_id = f"sub_dry_{hashlib.md5(f'{customer_id}_{plan}'.encode()).hexdigest()[:12]}"
        result = {
            "id": sub_id,
            "customer_id": customer_id,
            "plan": plan,
            "status": "active",
            "api_tier": plan_info["api_tier"],
            "created": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
        }

    data = _load_billing()
    data["subscriptions"][result["id"]] = result
    _save_billing(data)
    _log_billing("subscription_created", result)
    return result


def cancel_subscription(subscription_id: str) -> dict:
    """Cancel a subscription."""
    data = _load_billing()
    sub = data["subscriptions"].get(subscription_id)
    if not sub:
        raise ValueError(f"Subscription {subscription_id} not found")

    if not DRY_RUN and stripe:
        try:
            stripe.Subscription.delete(subscription_id)
        except Exception as exc:
            _log_billing("subscription_cancel_error", {
                "subscription_id": subscription_id,
                "error": str(exc),
            })
            raise

    sub["status"] = "canceled"
    sub["canceled_at"] = datetime.now(timezone.utc).isoformat()
    data["subscriptions"][subscription_id] = sub
    _save_billing(data)
    _log_billing("subscription_canceled", {"subscription_id": subscription_id})
    return sub


def get_customer_subscription(customer_id: str) -> Optional[dict]:
    """Get active subscription for a customer."""
    data = _load_billing()
    for sub in data["subscriptions"].values():
        if sub["customer_id"] == customer_id and sub["status"] == "active":
            return sub
    return None


def get_billing_summary() -> dict:
    """Get billing summary stats."""
    data = _load_billing()
    active_subs = [s for s in data["subscriptions"].values() if s["status"] == "active"]
    mrr = sum(PLANS.get(s["plan"], {}).get("price_monthly", 0) for s in active_subs)
    return {
        "total_customers": len(data["customers"]),
        "active_subscriptions": len(active_subs),
        "mrr": mrr,
        "arr": mrr * 12,
        "plan_breakdown": {
            plan: len([s for s in active_subs if s["plan"] == plan])
            for plan in PLANS
        },
        "dry_run": DRY_RUN,
    }


# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------

def verify_webhook_signature(payload: bytes, sig_header: str) -> bool:
    """Verify Stripe webhook signature."""
    if DRY_RUN or not STRIPE_WEBHOOK_SECRET:
        return True  # Skip in dry-run

    if stripe:
        try:
            stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
            return True
        except (ValueError, stripe.error.SignatureVerificationError):
            return False
    return False


def process_webhook_event(event_type: str, event_data: dict) -> dict:
    """Process a Stripe webhook event."""
    _log_billing(f"webhook_{event_type}", event_data)

    handlers = {
        "customer.subscription.created": _handle_sub_created,
        "customer.subscription.updated": _handle_sub_updated,
        "customer.subscription.deleted": _handle_sub_deleted,
        "invoice.paid": _handle_invoice_paid,
        "invoice.payment_failed": _handle_payment_failed,
    }

    handler = handlers.get(event_type)
    if handler:
        return handler(event_data)

    return {"status": "unhandled", "event_type": event_type}


def _handle_sub_created(data: dict) -> dict:
    """Handle new subscription from webhook."""
    _log_billing("webhook_sub_created", data)
    return {"status": "processed", "action": "subscription_created"}


def _handle_sub_updated(data: dict) -> dict:
    """Handle subscription update from webhook."""
    _log_billing("webhook_sub_updated", data)
    return {"status": "processed", "action": "subscription_updated"}


def _handle_sub_deleted(data: dict) -> dict:
    """Handle subscription deletion from webhook."""
    _log_billing("webhook_sub_deleted", data)
    return {"status": "processed", "action": "subscription_deleted"}


def _handle_invoice_paid(data: dict) -> dict:
    """Handle successful payment."""
    _log_billing("webhook_invoice_paid", data)
    return {"status": "processed", "action": "payment_recorded"}


def _handle_payment_failed(data: dict) -> dict:
    """Handle failed payment."""
    _log_billing("webhook_payment_failed", data)
    return {"status": "processed", "action": "payment_failed_recorded"}


# ---------------------------------------------------------------------------
# Flask Blueprint
# ---------------------------------------------------------------------------

if Blueprint:
    stripe_bp = Blueprint("stripe", __name__)

    @stripe_bp.route("/plans", methods=["GET"])
    def get_plans():
        """List available plans."""
        return jsonify({"plans": PLANS, "dry_run": DRY_RUN})

    @stripe_bp.route("/summary", methods=["GET"])
    def billing_summary():
        """Billing dashboard summary."""
        try:
            summary = get_billing_summary()
            return jsonify(summary)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @stripe_bp.route("/customers", methods=["POST"])
    def api_create_customer():
        """Create a new customer."""
        body = request.get_json(silent=True) or {}
        email = body.get("email", "")
        name = body.get("name", "")
        if not email:
            return jsonify({"error": "email is required"}), 400
        try:
            customer = create_customer(email, name)
            return jsonify(customer), 201
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @stripe_bp.route("/subscriptions", methods=["POST"])
    def api_create_subscription():
        """Create a subscription."""
        body = request.get_json(silent=True) or {}
        customer_id = body.get("customer_id", "")
        plan = body.get("plan", "starter")
        if not customer_id:
            return jsonify({"error": "customer_id is required"}), 400
        try:
            sub = create_subscription(customer_id, plan)
            return jsonify(sub), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @stripe_bp.route("/subscriptions/<sub_id>", methods=["DELETE"])
    def api_cancel_subscription(sub_id):
        """Cancel a subscription."""
        try:
            result = cancel_subscription(sub_id)
            return jsonify(result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @stripe_bp.route("/webhook", methods=["POST"])
    def stripe_webhook():
        """Handle Stripe webhooks."""
        payload = request.get_data()
        sig = request.headers.get("Stripe-Signature", "")

        if not verify_webhook_signature(payload, sig):
            return jsonify({"error": "Invalid signature"}), 400

        try:
            event = json.loads(payload)
            event_type = event.get("type", "unknown")
            event_data = event.get("data", {}).get("object", {})
            result = process_webhook_event(event_type, event_data)
            return jsonify(result)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON"}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @stripe_bp.route("/config", methods=["GET"])
    def billing_config():
        """Return publishable key + plan info for frontend."""
        return jsonify({
            "publishable_key": STRIPE_PUBLISHABLE_KEY if not DRY_RUN else "",
            "plans": PLANS,
            "dry_run": DRY_RUN,
        })
else:
    stripe_bp = None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Permanence OS Billing Manager")
    sub = parser.add_subparsers(dest="action")

    sub.add_parser("plans", help="List available plans")
    sub.add_parser("summary", help="Show billing summary")

    cust_p = sub.add_parser("create-customer", help="Create a customer")
    cust_p.add_argument("--email", required=True)
    cust_p.add_argument("--name", default="")

    sub_p = sub.add_parser("subscribe", help="Create subscription")
    sub_p.add_argument("--customer-id", required=True)
    sub_p.add_argument("--plan", default="starter", choices=list(PLANS.keys()))

    args = parser.parse_args()

    if args.action == "plans":
        for pid, info in PLANS.items():
            print(f"  {pid}: ${info['price_monthly']}/mo -- {', '.join(info['features'])}")
    elif args.action == "summary":
        s = get_billing_summary()
        print(f"  Customers: {s['total_customers']}")
        print(f"  Active subs: {s['active_subscriptions']}")
        print(f"  MRR: ${s['mrr']}")
        print(f"  ARR: ${s['arr']}")
        print(f"  Dry-run: {s['dry_run']}")
    elif args.action == "create-customer":
        c = create_customer(args.email, args.name)
        print(f"  Customer created: {c['id']} ({c['email']})")
    elif args.action == "subscribe":
        s = create_subscription(args.customer_id, args.plan)
        print(f"  Subscription created: {s['id']} (plan={s['plan']}, status={s['status']})")
    else:
        parser.print_help()
