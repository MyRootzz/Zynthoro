"""Stripe Checkout helpers for the Zynthoro Starter signup.

The Emergent-managed integration library exposes a one-time CheckoutSession
API. To deliver the "€99/mo for 3 months then €499/mo" promise we charge the
first month immediately at the correct introductory amount, store the founder
pricing window on the user, and rely on a real Stripe Product/Subscription
(configured in the Stripe Dashboard) to handle the recurring schedule once
production keys are set.

For now (test key) we therefore:
  - founder eligible -> one-time €99 charge for month 1 + founder window of 3 months
  - founder NOT eligible -> one-time €499 charge for month 1, standard schedule
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

logger = logging.getLogger(__name__)

PACKAGES: Dict[str, Dict] = {
    # Founder €99 pricing ended 2026-06-30. Only standard €499/mo remains.
    "starter_standard": {
        "amount": 499.00,
        "currency": "eur",
        "label": "Zynthoro Starter — Standard month 1",
        "founder_window_months": 0,
        "next_amount": 499.00,
    },
}


def _api_key() -> str:
    # Prefer STRIPE_SECRET_KEY (live), fall back to STRIPE_API_KEY (legacy/test).
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
    verification_id: str | None,
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
        "founder_window_months": str(pkg["founder_window_months"]),
        "next_amount_eur": str(pkg["next_amount"]),
        "label": pkg["label"],
    }
    if verification_id:
        metadata["verification_id"] = verification_id

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


def founder_pricing_window(months: int) -> dict:
    """Return the founder-pricing schedule that the customer is now on."""
    if months <= 0:
        return {"founder_pricing": False}
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=30 * months)
    return {
        "founder_pricing": True,
        "founder_pricing_months": months,
        "founder_pricing_start": start.isoformat(),
        "founder_pricing_end": end.isoformat(),
    }
