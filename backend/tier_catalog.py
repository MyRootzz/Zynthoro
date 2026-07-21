"""Zynthoro tier catalog — Kickstart lifetime deals, Compleet monthly, and
AI+Social top-ups.

This module is the single source of truth for:
  • Stripe product/price IDs
  • Pricing labels shown on the site
  • AI credit limits per tier (see /api/me and /api/ai/chat)
  • Feature access matrix (which modules a tier unlocks — used for the
    "🔒 Upgrade to unlock" badges on the dashboard)

Two-phase checkout:
  1. Frontend collects the herroepingsrecht (Dutch right-of-withdrawal
     waiver) consent + calls POST /api/checkout/tier/session.
  2. Backend creates a Stripe Checkout Session (mode=payment for lifetime
     & one-time, mode=subscription for Compleet) and records consent
     metadata on payment_transactions.

Provisioning happens in the Stripe webhook (`server.py`).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Literal

import stripe

logger = logging.getLogger(__name__)


# ---- Feature access matrix -------------------------------------------------
# Module keys must match the sidebar routes in /app/frontend/src/App.js
ALL_MODULES = [
    "zyntha", "thoro", "zyona",           # 3 AI assistants
    "planning", "time_tracking",
    "sales", "finance", "accounting",
    "projects", "operations",
    "communication", "compliance",
    "marketing", "canva",
    "team", "settings",
]

# Modules that every tier gets for free (login-required)
BASE_MODULES = ["settings", "team"]

TIER_FEATURES = {
    # Lifetime — Kickstart tiers
    "Kickstart 1": {
        "modules": BASE_MODULES + [
            "zyntha", "thoro", "zyona",
            "planning", "time_tracking",
            "communication", "canva",
        ],
        "workspaces": 1, "seats": 1,
        "ai_credits_limit": 50, "ai_credits_period": "month",
    },
    "Kickstart 2": {
        "modules": BASE_MODULES + [
            "zyntha", "thoro", "zyona",
            "planning", "time_tracking",
            "communication", "canva",
            "finance", "sales", "marketing",
        ],
        "workspaces": 1, "seats": 1,
        "ai_credits_limit": 150, "ai_credits_period": "month",
    },
    "Kickstart 3": {
        "modules": BASE_MODULES + [
            "zyntha", "thoro", "zyona",
            "planning", "time_tracking",
            "communication", "canva",
            "finance", "sales", "marketing",
            "accounting", "operations", "projects",
        ],
        "workspaces": 1, "seats": 2,
        "ai_credits_limit": 300, "ai_credits_period": "month",
    },
    # Monthly self-renewable
    "Compleet": {
        "modules": ALL_MODULES,
        "workspaces": 2, "seats": 1,
        "ai_credits_limit": None,  # unlimited
        "ai_credits_period": "month",
    },
    # AI+Social top-ups — do NOT unlock modules; consumed for AI credits only
    "AI+Social Week": {
        "modules": BASE_MODULES + ["zyntha", "thoro", "zyona", "marketing", "canva"],
        "workspaces": 1, "seats": 1,
        "ai_credits_limit": 30, "ai_credits_period": "one_time",
    },
    "AI+Social Month": {
        "modules": BASE_MODULES + ["zyntha", "thoro", "zyona", "marketing", "canva"],
        "workspaces": 1, "seats": 1,
        # NOTE: period MUST be "one_time" for a one-off top-up so
        # _consume_ai_credit uses the `ai_credits_period_ends_at` expiry
        # branch instead of resetting monthly (which would let a single
        # €59.99 payment refill 150 credits forever). Bugfix 2026-07-21.
        "ai_credits_limit": 150, "ai_credits_period": "one_time",
    },
    # Legacy / full monthly Starter — everything unlocked
    "Starter": {
        "modules": ALL_MODULES,
        "workspaces": 1, "seats": 3,
        "ai_credits_limit": None,
        "ai_credits_period": "month",
    },
    # Presale / no active plan
    "Presale": {
        "modules": BASE_MODULES,
        "workspaces": 1, "seats": 1,
        "ai_credits_limit": 10, "ai_credits_period": "month",
    },
}


# ---- Stripe catalog --------------------------------------------------------
Mode = Literal["payment", "subscription"]


TIER_CATALOG = {
    "kickstart_1": {
        "plan_key": "Kickstart 1",
        "label": "Kickstart 1",
        "amount_eur": 79.00,
        "currency": "eur",
        "billing": "lifetime",  # one-time, no recurring
        "mode": "payment",
        "product_id": "prod_UttjPOJtS5cTns",
        "price_id":   "price_1Tu5wO5sy2phCvUrZSqZNzak",
        "tagline": "40% of Starter · lifetime access",
        "description": "AI Assistants (50 credits/mo), Planning, Time Tracking, Communication, Canva Studio. 1 workspace · 1 user.",
    },
    "kickstart_2": {
        "plan_key": "Kickstart 2",
        "label": "Kickstart 2",
        "amount_eur": 149.00,
        "currency": "eur",
        "billing": "lifetime",
        "mode": "payment",
        "product_id": "prod_Uttr6UVu8Lcgde",
        "price_id":   "price_1Tu6465sy2phCvUrmt77jtlS",
        "tagline": "60% of Starter · lifetime access",
        "description": "Everything in K1 (150 AI credits/mo) + Finance & Invoicing, Sales, AI photo/video suite. 1 workspace · 1 user.",
    },
    "kickstart_3": {
        "plan_key": "Kickstart 3",
        "label": "Kickstart 3",
        "amount_eur": 199.00,
        "currency": "eur",
        "billing": "lifetime",
        "mode": "payment",
        "product_id": "prod_UttshkVDM8nk74",
        "price_id":   "price_1Tu64x5sy2phCvUrwBvmRSuG",
        "tagline": "75% of Starter · lifetime access",
        "description": "Everything in K2 (300 AI credits/mo) + Accounting, Operations, Projects, Marketing. 1 workspace · 2 users.",
    },
    "compleet": {
        "plan_key": "Compleet",
        "label": "Zynthoro Compleet",
        "amount_eur": 79.99,
        "currency": "eur",
        "billing": "monthly",
        "mode": "subscription",
        "product_id": "prod_Uv1y3dZi4VLSlz",
        "price_id":   "price_1TvBuG5sy2phCvUrlbahjtFj",
        "tagline": "Unlimited AI · monthly · cancel anytime",
        "description": "Unlimited AI credits, unlimited social posts, full Planning & Time Tracking, document upload, voice input, extra workspace.",
    },
    "ai_social_week": {
        "plan_key": "AI+Social Week",
        "label": "AI+Social — 1 Week",
        "amount_eur": 24.99,
        "currency": "eur",
        "billing": "one_time_week",
        "mode": "payment",
        "product_id": "prod_Utty09spK6ZzVF",
        "price_id":   "price_1Tu6AT5sy2phCvUrFW68MprM",
        "tagline": "30 AI credits · 7 days",
        "description": "Limited AI credits + social posts top-up. Valid for 1 week. No Tools.",
    },
    "ai_social_month": {
        "plan_key": "AI+Social Month",
        "label": "AI+Social — 1 Month",
        "amount_eur": 59.99,
        "currency": "eur",
        "billing": "one_time_month",
        "mode": "payment",
        "product_id": "prod_UttzlbwkpBggU9",
        "price_id":   "price_1Tu6BR5sy2phCvUrXCaUwBvE",
        "tagline": "150 AI credits · 30 days",
        "description": "Limited AI credits + social posts top-up. Valid for 1 month. No Tools.",
    },
}


def get_tier(tier_key: str) -> dict | None:
    """Return the tier catalog entry, or None if unknown."""
    return TIER_CATALOG.get(tier_key)


# Top-up tiers do NOT unlock modules and MUST NOT overwrite the user's
# existing subscription_plan / is_lifetime. Provisioning is additive-only.
TOP_UP_TIER_KEYS: frozenset[str] = frozenset({"ai_social_week", "ai_social_month"})


def is_top_up(tier_key: str) -> bool:
    """True if the tier is a credit-only top-up (AI+Social Week/Month)."""
    return tier_key in TOP_UP_TIER_KEYS


def _api_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY not set")
    return key


async def create_tier_checkout_session(
    *,
    tier_key: str,
    origin_url: str,
    user_id: str,
    user_email: str,
    consent_at: str,
    allow_promo: bool = False,
) -> dict:
    """Create a Stripe Checkout Session for the chosen tier.

    - lifetime & one-time top-ups → mode=payment
    - Compleet → mode=subscription

    Consent (herroepingsrecht) timestamp is written into the session metadata
    so it survives to the webhook and is stored on the payment_transactions
    row for legal audit.

    `allow_promo` controls whether the Stripe Checkout page offers a "Add
    promotion code" input. This is a SECURITY control — the ZYNTHORO-QA
    100%-off code exists in Stripe for internal QA and must not appear on
    real customer checkouts. Callers should set this True only for
    is_qa_test / staff accounts.
    """
    stripe.api_key = _api_key()

    tier = get_tier(tier_key)
    if not tier:
        raise ValueError(f"Unknown tier: {tier_key}")

    origin_url = origin_url.rstrip("/")
    success_url = f"{origin_url}/subscribe/return?session_id={{CHECKOUT_SESSION_ID}}&tier={tier_key}"
    cancel_url  = f"{origin_url}/subscribe/{tier_key}?cancelled=1"

    metadata = {
        "user_id":         user_id,
        "user_email":      user_email,
        "tier_key":        tier_key,
        "plan_key":        tier["plan_key"],
        "billing":         tier["billing"],
        "kind":            "tier_purchase",
        "consent_waiver":  "true",
        "consent_at":      consent_at,
        "amount_eur":      str(tier["amount_eur"]),
        "promo_allowed":   "true" if allow_promo else "false",
    }

    session_kwargs = dict(
        mode=tier["mode"],
        line_items=[{"price": tier["price_id"], "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=user_id,
        customer_email=user_email,
        metadata=metadata,
        allow_promotion_codes=allow_promo,
    )
    if tier["mode"] == "subscription":
        session_kwargs["subscription_data"] = {"metadata": metadata}
    else:
        session_kwargs["payment_intent_data"] = {"metadata": metadata}

    # Stripe SDK is synchronous — run in a thread with an 8s budget so it
    # cannot wedge the FastAPI event loop or trip Cloudflare's 502 timeout.
    session = await asyncio.wait_for(
        asyncio.to_thread(stripe.checkout.Session.create, **session_kwargs),
        timeout=8.0,
    )
    return {
        "session_id": session.id,
        "url": session.url,
        "amount": tier["amount_eur"],
        "currency": tier["currency"],
        "metadata": metadata,
    }


# ---- Startup validation ----------------------------------------------------
class StripeCatalogValidationError(RuntimeError):
    """Raised on startup when one or more TIER_CATALOG price/product IDs
    are missing or inactive in the connected Stripe account. Refuses to
    let the backend start serving with a stale catalog."""


async def validate_catalog_against_stripe() -> dict:
    """Verify every TIER_CATALOG entry has a live, active price + product
    in the current Stripe account.

    Returns a dict:
        {
            "ok":               bool,
            "checked":          int,     # total tiers checked
            "missing_prices":   [str],
            "missing_products": [str],
            "inactive_prices":  [str],
            "amount_mismatches":[{tier, expected, actual}],
        }

    Network errors (Stripe outage, DNS, etc.) are NOT treated as failures —
    they raise a distinct exception the caller can catch to decide whether
    to boot anyway (safer default) or refuse to boot (paranoid).
    """
    stripe.api_key = _api_key()

    report = {
        "ok": True,
        "checked": len(TIER_CATALOG),
        "missing_prices": [],
        "missing_products": [],
        "inactive_prices": [],
        "amount_mismatches": [],
    }

    def _check_one(tier_key: str, tier: dict) -> None:
        # Product presence
        try:
            prod = stripe.Product.retrieve(tier["product_id"])
            if not prod.get("active"):
                report["inactive_prices"].append(f"{tier_key}:product {tier['product_id']}")
                report["ok"] = False
        except stripe.error.InvalidRequestError:
            report["missing_products"].append(f"{tier_key}:{tier['product_id']}")
            report["ok"] = False
            return  # skip price check if product missing

        # Price presence + amount + active
        try:
            price = stripe.Price.retrieve(tier["price_id"])
            if not price.get("active"):
                report["inactive_prices"].append(f"{tier_key}:{tier['price_id']}")
                report["ok"] = False
            expected_cents = int(round(tier["amount_eur"] * 100))
            actual_cents = price.get("unit_amount") or 0
            if actual_cents != expected_cents:
                report["amount_mismatches"].append({
                    "tier": tier_key,
                    "expected_eur": tier["amount_eur"],
                    "actual_eur": actual_cents / 100,
                })
                report["ok"] = False
        except stripe.error.InvalidRequestError:
            report["missing_prices"].append(f"{tier_key}:{tier['price_id']}")
            report["ok"] = False

    # Run all HTTP calls in a background thread so we don't block the event
    # loop. Each call ~200-400ms; 6 tiers → ~1.5-2.5s wall time serial.
    def _run_all_sync():
        for tier_key, tier in TIER_CATALOG.items():
            _check_one(tier_key, tier)

    await asyncio.wait_for(asyncio.to_thread(_run_all_sync), timeout=20.0)
    return report
