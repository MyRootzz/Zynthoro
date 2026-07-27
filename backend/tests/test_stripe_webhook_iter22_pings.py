"""Iteration 22: Tests for the THREE NEW webhook_notifier ping triggers
on the Stripe webhook handler:
  (a) Enterprise tier subscription → '💎 New <Tier> subscription!' ping
  (b) invoice.payment_failed → '⚠️ Payment failed' ping (in addition to
      email_service.send_stripe_alert which must still fire)
  (c) Beta cap-hit (100th spot) → '🔒 Beta is SOLD OUT' extra ping next to
      the regular '🎉 New Beta Founding Member' ping

Plus regressions:
  * With beta_webhook_url EMPTY: NONE of the three new pings fire — but the
    email alert flow on payment_failed STILL runs.
  * Existing Starter / subscription_change / seats / cancel / trial_end /
    catch-all paths still work without spurious webhook_notifier calls.

Strategy: in-process direct call of `server_mod.stripe_webhook(req)` with a
fake Request, after monkey-patching:
    * stripe_sdk.Webhook.construct_event   → returns json.loads(body)
    * stripe_sdk.checkout.Session.retrieve → returns synthetic line_items
    * server_mod.email_service.send_stripe_alert → spy AsyncMock
    * sys.modules['webhook_notifier'].send → spy AsyncMock
    * server_mod.subs_mod.beta_status → returns spots_remaining
    * db.feature_flags singleton: temporarily set / clear beta_webhook_url
"""
import asyncio
import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, "/app/backend")

import server as server_mod  # noqa: E402
import stripe_subscriptions as subs_mod  # noqa: E402
import webhook_notifier as wn_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Shared event loop + helpers
# ---------------------------------------------------------------------------
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


class _FakeRequest:
    def __init__(self, body: bytes, sig: str = "sig_test"):
        self._body = body
        self.headers = {"Stripe-Signature": sig}
        self.base_url = "http://testserver/"

    async def body(self):
        return self._body


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def bypass_verify(monkeypatch):
    """Make stripe_sdk.Webhook.construct_event return whatever event we POST.
    Also ensure STRIPE_WEBHOOK_SECRET is set so the handler enters the
    SDK-verify branch."""
    def _fake_construct(body, sig, secret):
        return json.loads(body)
    monkeypatch.setattr(server_mod.stripe_sdk.Webhook, "construct_event", _fake_construct)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_" + "test_dummy")


@pytest.fixture
def stub_session_retrieve(monkeypatch):
    """Patch stripe_sdk.checkout.Session.retrieve so the Beta + Enterprise
    detection can read line_items. Caller sets `holder['items']` before
    invoking the webhook."""
    holder = {"items": []}

    def _fake_retrieve(session_id, expand=None):
        return {"line_items": {"data": holder["items"]}}

    monkeypatch.setattr(server_mod.stripe_sdk.checkout.Session, "retrieve", _fake_retrieve)
    return holder


@pytest.fixture
def spy_alert(monkeypatch):
    """Replace email_service.send_stripe_alert with a spy."""
    calls = []

    async def _spy(**kwargs):
        calls.append(kwargs)
        return "mock_msg_id"

    monkeypatch.setattr(server_mod.email_service, "send_stripe_alert", _spy)
    return calls


@pytest.fixture
def spy_notifier(monkeypatch):
    """Replace webhook_notifier.send with a spy on the *module* object.
    The handler does `import webhook_notifier` inside the function, which
    will resolve to the same module (already in sys.modules)."""
    calls = []

    async def _spy(url, *, title, body, fields):
        calls.append({"url": url, "title": title, "body": body, "fields": fields})
        return True

    monkeypatch.setattr(wn_mod, "send", _spy)
    # In case the handler re-imports — sys.modules entry already points at
    # the same module object, so patching the attribute is sufficient.
    return calls


@pytest.fixture
def set_webhook_url():
    """Set + restore the feature_flags.beta_webhook_url singleton."""
    snapshot = _run(server_mod.db.feature_flags.find_one({"singleton": True})) or {}
    original = snapshot.get("beta_webhook_url", "")

    def _apply(url):
        _run(server_mod.db.feature_flags.update_one(
            {"singleton": True},
            {"$set": {"singleton": True, "beta_webhook_url": url}},
            upsert=True,
        ))

    yield _apply

    _run(server_mod.db.feature_flags.update_one(
        {"singleton": True},
        {"$set": {"singleton": True, "beta_webhook_url": original}},
        upsert=True,
    ))


@pytest.fixture
def stub_beta_status(monkeypatch):
    """Patch subs_mod.beta_status to return whatever we set."""
    holder = {"spots_remaining": 50, "capped": False}

    def _fake():
        return dict(holder)

    monkeypatch.setattr(server_mod.subs_mod, "beta_status", _fake)
    return holder


# ---------------------------------------------------------------------------
# Helpers to build events
# ---------------------------------------------------------------------------
def _sub_session_event(*, customer_email="buyer@example.com", country="DE",
                       mode="subscription", metadata=None, session_id=None):
    return {
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": session_id or f"cs_test_{uuid.uuid4().hex[:8]}",
            "mode": mode,
            "metadata": metadata or {},
            "customer_details": {"email": customer_email,
                                 "address": {"country": country}},
            "customer_email": customer_email,
            "subscription": f"sub_test_{uuid.uuid4().hex[:8]}",
            "customer": f"cus_test_{uuid.uuid4().hex[:8]}",
            "payment_status": "paid",
        }},
    }


def _line_item_for_product(product_id):
    return {"price": {"product": product_id, "id": "price_test"}}


# ===========================================================================
# (a) Enterprise tier ping
# ===========================================================================
class TestEnterprisePing:
    def test_enterprise_basic_fires_diamond_ping(
        self, bypass_verify, stub_session_retrieve, spy_alert,
        spy_notifier, set_webhook_url,
    ):
        set_webhook_url("https://hooks.slack.com/services/T/B/X")
        ent_pid = subs_mod.PLAN_CATALOG["Enterprise Basic"]["product_id"]
        stub_session_retrieve["items"] = [_line_item_for_product(ent_pid)]

        evt = _sub_session_event(customer_email="ceo@bigcorp.com", country="FR")
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.1))

        titles = [c["title"] for c in spy_notifier]
        assert any("Enterprise Basic" in t and "💎" in t for t in titles), \
            f"Expected '💎 New Enterprise Basic subscription!' in {titles}"

        ent_call = next(c for c in spy_notifier if "Enterprise Basic" in c["title"])
        assert ent_call["fields"]["Plan"] == "Enterprise Basic"
        assert ent_call["fields"]["Amount"] == "€2499/mo"
        assert ent_call["fields"]["Country"] == "FR"

    def test_enterprise_plus_fires(self, bypass_verify, stub_session_retrieve,
                                   spy_alert, spy_notifier, set_webhook_url):
        set_webhook_url("https://discord.com/api/webhooks/x/y")
        pid = subs_mod.PLAN_CATALOG["Enterprise Plus"]["product_id"]
        stub_session_retrieve["items"] = [_line_item_for_product(pid)]

        _run(server_mod.stripe_webhook(_FakeRequest(
            json.dumps(_sub_session_event()).encode())))
        _run(asyncio.sleep(0.1))
        assert any("Enterprise Plus" in c["title"] for c in spy_notifier)

    def test_enterprise_advanced_fires(self, bypass_verify, stub_session_retrieve,
                                       spy_alert, spy_notifier, set_webhook_url):
        set_webhook_url("https://hooks.slack.com/services/A/B/C")
        pid = subs_mod.PLAN_CATALOG["Enterprise Advanced"]["product_id"]
        stub_session_retrieve["items"] = [_line_item_for_product(pid)]

        _run(server_mod.stripe_webhook(_FakeRequest(
            json.dumps(_sub_session_event()).encode())))
        _run(asyncio.sleep(0.1))
        ent_calls = [c for c in spy_notifier if "Enterprise Advanced" in c["title"]]
        assert len(ent_calls) == 1
        assert ent_calls[0]["fields"]["Amount"] == "€5999/mo"

    def test_non_enterprise_plan_does_not_fire_ping(
        self, bypass_verify, stub_session_retrieve, spy_alert,
        spy_notifier, set_webhook_url,
    ):
        """A Starter / Creator / Business product MUST NOT trigger the
        '💎' enterprise ping."""
        set_webhook_url("https://hooks.slack.com/services/X/Y/Z")
        pid = subs_mod.PLAN_CATALOG["Creator"]["product_id"]
        stub_session_retrieve["items"] = [_line_item_for_product(pid)]

        _run(server_mod.stripe_webhook(_FakeRequest(
            json.dumps(_sub_session_event()).encode())))
        _run(asyncio.sleep(0.1))
        assert not any("💎" in c["title"] for c in spy_notifier), \
            f"Unexpected enterprise ping for Creator tier: {spy_notifier}"

    def test_enterprise_no_ping_when_webhook_url_empty(
        self, bypass_verify, stub_session_retrieve, spy_alert,
        spy_notifier, set_webhook_url,
    ):
        set_webhook_url("")  # disabled
        pid = subs_mod.PLAN_CATALOG["Enterprise Basic"]["product_id"]
        stub_session_retrieve["items"] = [_line_item_for_product(pid)]

        _run(server_mod.stripe_webhook(_FakeRequest(
            json.dumps(_sub_session_event()).encode())))
        _run(asyncio.sleep(0.1))
        assert len(spy_notifier) == 0


# ===========================================================================
# (b) Payment failed ping
# ===========================================================================
class TestPaymentFailedPing:
    def _evt(self, email="bad@example.com", amount_cents=249900):
        return {
            "type": "invoice.payment_failed",
            "data": {"object": {
                "customer_email": email,
                "amount_due": amount_cents,
                "subscription": "sub_failtest",
                "attempt_count": 3,
                "next_payment_attempt": 1750000000,
            }},
        }

    def test_payment_failed_fires_warning_ping_and_email(
        self, bypass_verify, spy_alert, spy_notifier, set_webhook_url,
    ):
        set_webhook_url("https://hooks.slack.com/services/T/B/X")
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(self._evt()).encode())))
        _run(asyncio.sleep(0.1))

        # webhook_notifier ping
        warns = [c for c in spy_notifier if "⚠️" in c["title"]
                 and "Payment failed" in c["title"]]
        assert len(warns) == 1, f"Expected one ⚠️ ping, got {spy_notifier}"
        f = warns[0]["fields"]
        assert f["Amount"] == "€2499.00"
        assert f["Attempt"] == "3"
        assert f["Next attempt"] == "1750000000"
        assert f["Subscription"] == "sub_failtest"

        # Email alert MUST still fire (no regression)
        assert any(c.get("kind") == "payment_failed" for c in spy_alert), \
            f"email_service.send_stripe_alert NOT called for payment_failed: {spy_alert}"

    def test_payment_failed_no_ping_when_webhook_url_empty(
        self, bypass_verify, spy_alert, spy_notifier, set_webhook_url,
    ):
        set_webhook_url("")
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(self._evt()).encode())))
        _run(asyncio.sleep(0.1))

        assert len(spy_notifier) == 0
        # Email alert MUST still fire — proves regression-safe disable
        assert any(c.get("kind") == "payment_failed" for c in spy_alert)


# ===========================================================================
# (c) Beta SOLD OUT ping (100th spot)
# ===========================================================================
class TestBetaSoldOutPing:
    def test_beta_cap_hit_fires_both_pings(
        self, bypass_verify, stub_session_retrieve, spy_alert,
        spy_notifier, set_webhook_url, stub_beta_status,
    ):
        set_webhook_url("https://hooks.slack.com/services/T/B/X")
        stub_beta_status["spots_remaining"] = 0
        stub_beta_status["capped"] = True
        stub_session_retrieve["items"] = [
            _line_item_for_product(subs_mod.BETA_PRODUCT_ID)
        ]

        evt = _sub_session_event(customer_email="last@founder.com", country="NL")
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.15))

        titles = [c["title"] for c in spy_notifier]
        assert any("🎉" in t and "Beta Founding Member" in t for t in titles), \
            f"Missing 'New Beta Founding Member' in {titles}"
        assert any("🔒" in t and "SOLD OUT" in t for t in titles), \
            f"Missing 'SOLD OUT' in {titles}"

        sold_out = next(c for c in spy_notifier if "SOLD OUT" in c["title"])
        assert sold_out["fields"]["Milestone"] == "100 / 100"

    def test_beta_signup_below_cap_fires_only_one_ping(
        self, bypass_verify, stub_session_retrieve, spy_alert,
        spy_notifier, set_webhook_url, stub_beta_status,
    ):
        set_webhook_url("https://hooks.slack.com/services/T/B/X")
        stub_beta_status["spots_remaining"] = 7  # still room
        stub_session_retrieve["items"] = [
            _line_item_for_product(subs_mod.BETA_PRODUCT_ID)
        ]

        evt = _sub_session_event()
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.15))

        titles = [c["title"] for c in spy_notifier]
        assert any("Beta Founding Member" in t for t in titles)
        assert not any("SOLD OUT" in t for t in titles), \
            f"Unexpected SOLD OUT ping when spots_remaining=7: {titles}"

    def test_beta_no_ping_when_webhook_url_empty(
        self, bypass_verify, stub_session_retrieve, spy_alert,
        spy_notifier, set_webhook_url, stub_beta_status,
    ):
        set_webhook_url("")
        stub_beta_status["spots_remaining"] = 0
        stub_session_retrieve["items"] = [
            _line_item_for_product(subs_mod.BETA_PRODUCT_ID)
        ]

        _run(server_mod.stripe_webhook(_FakeRequest(
            json.dumps(_sub_session_event()).encode())))
        _run(asyncio.sleep(0.15))
        assert len(spy_notifier) == 0


# ===========================================================================
# (d) Regression: other webhook paths still work, no spurious notifier calls
# ===========================================================================
class TestRegressionExistingPaths:
    def test_subscription_change_does_not_fire_notifier_when_no_enterprise(
        self, bypass_verify, stub_session_retrieve, spy_alert,
        spy_notifier, set_webhook_url,
    ):
        set_webhook_url("https://hooks.slack.com/services/T/B/X")
        # Plain Creator change with NO matching line item
        stub_session_retrieve["items"] = []
        user_id = f"TEST_iter22_{uuid.uuid4().hex[:8]}"
        _run(server_mod.db.users.insert_one({
            "id": user_id, "email": f"{user_id}@x.com",
            "subscription_plan": "Presale",
        }))
        try:
            evt = _sub_session_event(metadata={
                "user_id": user_id, "kind": "subscription_change",
                "plan_key": "Creator",
            })
            _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
            _run(asyncio.sleep(0.1))

            # email alert fires (subscribe), but no Slack/Discord ping
            assert any(c["kind"] == "subscribe" for c in spy_alert)
            assert len(spy_notifier) == 0, \
                f"Unexpected notifier calls on plain subscription: {spy_notifier}"
        finally:
            _run(server_mod.db.users.delete_one({"id": user_id}))

    def test_cancel_no_notifier_call(self, bypass_verify, spy_alert,
                                     spy_notifier, set_webhook_url):
        set_webhook_url("https://hooks.slack.com/services/T/B/X")
        evt = {"type": "customer.subscription.deleted",
               "data": {"object": {"id": "sub_iter22_cancel"}}}
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.1))
        assert any(c["kind"] == "cancel" for c in spy_alert)
        assert len(spy_notifier) == 0

    def test_trial_will_end_no_notifier_call(self, bypass_verify, spy_alert,
                                             spy_notifier, set_webhook_url):
        set_webhook_url("https://hooks.slack.com/services/T/B/X")
        evt = {"type": "customer.subscription.trial_will_end",
               "data": {"object": {"customer": "cus_x", "id": "sub_trial_iter22",
                                   "trial_end": 1700000000}}}
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.1))
        assert any(c["kind"] == "trial_end" for c in spy_alert)
        assert len(spy_notifier) == 0

    def test_catchall_event_no_notifier_call(self, bypass_verify, spy_alert,
                                             spy_notifier, set_webhook_url):
        set_webhook_url("https://hooks.slack.com/services/T/B/X")
        evt = {"type": "invoice.paid",
               "data": {"object": {"id": "in_iter22"}}}
        _run(server_mod.stripe_webhook(_FakeRequest(json.dumps(evt).encode())))
        _run(asyncio.sleep(0.1))
        assert any(c["kind"] == "other" for c in spy_alert)
        assert len(spy_notifier) == 0


# ===========================================================================
# (e) Sanity: the iteration_21 founder beta-webhook test endpoint still works
# ===========================================================================
class TestFounderBetaWebhookTestEndpointIntact:
    """Quick smoke: POST /api/founder/beta-webhook/test still 403s w/o auth.
    This is a thin guard that the existing route exists; full coverage in
    /app/backend/tests/test_beta_webhook.py."""

    def test_endpoint_requires_auth(self):
        import requests
        base = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
        if not base:
            try:
                with open("/app/frontend/.env") as fh:
                    for line in fh:
                        if line.startswith("REACT_APP_BACKEND_URL="):
                            base = line.split("=", 1)[1].strip().rstrip("/")
                            break
            except Exception:
                pass
        if not base:
            pytest.skip("REACT_APP_BACKEND_URL not configured")

        r = requests.post(f"{base}/api/founder/beta-webhook/test",
                          json={"url": "https://hooks.slack.com/a/b/c"},
                          timeout=10)
        # 401 or 403 — both prove auth gate is intact
        assert r.status_code in (401, 403, 422), \
            f"unexpected status {r.status_code}: {r.text[:200]}"
