"""Stripe subscription checkout helpers (Fix 8 & 9).

Uses the real Stripe SDK (`stripe-python`) — separate from `checkout.py` which
uses the Emergent one-time `CheckoutSession` wrapper for the legacy Starter
flow. All plan / add-on Price IDs are PUBLIC Stripe identifiers (safe to ship
in code), so they live here for clarity instead of in `.env`.
"""
import os
import logging
from datetime import datetime, timezone
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


# ===============================================================
# Builder-Mode metrics — live Stripe MRR / ARR / breakdown
# ===============================================================

# Reverse map: price_id -> plan_key (built from PLAN_PRICE_IDS)
_PRICE_TO_PLAN = {cfg["price_id"]: key for key, cfg in PLAN_PRICE_IDS.items()}
_SEAT_PRICE_TO_PLAN = {cfg["price_id"]: key for key, cfg in SEAT_PRICE_IDS.items()}


def compute_stripe_mrr() -> Dict:
    """Pull every ACTIVE Stripe subscription and aggregate MRR + ARR.

    Pricing logic:
      - Sums actual `unit_amount * quantity` from each subscription item.
      - Monthly intervals stay as-is. Yearly intervals divided by 12.
    """
    _configure()
    plan_counts: Dict[str, int] = {}
    plan_mrr: Dict[str, float] = {}
    seat_counts: Dict[str, int] = {}
    seat_mrr: Dict[str, float] = {}
    active = 0
    total_mrr = 0.0
    seats_total_mrr = 0.0

    starting_after: Optional[str] = None
    while True:
        kwargs = {"status": "active", "limit": 100, "expand": ["data.items.data.price"]}
        if starting_after:
            kwargs["starting_after"] = starting_after
        page = stripe.Subscription.list(**kwargs)
        for sub in page.data:
            active += 1
            for item in sub["items"]["data"]:
                price = item.get("price") or {}
                unit_amount = price.get("unit_amount") or 0
                qty = item.get("quantity") or 1
                interval = (price.get("recurring") or {}).get("interval") or "month"
                price_id = price.get("id") or ""
                monthly_cents = unit_amount * qty
                if interval == "year":
                    monthly_cents = monthly_cents / 12
                elif interval == "week":
                    monthly_cents = monthly_cents * 52 / 12
                elif interval == "day":
                    monthly_cents = monthly_cents * 365 / 12
                monthly_eur = round(monthly_cents / 100.0, 2)

                if price_id in _SEAT_PRICE_TO_PLAN:
                    key = _SEAT_PRICE_TO_PLAN[price_id]
                    seat_counts[key] = seat_counts.get(key, 0) + qty
                    seat_mrr[key] = round(seat_mrr.get(key, 0.0) + monthly_eur, 2)
                    seats_total_mrr += monthly_eur
                else:
                    key = _PRICE_TO_PLAN.get(price_id, "Other")
                    plan_counts[key] = plan_counts.get(key, 0) + 1
                    plan_mrr[key] = round(plan_mrr.get(key, 0.0) + monthly_eur, 2)
                total_mrr += monthly_eur
        if not page.has_more:
            break
        starting_after = page.data[-1].id

    plan_breakdown = []
    for key in list(PLAN_PRICE_IDS.keys()) + ["Other"]:
        if key in plan_counts:
            plan_breakdown.append({
                "plan_key": key,
                "label": PLAN_PRICE_IDS.get(key, {}).get("label", key),
                "count": plan_counts[key],
                "mrr_eur": plan_mrr.get(key, 0.0),
            })

    seat_breakdown = [
        {"plan_key": k, "seats": v, "mrr_eur": seat_mrr.get(k, 0.0)}
        for k, v in seat_counts.items()
    ]

    return {
        "active_subs": active,
        "mrr_eur": round(total_mrr, 2),
        "arr_eur": round(total_mrr * 12, 2),
        "seats_mrr_eur": round(seats_total_mrr, 2),
        "plan_breakdown": plan_breakdown,
        "seat_breakdown": seat_breakdown,
        "currency": "eur",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }



# ===============================================================
# Beta Founding Member program — first 100 founders at €4.99/mo
# Price is created via Stripe API on first use and cached.
# ===============================================================

BETA_CAP = 100
BETA_PRODUCT_NAME = "Zynthoro Beta — Founding Member"
BETA_PRODUCT_DESC = (
    "First 100 founders special pricing. Full Starter plan access. "
    "Price locked for life."
)
BETA_AMOUNT_CENTS = 499  # €4.99
BETA_CURRENCY = "eur"


def ensure_beta_price() -> Dict[str, str]:
    """Idempotently create the Stripe Product + Price for the beta program.

    Looks up an existing product named ``BETA_PRODUCT_NAME`` first. If found,
    reuses its existing monthly recurring EUR price. Otherwise creates both.
    Returns ``{product_id, price_id, amount_eur}``.
    """
    _configure()

    # 1) Try to find an existing product by metadata kind (most reliable across runs).
    product = None
    for p in stripe.Product.search(query="metadata['kind']:'beta_founder'").data:
        product = p
        break

    if product is None:
        product = stripe.Product.create(
            name=BETA_PRODUCT_NAME,
            description=BETA_PRODUCT_DESC,
            metadata={"kind": "beta_founder", "spot_cap": str(BETA_CAP)},
        )
        logger.info("Created Stripe beta product %s", product.id)

    # 2) Find existing recurring monthly EUR price on that product, else create one.
    price = None
    for pr in stripe.Price.list(product=product.id, active=True, limit=100).data:
        rec = (pr.get("recurring") or {})
        if (
            pr.get("unit_amount") == BETA_AMOUNT_CENTS
            and pr.get("currency") == BETA_CURRENCY
            and rec.get("interval") == "month"
        ):
            price = pr
            break

    if price is None:
        price = stripe.Price.create(
            product=product.id,
            unit_amount=BETA_AMOUNT_CENTS,
            currency=BETA_CURRENCY,
            recurring={"interval": "month"},
            metadata={"kind": "beta_founder", "locked_price": "1"},
        )
        logger.info("Created Stripe beta price %s on product %s", price.id, product.id)

    return {
        "product_id": product.id,
        "price_id": price.id,
        "amount_eur": "4.99",
    }


def count_beta_filled() -> int:
    """Count active or trialing subscriptions on the beta price.

    Cancelled / refunded subscriptions are not counted — they free up a spot.
    """
    _configure()
    info = ensure_beta_price()
    price_id = info["price_id"]
    count = 0
    starting_after: Optional[str] = None
    while True:
        kwargs = {"price": price_id, "limit": 100, "status": "all"}
        if starting_after:
            kwargs["starting_after"] = starting_after
        page = stripe.Subscription.list(**kwargs)
        for sub in page.data:
            if sub.status in ("active", "trialing", "past_due", "incomplete"):
                count += 1
        if not page.has_more:
            break
        starting_after = page.data[-1].id
    return count


def beta_status() -> Dict:
    """Public-safe snapshot of the beta program."""
    info = ensure_beta_price()
    filled = count_beta_filled()
    return {
        "price_id": info["price_id"],
        "product_id": info["product_id"],
        "amount_eur": info["amount_eur"],
        "spots_total": BETA_CAP,
        "spots_filled": filled,
        "spots_remaining": max(BETA_CAP - filled, 0),
        "capped": filled >= BETA_CAP,
    }


def create_beta_session(origin_url: str, email: Optional[str] = None) -> Dict:
    """Create a public Stripe Checkout session for the beta program.

    Caller MUST verify the cap is not yet reached before calling.
    """
    info = ensure_beta_price()
    success_url = (
        f"{origin_url.rstrip('/')}/subscribe/beta"
        "?checkout=success&session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = f"{origin_url.rstrip('/')}/subscribe/beta?checkout=cancelled"

    kwargs = {
        "mode": "subscription",
        "line_items": [{"price": info["price_id"], "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "billing_address_collection": "required",
        "allow_promotion_codes": False,
        "metadata": {
            "kind": "beta_founder",
            "amount_eur": info["amount_eur"],
        },
        "subscription_data": {
            "metadata": {
                "kind": "beta_founder",
                "locked_price": "1",
                "tier": "Beta Founding Member",
            },
        },
    }
    if email:
        kwargs["customer_email"] = email

    session = stripe.checkout.Session.create(**kwargs)
    logger.info("Created beta session %s email=%s", session.id, email)
    return {
        "session_id": session.id,
        "url": session.url,
        "amount_eur": info["amount_eur"],
    }
