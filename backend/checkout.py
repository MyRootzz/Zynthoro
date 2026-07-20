"""Stripe Checkout helpers for the Zynthoro Starter signup.

Only the standard €499/mo Starter package remains (Founder €99 was sunset 2026-06-30).
"""
import os
import logging
from typing import Dict

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

logger = logging.getLogger(__name__)

PACKAGES: Dict[str, Dict] = {
    "starter_standard": {
        "amount": 499.00,
        "currency": "eur",
        "label": "Zynthoro Starter — Standard month 1",
    },
}


def _api_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY not set")
    return key


def stripe_mode() -> str:
    """Return 'live' | 'test' | 'unknown' based on key prefix."""
    key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY") or ""
    if key.startswith(("sk_live_", "rk_live_")):
        return "live"
    if key.startswith(("sk_test_", "rk_test_", "sk_test_emergent")) or key == "sk_test_emergent":
        return "test"
    return "unknown"


def _client(host_url: str) -> StripeCheckout:
    webhook_url = f"{host_url.rstrip('/')}/api/webhook/stripe"
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    return StripeCheckout(
        api_key=_api_key(),
        webhook_secret=webhook_secret,
        webhook_url=webhook_url,
    )


async def create_subscription_checkout(
    package_id: str,
    host_url: str,
    origin_url: str,
    user_id: str,
    user_email: str,
    verification_id: str | None = None,
) -> dict:
    """Create a one-time Stripe Checkout session for the chosen package."""
    if package_id not in PACKAGES:
        raise ValueError(f"Unknown package: {package_id}")

    pkg = PACKAGES[package_id]
    success_url = (
        f"{origin_url.rstrip('/')}/subscribe/starter/return"
        "?session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = f"{origin_url.rstrip('/')}/subscribe/starter?cancelled=1"

    metadata = {
        "user_id": user_id,
        "user_email": user_email,
        "package_id": package_id,
        "plan": "Starter",
        "label": pkg["label"],
    }

    client = _client(host_url)
    request = CheckoutSessionRequest(
        amount=pkg["amount"],
        currency=pkg["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session = await client.create_checkout_session(request)
    return {
        "session_id": session.session_id,
        "url": session.url,
        "amount": pkg["amount"],
        "currency": pkg["currency"],
        "metadata": metadata,
    }


async def get_session_status(host_url: str, session_id: str) -> dict:
    client = _client(host_url)
    status = await client.get_checkout_status(session_id)
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
        "metadata": status.metadata,
    }
