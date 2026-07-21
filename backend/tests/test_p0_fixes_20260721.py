"""Regression tests for the 2026-07-21 P0 bug fixes.

  Bug 1: Buying an AI+Social top-up must NOT overwrite a lifetime plan.
  Bug 2: AI+Social Month must expire after 30 days.
  Bug 3: ZYNTHORO-QA promo abuse blocked at provisioning
         (amount_paid < 50% of list → refuse to grant entitlement).

Run:
    cd /app/backend && python -m pytest tests/test_p0_fixes_20260721.py -v
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

import server  # noqa: E402
import tier_catalog  # noqa: E402
from server import db as server_db, _provision_tier_purchase, _consume_ai_credit  # noqa: E402


# Motor's AsyncIOMotorClient binds to the FIRST loop it sees, so we must
# reuse a single event loop across every test (creating a new loop per
# test raises "Event loop is closed" on the 2nd DB call).
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


# ---- Test helpers ---------------------------------------------------------
async def _create_user(**fields) -> str:
    uid = f"test-p0-{uuid.uuid4()}"
    doc = {
        "id": uid,
        "email": f"{uid}@test.zynthoro.ai",
        "subscription_plan": "Presale",
        "is_lifetime": False,
    }
    doc.update(fields)
    await server_db.users.insert_one(doc)
    return uid


async def _cleanup(uid: str) -> None:
    await server_db.users.delete_one({"id": uid})
    await server_db.security_incidents.delete_many({"user_id": uid})


# ============================================================================
# Bug 1 — Top-up must not overwrite a lifetime plan
# ============================================================================
def test_ai_week_topup_preserves_kickstart_3_lifetime():
    async def run():
        uid = await _create_user(
            subscription_plan="Kickstart 3",
            is_lifetime=True,
            billing_model="lifetime",
            ai_credits_limit=300,
            ai_credits_period="month",
            ai_credits_used_this_period=42,
        )
        try:
            meta = {
                "user_id": uid, "user_email": "x@x",
                "tier_key": "ai_social_week", "plan_key": "AI+Social Week",
                "billing": "one_time_week", "kind": "tier_purchase",
                "amount_eur": "24.99",
            }
            await _provision_tier_purchase(
                user_id=uid, meta=meta,
                stripe_subscription=None, stripe_customer="cus_test",
                event_type="test", session_id=f"cs_test_{uuid.uuid4()}",
                amount_total_cents=2499,
            )
            u = await server_db.users.find_one({"id": uid})
            assert u["subscription_plan"] == "Kickstart 3", (
                f"top-up MUST NOT overwrite plan (got {u['subscription_plan']})"
            )
            assert u["is_lifetime"] is True, "top-up must not clear is_lifetime"
            assert u["billing_model"] == "lifetime"
            assert u["ai_credits_limit"] == 30, "week top-up grants 30 credits"
            assert u["ai_credits_period"] == "one_time"
            assert u["ai_credits_period_ends_at"] is not None
            assert u.get("active_top_up", {}).get("tier_key") == "ai_social_week"
        finally:
            await _cleanup(uid)
    _run(run())


def test_ai_month_topup_preserves_kickstart_3_lifetime():
    async def run():
        uid = await _create_user(
            subscription_plan="Kickstart 3", is_lifetime=True,
            billing_model="lifetime", ai_credits_limit=300,
            ai_credits_period="month",
        )
        try:
            meta = {
                "user_id": uid, "user_email": "x@x",
                "tier_key": "ai_social_month", "plan_key": "AI+Social Month",
                "billing": "one_time_month", "kind": "tier_purchase",
                "amount_eur": "59.99",
            }
            await _provision_tier_purchase(
                user_id=uid, meta=meta,
                stripe_subscription=None, stripe_customer="cus_test",
                event_type="test", session_id=f"cs_test_{uuid.uuid4()}",
                amount_total_cents=5999,
            )
            u = await server_db.users.find_one({"id": uid})
            assert u["subscription_plan"] == "Kickstart 3"
            assert u["is_lifetime"] is True
            assert u["ai_credits_limit"] == 150
            # Bug 2: MUST be one_time so expiry is enforced
            assert u["ai_credits_period"] == "one_time"
        finally:
            await _cleanup(uid)
    _run(run())


def test_kickstart_purchase_by_presale_user_still_overwrites():
    """Sanity: a real (non-top-up) plan purchase still applies fully."""
    async def run():
        uid = await _create_user()
        try:
            meta = {
                "user_id": uid, "user_email": "x@x",
                "tier_key": "kickstart_3", "plan_key": "Kickstart 3",
                "billing": "lifetime", "kind": "tier_purchase",
                "amount_eur": "199.00",
            }
            await _provision_tier_purchase(
                user_id=uid, meta=meta,
                stripe_subscription=None, stripe_customer=None,
                event_type="test", session_id=f"cs_test_{uuid.uuid4()}",
                amount_total_cents=19900,
            )
            u = await server_db.users.find_one({"id": uid})
            assert u["subscription_plan"] == "Kickstart 3"
            assert u["is_lifetime"] is True
        finally:
            await _cleanup(uid)
    _run(run())


def test_topup_preserves_compleet_subscription():
    """Buying a top-up on Compleet must not downgrade to top-up module set."""
    async def run():
        uid = await _create_user(
            subscription_plan="Compleet", is_lifetime=False, billing_model="monthly",
            ai_credits_limit=None, ai_credits_period="month",
        )
        try:
            meta = {
                "user_id": uid, "user_email": "x@x",
                "tier_key": "ai_social_week", "plan_key": "AI+Social Week",
                "billing": "one_time_week", "kind": "tier_purchase",
                "amount_eur": "24.99",
            }
            await _provision_tier_purchase(
                user_id=uid, meta=meta,
                stripe_subscription="sub_x", stripe_customer="cus_x",
                event_type="test", session_id=f"cs_test_{uuid.uuid4()}",
                amount_total_cents=2499,
            )
            u = await server_db.users.find_one({"id": uid})
            assert u["subscription_plan"] == "Compleet"
            assert u["billing_model"] == "monthly"
        finally:
            await _cleanup(uid)
    _run(run())


# ============================================================================
# Bug 2 — AI+Social Month must expire after 30 days
# ============================================================================
def test_tier_catalog_month_is_one_time():
    """The root-cause fix: the catalog flags Month as one-time."""
    assert tier_catalog.TIER_FEATURES["AI+Social Month"]["ai_credits_period"] == "one_time"


def test_tier_catalog_week_still_one_time():
    assert tier_catalog.TIER_FEATURES["AI+Social Week"]["ai_credits_period"] == "one_time"


def test_expired_month_topup_raises_402():
    async def run():
        uid = await _create_user()
        try:
            past_ts = datetime.now(timezone.utc).timestamp() - 31 * 86400
            ended_ts = past_ts + 30 * 86400  # ended 1 day ago
            await server_db.users.update_one(
                {"id": uid},
                {"$set": {
                    "ai_credits_limit": 150,
                    "ai_credits_period": "one_time",
                    "ai_credits_used_this_period": 0,
                    "ai_credits_period_started_at": datetime.fromtimestamp(past_ts, tz=timezone.utc).isoformat(),
                    "ai_credits_period_ends_at": datetime.fromtimestamp(ended_ts, tz=timezone.utc).isoformat(),
                }},
            )
            u = await server_db.users.find_one({"id": uid})
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as ei:
                await _consume_ai_credit(u)
            assert ei.value.status_code == 402
            assert "expired" in str(ei.value.detail).lower()
        finally:
            await _cleanup(uid)
    _run(run())


def test_active_month_topup_consumes_credit():
    async def run():
        uid = await _create_user()
        try:
            now = datetime.now(timezone.utc)
            ends = now.timestamp() + 20 * 86400
            await server_db.users.update_one(
                {"id": uid},
                {"$set": {
                    "ai_credits_limit": 150,
                    "ai_credits_period": "one_time",
                    "ai_credits_used_this_period": 5,
                    "ai_credits_period_started_at": now.isoformat(),
                    "ai_credits_period_ends_at": datetime.fromtimestamp(ends, tz=timezone.utc).isoformat(),
                }},
            )
            u = await server_db.users.find_one({"id": uid})
            await _consume_ai_credit(u)  # must not raise
            fresh = await server_db.users.find_one({"id": uid})
            assert fresh["ai_credits_used_this_period"] == 6
        finally:
            await _cleanup(uid)
    _run(run())


# ============================================================================
# Bug 3 — Promo abuse blocked at provisioning + allow_promo default OFF
# ============================================================================
def test_amount_below_50pct_blocks_non_internal_user():
    async def run():
        uid = await _create_user()
        session_id = f"cs_test_{uuid.uuid4()}"
        try:
            meta = {
                "user_id": uid, "user_email": "x@x",
                "tier_key": "kickstart_3", "plan_key": "Kickstart 3",
                "billing": "lifetime", "kind": "tier_purchase",
                "amount_eur": "199.00",
            }
            await _provision_tier_purchase(
                user_id=uid, meta=meta,
                stripe_subscription=None, stripe_customer=None,
                event_type="test", session_id=session_id,
                amount_total_cents=0,  # 100% off
            )
            u = await server_db.users.find_one({"id": uid})
            assert u["subscription_plan"] == "Presale", "must not provision"
            assert not u.get("is_lifetime")
            incident = await server_db.security_incidents.find_one({"session_id": session_id})
            assert incident is not None
            assert incident["type"] == "promo_abuse_blocked"
            assert incident["amount_paid_cents"] == 0
            assert incident["expected_cents"] == 19900
        finally:
            await _cleanup(uid)
    _run(run())


def test_amount_below_50pct_allowed_for_qa_user():
    async def run():
        uid = await _create_user(is_qa_test=True)
        try:
            meta = {
                "user_id": uid, "user_email": "x@x",
                "tier_key": "kickstart_1", "plan_key": "Kickstart 1",
                "billing": "lifetime", "kind": "tier_purchase",
                "amount_eur": "79.00",
            }
            await _provision_tier_purchase(
                user_id=uid, meta=meta,
                stripe_subscription=None, stripe_customer=None,
                event_type="test", session_id=f"cs_test_{uuid.uuid4()}",
                amount_total_cents=0,
            )
            u = await server_db.users.find_one({"id": uid})
            assert u["subscription_plan"] == "Kickstart 1"
            assert u["is_lifetime"] is True
        finally:
            await _cleanup(uid)
    _run(run())


def test_full_payment_provisions_normally():
    async def run():
        uid = await _create_user()
        try:
            meta = {
                "user_id": uid, "user_email": "x@x",
                "tier_key": "kickstart_3", "plan_key": "Kickstart 3",
                "billing": "lifetime", "kind": "tier_purchase",
                "amount_eur": "199.00",
            }
            await _provision_tier_purchase(
                user_id=uid, meta=meta,
                stripe_subscription=None, stripe_customer=None,
                event_type="test", session_id=f"cs_test_{uuid.uuid4()}",
                amount_total_cents=19900,
            )
            u = await server_db.users.find_one({"id": uid})
            assert u["subscription_plan"] == "Kickstart 3"
        finally:
            await _cleanup(uid)
    _run(run())


def test_partial_legitimate_discount_still_allowed():
    """A 30% off legitimate promo still provisions (paid > 50% of list)."""
    async def run():
        uid = await _create_user()
        try:
            meta = {
                "user_id": uid, "user_email": "x@x",
                "tier_key": "kickstart_3", "plan_key": "Kickstart 3",
                "billing": "lifetime", "kind": "tier_purchase",
                "amount_eur": "199.00",
            }
            await _provision_tier_purchase(
                user_id=uid, meta=meta,
                stripe_subscription=None, stripe_customer=None,
                event_type="test", session_id=f"cs_test_{uuid.uuid4()}",
                amount_total_cents=13930,  # 70% of list
            )
            u = await server_db.users.find_one({"id": uid})
            assert u["subscription_plan"] == "Kickstart 3"
        finally:
            await _cleanup(uid)
    _run(run())


def test_founder_full_discount_allowed():
    """Founder can still get 100%-off provisioned (billing_exempt / is_founder)."""
    async def run():
        uid = await _create_user(is_founder=True, billing_exempt=True)
        try:
            meta = {
                "user_id": uid, "user_email": "x@x",
                "tier_key": "kickstart_3", "plan_key": "Kickstart 3",
                "billing": "lifetime", "kind": "tier_purchase",
                "amount_eur": "199.00",
            }
            await _provision_tier_purchase(
                user_id=uid, meta=meta,
                stripe_subscription=None, stripe_customer=None,
                event_type="test", session_id=f"cs_test_{uuid.uuid4()}",
                amount_total_cents=0,
            )
            u = await server_db.users.find_one({"id": uid})
            assert u["subscription_plan"] == "Kickstart 3"
        finally:
            await _cleanup(uid)
    _run(run())


# ---------------------------------------------------------------------------
# Bug 3 (part B) — allow_promo flag is off by default at checkout creation.
# We monkeypatch stripe.checkout.Session.create so no real API call happens.
# ---------------------------------------------------------------------------
def test_checkout_session_disables_promo_by_default(monkeypatch):
    captured = {}
    class _Sess:
        id = "cs_test"; url = "https://stripe/test"
    def fake_create(**kwargs):
        captured.update(kwargs)
        return _Sess()
    import stripe as stripe_sdk
    monkeypatch.setattr(stripe_sdk.checkout.Session, "create", fake_create)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")

    async def go():
        await tier_catalog.create_tier_checkout_session(
            tier_key="kickstart_1", origin_url="https://x",
            user_id="u1", user_email="u@x",
            consent_at=datetime.now(timezone.utc).isoformat(),
            allow_promo=False,
        )
    _run(go())
    assert captured["allow_promotion_codes"] is False
    assert captured["metadata"]["promo_allowed"] == "false"


def test_checkout_session_enables_promo_for_qa(monkeypatch):
    captured = {}
    class _Sess:
        id = "cs_test"; url = "https://stripe/test"
    def fake_create(**kwargs):
        captured.update(kwargs)
        return _Sess()
    import stripe as stripe_sdk
    monkeypatch.setattr(stripe_sdk.checkout.Session, "create", fake_create)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")

    async def go():
        await tier_catalog.create_tier_checkout_session(
            tier_key="kickstart_1", origin_url="https://x",
            user_id="u1", user_email="u@x",
            consent_at=datetime.now(timezone.utc).isoformat(),
            allow_promo=True,
        )
    _run(go())
    assert captured["allow_promotion_codes"] is True
    assert captured["metadata"]["promo_allowed"] == "true"
