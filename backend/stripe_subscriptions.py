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


# =====================================================================
#  Live Stripe catalog (2026-02-26 — new account)
# =====================================================================
# Each plan exposes:
#   - product_id   : Stripe product (stable across price changes)
#   - payment_link : pre-built Stripe Payment Link (https://buy.stripe.com/…)
#                    used by the public pricing page → no backend round-trip
#   - amount_eur   : monthly price in EUR (display only)
#   - label        : human-readable label
#
# For the in-app upgrade/downgrade flow we still create Stripe Checkout
# Sessions server-side. We resolve the *active* recurring price for each
# product lazily via Stripe's API and cache it in memory.
PLAN_CATALOG: Dict[str, Dict[str, str]] = {
    "Starter":             {"product_id": "prod_UlNbqlkAoLv0nK", "payment_link": "https://buy.stripe.com/4gM6oA4YKb7ZgKJard6Ri00", "amount_eur": "499",   "label": "Starter"},
    "Creator":             {"product_id": "prod_UlNjuSTpfiqL4n", "payment_link": "https://buy.stripe.com/8x26oA0Iu4JB9ih7f16Ri02", "amount_eur": "699",   "label": "Creator"},
    "Business":            {"product_id": "prod_UlNlr39JAeUFPr", "payment_link": "https://buy.stripe.com/4gMdR2fDo2Bt2TT56T6Ri03", "amount_eur": "899",   "label": "Business"},
    "Agency":              {"product_id": "prod_UlNmUAq5RfJYsr", "payment_link": "https://buy.stripe.com/bJe7sE4YK4JB0LLard6Ri04", "amount_eur": "1199",  "label": "Agency"},
    "Enterprise Basic":    {"product_id": "prod_UlNmG6bbZQFEqh", "payment_link": "https://buy.stripe.com/8x200c0Iucc39ihdDp6Ri05", "amount_eur": "2499",  "label": "Enterprise Basic"},
    "Enterprise Plus":     {"product_id": "prod_UlNnUYsf9btulz", "payment_link": "https://buy.stripe.com/9B614g3UGcc36652YL6Ri06", "amount_eur": "3999",  "label": "Enterprise Plus"},
    "Enterprise Advanced": {"product_id": "prod_UlO0nF9p11at94", "payment_link": "https://buy.stripe.com/9B63coezk3Fxdyxard6Ri07", "amount_eur": "5999",  "label": "Enterprise Advanced"},
}

# Backwards-compat: a few callers (and tests) still import PLAN_PRICE_IDS.
# Price IDs are resolved lazily — see _price_id_for_product().
PLAN_PRICE_IDS = PLAN_CATALOG  # alias (price_id key populated by _resolve_price_id)

# Extra-seat add-on Price IDs (recurring, per-seat). Pending re-creation on the
# new account — kept for backwards-compat but disabled until refreshed.
SEAT_PRICE_IDS: Dict[str, Dict[str, str]] = {}


# Cache: product_id -> active recurring EUR price_id
_PRICE_CACHE: Dict[str, str] = {}


def _api_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY not set")
    return key


def _configure() -> None:
    stripe.api_key = _api_key()


def _price_id_for_product(product_id: str) -> str:
    """Return the active recurring EUR price_id for a product. Cached."""
    if product_id in _PRICE_CACHE:
        return _PRICE_CACHE[product_id]
    _configure()
    for pr in stripe.Price.list(product=product_id, active=True, limit=100).data:
        if pr.get("recurring") and pr.get("currency") == "eur":
            _PRICE_CACHE[product_id] = pr["id"]
            return pr["id"]
    raise RuntimeError(f"No active recurring EUR price found on product {product_id}")


def create_subscription_session(
    plan_key: str,
    origin_url: str,
    user_id: str,
    user_email: str,
) -> Dict:
    """Create a Stripe Checkout Session in `subscription` mode for a recurring plan.

    Returns: {session_id, url, plan_key, amount_eur}
    """
    if plan_key not in PLAN_CATALOG:
        raise ValueError(f"Unknown plan_key: {plan_key}")
    _configure()
    cfg = PLAN_CATALOG[plan_key]
    price_id = _price_id_for_product(cfg["product_id"])

    success_url = (
        f"{origin_url.rstrip('/')}/dashboard/settings"
        "?checkout=success&session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = f"{origin_url.rstrip('/')}/dashboard/settings?checkout=cancelled"

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
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


def create_seats_session(*_args, **_kwargs) -> Dict:
    """Extra-seat add-ons are temporarily unavailable while we refresh price IDs
    on the new Stripe account (2026-02-26). Re-enable once SEAT_PRICE_IDS is
    populated again.
    """
    raise ValueError(
        "Extra-seat add-ons are temporarily unavailable while billing is being "
        "migrated. Please contact info@zynthoro.ai if you need additional seats."
    )


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
    cfg = PLAN_CATALOG.get(plan_key)
    return cfg["label"] if cfg else None


# ===============================================================
# Builder-Mode metrics — live Stripe MRR / ARR / breakdown
# ===============================================================

# Reverse maps for MRR aggregation. We key on product_id (not price_id) so the
# breakdown survives Stripe price refreshes / multiple prices per product.
_PRODUCT_TO_PLAN = {cfg["product_id"]: key for key, cfg in PLAN_CATALOG.items()}
_SEAT_PRICE_TO_PLAN = {cfg["price_id"]: key for key, cfg in SEAT_PRICE_IDS.items() if "price_id" in cfg}


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
                    product_id = (price.get("product") or "")
                    key = _PRODUCT_TO_PLAN.get(product_id, "Other")
                    plan_counts[key] = plan_counts.get(key, 0) + 1
                    plan_mrr[key] = round(plan_mrr.get(key, 0.0) + monthly_eur, 2)
                total_mrr += monthly_eur
        if not page.has_more:
            break
        starting_after = page.data[-1].id

    plan_breakdown = []
    for key in list(PLAN_CATALOG.keys()) + ["Other"]:
        if key in plan_counts:
            plan_breakdown.append({
                "plan_key": key,
                "label": PLAN_CATALOG.get(key, {}).get("label", key),
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
BETA_PRODUCT_ID = "prod_Um9oZGyOLXCPim"
BETA_PRICE_ID = "price_1TmeCCCLVRJtO07SRJz12MMs"  # €4.99/mo recurring (locked)
BETA_PAYMENT_LINK = "https://buy.stripe.com/4gM00cezkb7Z7a9dDp6Ri08"
BETA_PRODUCT_NAME = "Zynthoro Beta — Founding Member"
BETA_PRODUCT_DESC = (
    "First 100 founders special pricing. Full Starter plan access. "
    "Price locked for life."
)
BETA_AMOUNT_CENTS = 499  # €4.99
BETA_CURRENCY = "eur"


def ensure_beta_price() -> Dict[str, str]:
    """Return the live Stripe Product + Price for the beta program.

    Pins the canonical recurring price ``BETA_PRICE_ID`` (€4.99/mo, locked
    for life) so the count + checkout always target the right one even if
    other prices are attached to the product over time.
    """
    _configure()
    product = stripe.Product.retrieve(BETA_PRODUCT_ID)

    price = None
    try:
        candidate = stripe.Price.retrieve(BETA_PRICE_ID)
        if candidate.get("active") and candidate.get("currency") == BETA_CURRENCY \
                and candidate.get("product") == BETA_PRODUCT_ID:
            price = candidate
    except Exception:
        price = None

    if price is None:
        # Fallback: any active EUR price on the product (legacy / DR safety net).
        for pr in stripe.Price.list(product=product.id, active=True, limit=100).data:
            if pr.get("currency") == BETA_CURRENCY:
                price = pr
                break

    if price is None:
        raise RuntimeError(
            f"No active EUR price found on beta product {BETA_PRODUCT_ID}."
        )

    return {
        "product_id": product.id,
        "price_id": price.id,
        "amount_eur": "4.99",
        "payment_link": BETA_PAYMENT_LINK,
    }


def count_beta_filled() -> int:
    """Count completed Stripe Checkout sessions for the beta product.

    Stripe Payment Links create Checkout Sessions under the hood — we count
    those with ``payment_status == 'paid'`` (one-time) or active subscriptions
    (recurring) referencing the beta price.
    """
    _configure()
    info = ensure_beta_price()
    price_id = info["price_id"]

    # Subscriptions path (only meaningful if the price is recurring)
    sub_count = 0
    try:
        starting_after: Optional[str] = None
        while True:
            kwargs = {"price": price_id, "limit": 100, "status": "all"}
            if starting_after:
                kwargs["starting_after"] = starting_after
            page = stripe.Subscription.list(**kwargs)
            for sub in page.data:
                if sub.status in ("active", "trialing", "past_due", "incomplete"):
                    sub_count += 1
            if not page.has_more:
                break
            starting_after = page.data[-1].id
    except Exception:
        # Stripe will refuse `list(price=X)` if the price isn't recurring.
        sub_count = 0

    if sub_count:
        return sub_count

    # Fallback: count paid Checkout sessions for the beta product.
    paid = 0
    starting_after = None
    while True:
        kwargs = {"limit": 100, "expand": ["data.line_items"]}
        if starting_after:
            kwargs["starting_after"] = starting_after
        page = stripe.checkout.Session.list(**kwargs)
        for s in page.data:
            if s.payment_status != "paid":
                continue
            items = (s.get("line_items") or {}).get("data") or []
            for it in items:
                p = (it.get("price") or {})
                if p.get("product") == BETA_PRODUCT_ID or p.get("id") == price_id:
                    paid += 1
                    break
        if not page.has_more:
            break
        starting_after = page.data[-1].id
    return paid


def beta_status() -> Dict:
    """Public-safe snapshot of the beta program."""
    info = ensure_beta_price()
    filled = count_beta_filled()
    return {
        "price_id": info["price_id"],
        "product_id": info["product_id"],
        "amount_eur": info["amount_eur"],
        "payment_link": info["payment_link"],
        "spots_total": BETA_CAP,
        "spots_filled": filled,
        "spots_remaining": max(BETA_CAP - filled, 0),
        "capped": filled >= BETA_CAP,
    }


def create_beta_session(origin_url: str, email: Optional[str] = None) -> Dict:
    """Return the Stripe Payment Link for the beta program.

    The link is pre-configured in the user's Stripe dashboard (subscription
    semantics, billing address, currency, etc.) so we just forward the visitor.
    """
    info = ensure_beta_price()
    # Pre-fill email + add a return URL so we can detect completion on /subscribe/beta.
    url = info["payment_link"]
    extra = []
    if email:
        extra.append(f"prefilled_email={email}")
    if origin_url:
        success = f"{origin_url.rstrip('/')}/subscribe/beta?checkout=success"
        extra.append(f"checkout%5Bsuccess_url%5D={success}")
    if extra:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}" + "&".join(extra)
    return {
        "session_id": None,
        "url": url,
        "amount_eur": info["amount_eur"],
        "payment_link": info["payment_link"],
    }
