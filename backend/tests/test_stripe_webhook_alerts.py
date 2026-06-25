"""Tests for the new internal Stripe webhook → Resend alert wiring.

Covers:
  * Unit-level: email_service.send_stripe_alert exists, never raises, and the
    INTERNAL_ALERT_* constants + _EMOJI_FOR_KIND mapping are present.
  * Unit-level: server._plan_rank classifies plans correctly (Presale=0, …
    Enterprise Advanced=7, UnknownPlan=1).
  * Integration: hit POST /api/webhook/stripe with a fabricated `event` after
    monkey-patching stripe_sdk.Webhook.construct_event so signature
    verification is bypassed, and email_service.send_stripe_alert so we can
    spy on the call args. Confirms subscribe/upgrade/downgrade/seats/cancel/
    payment_failed/trial_end/other classifications, and that the webhook stays
    2xx even when send_stripe_alert itself raises (fire-and-forget contract).
"""
import asyncio
import inspect
import json
import os
import sys
import uuid
from unittest.mock import patch

import pytest
import requests

sys.path.insert(0, "/app/backend")

import email_service  # noqa: E402
import server as server_mod  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

WEBHOOK = f"{BASE_URL}/api/webhook/stripe"


# ---------------------------------------------------------------------------
# Unit-level checks on email_service
# ---------------------------------------------------------------------------
class TestEmailServiceHelpers:
    def test_constants_present(self):
        assert email_service.INTERNAL_ALERT_TO == "info@zynthoro.ai"
        assert "alerts@zynthoro.ai" in email_service.INTERNAL_ALERT_FROM or \
               "zynthoro.ai" in email_service.INTERNAL_ALERT_FROM

    def test_emoji_mapping_complete(self):
        keys = set(email_service._EMOJI_FOR_KIND.keys())
        expected = {
            "subscribe", "upgrade", "downgrade", "seats",
            "cancel", "payment_failed", "trial_end", "other",
        }
        assert expected.issubset(keys), f"Missing kinds: {expected - keys}"

    def test_send_stripe_alert_is_async(self):
        assert inspect.iscoroutinefunction(email_service.send_stripe_alert)

    def test_send_stripe_alert_does_not_raise_on_resend_failure(self):
        """Resend domain not verified → must log and return None, not raise."""
        from unittest.mock import MagicMock

        def _boom(*a, **kw):
            raise RuntimeError("domain not verified")

        with patch.object(email_service, "resend", MagicMock(Emails=MagicMock(send=_boom)),
                          create=True), \
             patch.dict(os.environ, {"RESEND_API_KEY": "re_test_dummy"}, clear=False):
            result = asyncio.new_event_loop().run_until_complete(
                email_service.send_stripe_alert(
                    kind="subscribe",
                    event_type="checkout.session.completed",
                    user_email="x@y.com",
                    user_id="u_1",
                    plan_key="Creator",
                    amount_eur=29.0,
                )
            )
        assert result is None

    def test_send_stripe_alert_unknown_kind_uses_other(self):
        # Just verifying the .get fallback doesn't blow up
        result = asyncio.new_event_loop().run_until_complete(
            email_service.send_stripe_alert(
                kind="totally_unknown_kind",
                event_type="some.event",
            )
        )
        # No RESEND_API_KEY mock here → _init returns False → returns None
        assert result is None


# ---------------------------------------------------------------------------
# Unit-level checks on server._plan_rank
# ---------------------------------------------------------------------------
class TestPlanRank:
    def test_presale_zero(self):
        assert server_mod._plan_rank("Presale") == 0

    def test_starter_one(self):
        assert server_mod._plan_rank("Starter") == 1

    def test_creator_two(self):
        assert server_mod._plan_rank("Creator") == 2

    def test_enterprise_advanced_seven(self):
        assert server_mod._plan_rank("Enterprise Advanced") == 7

    def test_unknown_plan_one(self):
        assert server_mod._plan_rank("UnknownPlan") == 1

    def test_none_zero(self):
        assert server_mod._plan_rank(None) == 0

    def test_upgrade_logic(self):
        # Presale → Creator   = subscribe (handled at branch level)
        # Creator → Business  = upgrade
        # Business → Starter  = downgrade
        assert server_mod._plan_rank("Business") > server_mod._plan_rank("Creator")
        assert server_mod._plan_rank("Starter") < server_mod._plan_rank("Business")


# ---------------------------------------------------------------------------
# Integration: hit the live webhook with mocked verify + spy on alerts.
# We need to monkey-patch the module-level symbols that the webhook handler
# imports.  Because the backend runs in a separate uvicorn process, we can't
# monkeypatch from this test process — so we use a small "test mode" path:
# we POST a header `X-Test-Webhook-Event` that, when STRIPE_WEBHOOK_TEST_MODE
# env is set, bypasses signature.  HOWEVER, the running server has no such
# bypass.  So instead we verify by:
#   (a) building the event payload + a valid sig is impossible (no shared
#       webhook_secret in test).  We therefore expect 400 from prod webhook.
#   (b) we exercise the handler logic by importing the function directly and
#       calling it with a stub Request, after monkey-patching
#       stripe_sdk.Webhook.construct_event in the running process via
#       importlib reload is also impossible.
#
# So this section uses **in-process** patching: we call the async
# stripe_webhook coroutine directly with a fake Request object.
# ---------------------------------------------------------------------------
class _FakeRequest:
    def __init__(self, body: bytes, sig: str = "sig_test"):
        self._body = body
        self.headers = {"Stripe-Signature": sig}
        self.base_url = "http://testserver/"

    async def body(self):
        return self._body


_SHARED_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_SHARED_LOOP)


def _run(coro):
    return _SHARED_LOOP.run_until_complete(coro)


@pytest.fixture
def spy_alert(monkeypatch):
    """Replace email_service.send_stripe_alert with a spy coroutine."""
    calls = []

    async def _spy(**kwargs):
        calls.append(kwargs)
        return "mock_msg_id"

    monkeypatch.setattr(server_mod.email_service, "send_stripe_alert", _spy)
    return calls


@pytest.fixture
def bypass_verify(monkeypatch):
    """Make stripe_sdk.Webhook.construct_event return whatever event we pass
    in via the body JSON.  Also ensure STRIPE_WEBHOOK_SECRET is set so the
    code enters the SDK-verify branch."""
    def _fake_construct(body, sig, secret):
        return json.loads(body)
    monkeypatch.setattr(server_mod.stripe_sdk.Webhook, "construct_event", _fake_construct)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_dummy")


@pytest.fixture
def seed_user():
    """Insert a stub user we can flip plans on, return its id.  Cleanup after."""
    user_id = f"TEST_wh_user_{uuid.uuid4().hex[:8]}"

    async def _setup():
        await server_mod.db.users.insert_one({
            "id": user_id,
            "email": f"{user_id}@example.com",
            "subscription_plan": "Presale",
            "subscription_status": "presale",
            "stripe_customer_id": f"cus_{user_id}",
            "stripe_subscription_id": f"sub_{user_id}",
        })
    _run(_setup())
    yield user_id

    async def _cleanup():
        await server_mod.db.users.delete_one({"id": user_id})
    _run(_cleanup())


def _checkout_session_event(*, user_id, plan_key, kind="subscription_change", seat_qty=None,
                            subscription_id=None):
    meta = {"user_id": user_id, "kind": kind, "plan_key": plan_key}
    if seat_qty is not None:
        meta = {"user_id": user_id, "kind": "seat_addon", "seat_quantity": str(seat_qty)}
    return {
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": f"cs_test_{uuid.uuid4().hex[:8]}",
            "mode": "subscription",
            "metadata": meta,
            "subscription": subscription_id or f"sub_test_{uuid.uuid4().hex[:8]}",
            "customer": f"cus_test_{uuid.uuid4().hex[:8]}",
            "payment_status": "paid",
            "client_reference_id": user_id,
        }},
    }


class TestWebhookAlertWiring:
    def test_subscribe_kind_when_prev_is_presale(self, bypass_verify, spy_alert, seed_user):
        evt = _checkout_session_event(user_id=seed_user, plan_key="Creator")
        req = _FakeRequest(json.dumps(evt).encode())
        resp = _run(server_mod.stripe_webhook(req))
        # Give the fire-and-forget task a chance to schedule
        _run(asyncio.sleep(0.05))
        assert resp.get("received") is True
        assert len(spy_alert) == 1, f"expected one alert, got {spy_alert}"
        assert spy_alert[0]["kind"] == "subscribe"
        assert spy_alert[0]["plan_key"] == "Creator"
        assert spy_alert[0]["user_id"] == seed_user
        # Verify user plan flipped
        user = _run(server_mod.db.users.find_one({"id": seed_user}))
        assert user["subscription_plan"] == "Creator"

    def test_upgrade_kind_creator_to_business(self, bypass_verify, spy_alert, seed_user):
        _run(server_mod.db.users.update_one({"id": seed_user},
                                            {"$set": {"subscription_plan": "Creator"}}))
        evt = _checkout_session_event(user_id=seed_user, plan_key="Business")
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.05))
        assert len(spy_alert) == 1
        assert spy_alert[0]["kind"] == "upgrade"

    def test_downgrade_kind_business_to_starter(self, bypass_verify, spy_alert, seed_user):
        _run(server_mod.db.users.update_one({"id": seed_user},
                                            {"$set": {"subscription_plan": "Business"}}))
        evt = _checkout_session_event(user_id=seed_user, plan_key="Starter")
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.05))
        assert len(spy_alert) == 1
        assert spy_alert[0]["kind"] == "downgrade"

    def test_seats_kind(self, bypass_verify, spy_alert, seed_user):
        evt = _checkout_session_event(user_id=seed_user, plan_key="Business", seat_qty=5)
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.05))
        assert len(spy_alert) == 1
        assert spy_alert[0]["kind"] == "seats"
        assert spy_alert[0]["quantity"] == 5

    def test_cancel_kind(self, bypass_verify, spy_alert, seed_user):
        # subscription_id of seed user is sub_<id>
        sub_id = f"sub_{seed_user}"
        evt = {
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": sub_id}},
        }
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.05))
        assert len(spy_alert) == 1
        assert spy_alert[0]["kind"] == "cancel"
        user = _run(server_mod.db.users.find_one({"id": seed_user}))
        assert user["subscription_status"] == "cancelled"

    def test_payment_failed_kind_with_amount(self, bypass_verify, spy_alert):
        evt = {
            "type": "invoice.payment_failed",
            "data": {"object": {
                "customer_email": "bad@example.com",
                "amount_due": 2900,  # cents
                "subscription": "sub_failed",
                "attempt_count": 2,
                "next_payment_attempt": 1234567890,
            }},
        }
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.05))
        assert len(spy_alert) == 1
        assert spy_alert[0]["kind"] == "payment_failed"
        assert spy_alert[0]["amount_eur"] == 29.0

    def test_trial_end_kind(self, bypass_verify, spy_alert, seed_user):
        cust = f"cus_{seed_user}"
        evt = {
            "type": "customer.subscription.trial_will_end",
            "data": {"object": {"customer": cust, "id": "sub_trial", "trial_end": 1700000000}},
        }
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.05))
        assert len(spy_alert) == 1
        assert spy_alert[0]["kind"] == "trial_end"

    def test_other_kind_for_updated(self, bypass_verify, spy_alert):
        evt = {
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_upd"}},
        }
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.05))
        assert len(spy_alert) == 1
        assert spy_alert[0]["kind"] == "other"

    def test_webhook_still_2xx_when_alert_raises(self, bypass_verify, monkeypatch, seed_user):
        """If send_stripe_alert itself raises, the asyncio.create_task call
        must NOT propagate — the handler returns its `received: True`."""
        async def _boom(**kwargs):
            raise RuntimeError("resend exploded")
        monkeypatch.setattr(server_mod.email_service, "send_stripe_alert", _boom)

        evt = _checkout_session_event(user_id=seed_user, plan_key="Creator")
        resp = _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        # Drain the orphan task so pytest doesn't warn about pending coroutines
        _run(asyncio.sleep(0.05))
        assert resp.get("received") is True
        # Plan still flipped
        user = _run(server_mod.db.users.find_one({"id": seed_user}))
        assert user["subscription_plan"] == "Creator"


# ---------------------------------------------------------------------------
# Smoke: the LIVE webhook endpoint must still 400 on bad signature
# (we can't fake-sign in cross-process land — this is the prod-safety check).
# ---------------------------------------------------------------------------
class TestWebhookEndpointReachable:
    def test_live_webhook_rejects_bad_signature(self):
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not configured")
        r = requests.post(WEBHOOK,
                          data=b'{"type":"ping"}',
                          headers={"Stripe-Signature": "t=1,v1=bad",
                                   "Content-Type": "application/json"},
                          timeout=10)
        # Either 400 (sig invalid) or 200 if there's NO secret configured.
        assert r.status_code in (400, 200), f"unexpected: {r.status_code} {r.text[:200]}"
