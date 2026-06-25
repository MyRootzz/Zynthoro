"""Stripe subscription checkout helpers (Fix 8 & 9).

Uses the real Stripe SDK (`stripe-python`) — separate from `checkout.py` which
uses the Emergent one-time `CheckoutSession` wrapper for the legacy Starter
flow. All plan / add-on Price IDs are PUBLIC Stripe identifiers (safe to ship
in code), so they live here for clarity instead of in `.env`.
"""
import os
import logging
from typing import Dict, Optional

import stripe

logger = logging.getLogger(__name__)


# Public Stripe Price IDs (recurring subscriptions). Provided by user 2026-02-05.
PLAN_PRICE_IDS: Dict[str, Dict[str, str]] = {
    "Starter":              {"price_id": "price_1TlraS5sy2phCvUr6aZERuEe", "amount_eur": "499",   "label": "Starter"},
    "Creator":              {"price_id": "price_1TlraR5sy2phCvUrGAqE2Dru", "amount_eur": "699",   "label": "Creator"},
    "Business":             {"price_id": "price_1TlraS5sy2phCvUrBrpiSV08", "amount_eur": "899",   "label": "Business"},
    "Agency":               {"price_id": "price_1TlraR5sy2phCvUr2ACgbOuI", "amount_eur": "1199",  "label": "Agency"},
    "Enterprise Basic":     {"price_id": "price_1TlraR5sy2phCvUrCSp2VpB0", "amount_eur": "2499",  "label": "Enterprise Basic"},
    "Enterprise Plus":      {"price_id": "price_1TlraR5sy2phCvUrDKnlJD3n", "amount_eur": "3999",  "label": "Enterprise Plus"},
    "Enterprise Advanced":  {"price_id": "price_1TlraS5sy2phCvUrKkdnPSDO", "amount_eur": "5999",  "label": "Enterprise Advanced"},
}

# Extra-seat add-on Price IDs (recurring, per-seat).
SEAT_PRICE_IDS: Dict[str, Dict[str, str]] = {
    "Business": {"price_id": "price_1Tm6t95sy2phCvUrcwMghidR", "amount_eur": "4.99"},
    "Agency":   {"price_id": "price_1Tm6tx5sy2phCvUraLldzOr2", "amount_eur": "3.99"},
}


def _api_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY not set")
    return key


def _configure() -> None:
    stripe.api_key = _api_key()


def create_subscription_session(
    plan_key: str,
    origin_url: str,
    user_id: str,
    user_email: str,
) -> Dict:
    """Create a Stripe Checkout Session in `subscription` mode for a recurring plan.

    Returns: {session_id, url, plan_key, amount_eur}
    """
    if plan_key not in PLAN_PRICE_IDS:
        raise ValueError(f"Unknown plan_key: {plan_key}")
    _configure()
    cfg = PLAN_PRICE_IDS[plan_key]

    success_url = (
        f"{origin_url.rstrip('/')}/dashboard/settings"
        "?checkout=success&session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = f"{origin_url.rstrip('/')}/dashboard/settings?checkout=cancelled"

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": cfg["price_id"], "quantity": 1}],
        customer_email=user_email,
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=True,
        billing_address_collection="required",
        client_reference_id=user_id,
        metadata={
            "user_id": user_id,
            "user_email": user_email,
            "plan_key": plan_key,
            "amount_eur": cfg["amount_eur"],
            "kind": "subscription_change",
        },
        subscription_data={
            "metadata": {
                "user_id": user_id,
                "plan_key": plan_key,
            },
        },
    )
    logger.info("Created subscription session %s for user=%s plan=%s", session.id, user_id, plan_key)
    return {
        "session_id": session.id,
        "url": session.url,
        "plan_key": plan_key,
        "amount_eur": cfg["amount_eur"],
    }


def create_seats_session(
    current_plan: str,
    quantity: int,
    origin_url: str,
    user_id: str,
    user_email: str,
) -> Dict:
    """Create a Stripe Checkout Session for extra team-seat add-ons.

    Only Business and Agency plans support seat add-ons. Enterprise has unlimited.
    Returns: {session_id, url, quantity, unit_amount_eur, plan_key}
    """
    if quantity < 1 or quantity > 100:
        raise ValueError("Seat quantity must be between 1 and 100.")
    norm = current_plan
    if norm not in SEAT_PRICE_IDS:
        raise ValueError(
            f"Extra-seat add-ons are not available on the {current_plan} plan. "
            "Upgrade to Business (€4.99/seat) or Agency (€3.99/seat) first."
        )
    _configure()
    cfg = SEAT_PRICE_IDS[norm]

    success_url = (
        f"{origin_url.rstrip('/')}/dashboard/team"
        "?checkout=success&session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = f"{origin_url.rstrip('/')}/dashboard/team?checkout=cancelled"

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": cfg["price_id"], "quantity": quantity}],
        customer_email=user_email,
        success_url=success_url,
        cancel_url=cancel_url,
        billing_address_collection="required",
        client_reference_id=user_id,
        metadata={
            "user_id": user_id,
            "user_email": user_email,
            "plan_key": norm,
            "seat_quantity": str(quantity),
            "kind": "seat_addon",
        },
        subscription_data={
            "metadata": {
                "user_id": user_id,
                "seat_quantity": str(quantity),
                "kind": "seat_addon",
            },
        },
    )
    logger.info("Created seats session %s qty=%s for user=%s plan=%s", session.id, quantity, user_id, norm)
    return {
        "session_id": session.id,
        "url": session.url,
        "quantity": quantity,
        "unit_amount_eur": cfg["amount_eur"],
        "plan_key": norm,
    }


def get_session_summary(session_id: str) -> Dict:
    """Fetch a session's high-level outcome — used by the return page poller."""
    _configure()
    s = stripe.checkout.Session.retrieve(session_id)
    return {
        "id": s.id,
        "status": s.status,
        "payment_status": s.payment_status,
        "amount_total": s.amount_total,
        "currency": s.currency,
        "metadata": dict(s.metadata or {}),
        "customer_email": s.customer_email,
        "subscription_id": getattr(s, "subscription", None),
    }


def normalised_plan_label(plan_key: str) -> Optional[str]:
    cfg = PLAN_PRICE_IDS.get(plan_key)
    return cfg["label"] if cfg else None
