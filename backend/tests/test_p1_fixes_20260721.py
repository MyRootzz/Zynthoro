"""Regression tests for the 5 P1 fixes shipped 2026-07-21:

  P1-1: `/api/ai/chat` and `/api/ai/stream` refund the AI credit when the
        LLM call fails (previously the credit was charged up-front and
        lost even if no response was delivered).
  P1-2: `_provision_tier_purchase` is atomically idempotent — concurrent
        webhook + self-heal (or Stripe replay) can never double-provision.
  P1-4: Auth cookie is `Secure` by default; `CORS_ORIGINS` no longer
        reflects `*` when `allow_credentials=True`.
  P1-5: `seed_founder` fails-closed if `FOUNDER_PASSWORD` env is unset;
        `seed_jury_demo` fails-closed if `JURY_DEMO_PASSWORD` env is unset.

Run:
    cd /app/backend && python -m pytest tests/test_p1_fixes_20260721.py -v
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
from server import (  # noqa: E402
    db as server_db,
    _consume_ai_credit,
    _refund_ai_credit,
    _provision_tier_purchase,
    seed_founder,
    seed_jury_demo,
)

# Reuse ONE event loop — Motor binds to first loop it sees.
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


# ============================================================================
# P1-1 — Refund AI credit on LLM failure
# ============================================================================
class TestAiCreditRefund:

    def test_refund_decrements_counter(self):
        async def run():
            uid = f"test-p1-refund-{uuid.uuid4()}"
            await server_db.users.insert_one({
                "id": uid, "email": f"{uid}@x", "subscription_plan": "Kickstart 1",
                "ai_credits_limit": 50, "ai_credits_period": "month",
                "ai_credits_used_this_period": 7,
            })
            try:
                user = await server_db.users.find_one({"id": uid})
                await _refund_ai_credit(user)
                fresh = await server_db.users.find_one({"id": uid})
                assert fresh["ai_credits_used_this_period"] == 6
            finally:
                await server_db.users.delete_one({"id": uid})
        _run(run())

    def test_refund_skipped_for_unlimited_users(self):
        async def run():
            uid = f"test-p1-founder-{uuid.uuid4()}"
            await server_db.users.insert_one({
                "id": uid, "email": f"{uid}@x", "is_founder": True, "is_unlimited": True,
                "ai_credits_used_this_period": 0,
            })
            try:
                user = await server_db.users.find_one({"id": uid})
                await _refund_ai_credit(user)  # must not raise or decrement
                fresh = await server_db.users.find_one({"id": uid})
                # Founder counter is never incremented, so refund keeps it at 0
                assert fresh["ai_credits_used_this_period"] == 0
            finally:
                await server_db.users.delete_one({"id": uid})
        _run(run())

    def test_refund_does_not_go_below_zero(self):
        async def run():
            uid = f"test-p1-zero-{uuid.uuid4()}"
            await server_db.users.insert_one({
                "id": uid, "email": f"{uid}@x", "subscription_plan": "Kickstart 1",
                "ai_credits_limit": 50, "ai_credits_period": "month",
                "ai_credits_used_this_period": 0,
            })
            try:
                user = await server_db.users.find_one({"id": uid})
                await _refund_ai_credit(user)
                fresh = await server_db.users.find_one({"id": uid})
                assert fresh["ai_credits_used_this_period"] == 0
            finally:
                await server_db.users.delete_one({"id": uid})
        _run(run())

    def test_consume_then_refund_is_neutral(self):
        async def run():
            uid = f"test-p1-net-{uuid.uuid4()}"
            await server_db.users.insert_one({
                "id": uid, "email": f"{uid}@x", "subscription_plan": "Kickstart 1",
                "ai_credits_limit": 50, "ai_credits_period": "month",
                "ai_credits_used_this_period": 10,
            })
            try:
                user = await server_db.users.find_one({"id": uid})
                await _consume_ai_credit(user)
                mid = await server_db.users.find_one({"id": uid})
                assert mid["ai_credits_used_this_period"] == 11
                await _refund_ai_credit(mid)
                fresh = await server_db.users.find_one({"id": uid})
                assert fresh["ai_credits_used_this_period"] == 10
            finally:
                await server_db.users.delete_one({"id": uid})
        _run(run())


# ============================================================================
# P1-2 — Atomic idempotent provisioning
# ============================================================================
class TestIdempotentProvisioning:

    def test_first_call_provisions_second_call_skips(self):
        async def run():
            uid = f"test-p1-idem-{uuid.uuid4()}"
            session_id = f"cs_test_idem_{uuid.uuid4()}"
            await server_db.users.insert_one({
                "id": uid, "email": f"{uid}@x", "subscription_plan": "Presale",
            })
            await server_db.payment_transactions.insert_one({
                "session_id": session_id, "user_id": uid,
                "provisioned": False,
            })
            try:
                meta = {
                    "user_id": uid, "user_email": "x@x",
                    "tier_key": "kickstart_1", "plan_key": "Kickstart 1",
                    "billing": "lifetime", "kind": "tier_purchase",
                    "amount_eur": "79.00",
                }
                # 1st call: provisions.
                await _provision_tier_purchase(
                    user_id=uid, meta=meta,
                    stripe_subscription=None, stripe_customer=None,
                    event_type="webhook_first", session_id=session_id,
                    amount_total_cents=7900,
                )
                u1 = await server_db.users.find_one({"id": uid})
                assert u1["subscription_plan"] == "Kickstart 1"
                # Bump the credit counter to prove the 2nd call does NOT
                # reset it (that was the CR-4 replay symptom).
                await server_db.users.update_one(
                    {"id": uid}, {"$set": {"ai_credits_used_this_period": 12}}
                )
                # 2nd call: idempotent — must not overwrite, must not reset
                # ai_credits_used_this_period to 0, must not send another email.
                await _provision_tier_purchase(
                    user_id=uid, meta=meta,
                    stripe_subscription=None, stripe_customer=None,
                    event_type="webhook_replay", session_id=session_id,
                    amount_total_cents=7900,
                )
                u2 = await server_db.users.find_one({"id": uid})
                assert u2["ai_credits_used_this_period"] == 12, (
                    "Replay reset credit counter — idempotency broken"
                )
                # Transaction stamped as provisioned once
                txn = await server_db.payment_transactions.find_one(
                    {"session_id": session_id}
                )
                assert txn["provisioned"] is True
                assert txn["provisioning_source"] == "webhook_first"
            finally:
                await server_db.users.delete_one({"id": uid})
                await server_db.payment_transactions.delete_one({"session_id": session_id})
        _run(run())

    def test_blocked_by_amount_does_not_set_provisioned(self):
        async def run():
            uid = f"test-p1-block-{uuid.uuid4()}"
            session_id = f"cs_test_block_{uuid.uuid4()}"
            await server_db.users.insert_one({
                "id": uid, "email": f"{uid}@x", "subscription_plan": "Presale",
            })
            await server_db.payment_transactions.insert_one({
                "session_id": session_id, "user_id": uid, "provisioned": False,
            })
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
                    event_type="webhook_blocked", session_id=session_id,
                    amount_total_cents=0,  # 100%-off — blocked for non-internal
                )
                u = await server_db.users.find_one({"id": uid})
                assert u["subscription_plan"] == "Presale"
                txn = await server_db.payment_transactions.find_one({"session_id": session_id})
                assert txn.get("provisioning_blocked") is True
                # `provisioned` must NOT be True — otherwise a future refund
                # / manual fix couldn't re-run provisioning.
                assert txn.get("provisioned") is not True
            finally:
                await server_db.users.delete_one({"id": uid})
                await server_db.payment_transactions.delete_one({"session_id": session_id})
                await server_db.security_incidents.delete_many({"user_id": uid})
        _run(run())



# ============================================================================
# P1-4 — Cookie Secure + CORS origins pinned
# ============================================================================
class TestCookieAndCors:

    def test_cookie_secure_defaults_to_true(self):
        """The default env has no COOKIE_SECURE key → helper must set Secure."""
        from fastapi import Response
        # Ensure no local override
        if "COOKIE_SECURE" in os.environ:
            del os.environ["COOKIE_SECURE"]
        resp = Response()
        server._set_auth_cookies(resp, "abc.def.ghi")
        raw = resp.headers.get("set-cookie", "")
        assert "Secure" in raw, f"cookie missing Secure flag: {raw}"
        assert "HttpOnly" in raw
        assert "SameSite=lax" in raw

    def test_cookie_secure_can_be_disabled_for_local_dev(self, monkeypatch):
        from fastapi import Response
        monkeypatch.setenv("COOKIE_SECURE", "false")
        resp = Response()
        server._set_auth_cookies(resp, "abc")
        raw = resp.headers.get("set-cookie", "")
        assert "Secure" not in raw

    def test_cors_origins_no_wildcard(self):
        """The CORS middleware must not be initialized with '*' when
        allow_credentials=True — this was SEC-005."""
        cors_mw = None
        for mw in server.app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_mw = mw
                break
        assert cors_mw is not None, "CORSMiddleware not installed"
        origins = cors_mw.kwargs.get("allow_origins", [])
        assert "*" not in origins, f"CORS still allows wildcard: {origins}"
        assert all(o.startswith("http") for o in origins), origins


# ============================================================================
# P1-5 — Seed functions fail closed without env passwords
# ============================================================================
class TestSeedFailClosed:

    def test_seed_founder_skips_when_env_missing(self, monkeypatch, caplog):
        # Preserve DB state — this test does not touch the founder record
        # (the seed helper's "existing" branch never rewrites the password
        # anyway, but with no env password we bail out before that branch).
        monkeypatch.delenv("FOUNDER_PASSWORD", raising=False)
        with caplog.at_level("CRITICAL"):
            _run(seed_founder())
        # Message must mention FOUNDER_PASSWORD
        assert any("FOUNDER_PASSWORD" in rec.message for rec in caplog.records), (
            f"expected CRITICAL log; got {[r.message for r in caplog.records]}"
        )

    def test_seed_founder_skips_when_env_too_short(self, monkeypatch, caplog):
        monkeypatch.setenv("FOUNDER_PASSWORD", "short")
        with caplog.at_level("CRITICAL"):
            _run(seed_founder())
        assert any("FOUNDER_PASSWORD" in rec.message for rec in caplog.records)

    def test_seed_jury_demo_skips_when_env_missing(self, monkeypatch, caplog):
        monkeypatch.delenv("JURY_DEMO_PASSWORD", raising=False)
        with caplog.at_level("WARNING"):
            _run(seed_jury_demo())
        assert any("JURY_DEMO_PASSWORD" in rec.message for rec in caplog.records)
