"""
Iteration 25 — direct tests for the `_provision_tier_purchase` helper in
server.py plus regression tests for the checkout status self-heal path.

Rationale
---------
Production hit a bug where Stripe one-time-payment sessions (Kickstart
1/2/3, AI+Social Week/Month) were IGNORED by the webhook (which only
looked at mode='subscription'). The fix widened the webhook branch and
extracted provisioning into `_provision_tier_purchase`, plus added a
self-heal path in GET /api/checkout/tier/status/{session_id}.

Stripe is in LIVE mode — we CANNOT complete a real checkout in a test.
Instead we invoke `_provision_tier_purchase` directly with a mock meta
dict, then verify the user record in mongo reflects the new tier. Each
test resets the QA user back to Presale afterwards.
"""
from __future__ import annotations

import os
import asyncio
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

# Import after load_dotenv so server picks up MONGO_URL/DB_NAME correctly.
import server  # noqa: E402
from server import _provision_tier_purchase, db as server_db  # noqa: E402

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

# (email, password, tier_key, plan_key, expected_credits, expected_billing,
#  expected_is_lifetime, expected_period_days_or_None)
TIER_MATRIX = [
    ("qa-kickstart1@zynthoro.io", "QaKick1!Test", "kickstart_1",
     "Kickstart 1", 50, "lifetime", True, None),
    ("qa-kickstart2@zynthoro.io", "QaKick2!Test", "kickstart_2",
     "Kickstart 2", 150, "lifetime", True, None),
    ("qa-kickstart3@zynthoro.io", "QaKick3!Test", "kickstart_3",
     "Kickstart 3", 300, "lifetime", True, None),
    ("qa-compleet@zynthoro.io", "QaComp!Test", "compleet",
     "Compleet", None, "monthly", False, None),
    ("qa-aiweek@zynthoro.io", "QaWeek!Test", "ai_social_week",
     "AI+Social Week", 30, "one_time_week", False, 7),
    ("qa-aimonth@zynthoro.io", "QaMonth!Test", "ai_social_month",
     "AI+Social Month", 150, "one_time_month", False, 30),
]


# --------------------------------------------------------------------- helpers
def _run(coro):
    """Run an async coroutine on the shared event loop.

    Motor's AsyncIOMotorClient (used inside server.py) binds to the loop
    of the FIRST call, so we must reuse a single loop for every await
    against `server_db`. Creating a new loop per call raises
    "Event loop is closed" the second time.
    """
    return _LOOP.run_until_complete(coro)


_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _login(email: str, password: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("stage") == "ok", data
    return data


async def _reset_user_to_presale(user_id: str) -> None:
    await server_db.users.update_one(
        {"id": user_id},
        {"$set": {
            "subscription_plan": "Presale",
            "subscription_status": "presale",
            "is_lifetime": False,
            "billing_model": None,
            "ai_credits_limit": 10,
            "ai_credits_period": "month",
            "ai_credits_used_this_period": 0,
            "ai_credits_period_ends_at": None,
        },
         "$unset": {
            "stripe_subscription_id": "",
            "stripe_customer_id": "",
        }},
    )


async def _get_user(user_id: str) -> dict:
    return await server_db.users.find_one({"id": user_id}, {"_id": 0})


# ------------------------------------------------------- main provisioning matrix
@pytest.mark.parametrize(
    "email,password,tier_key,plan_key,exp_credits,exp_billing,exp_lifetime,exp_days",
    TIER_MATRIX,
    ids=[t[2] for t in TIER_MATRIX],
)
def test_provision_tier_purchase_helper(
    email, password, tier_key, plan_key, exp_credits, exp_billing,
    exp_lifetime, exp_days,
):
    """For each of the 6 tiers, invoke the helper directly and assert the
    user document is updated correctly, then reset."""
    login = _login(email, password)
    user_id = login["user"]["id"]

    # Pre-condition: user must be on Presale (self-heal / clean-up baseline).
    _run(_reset_user_to_presale(user_id))
    pre = _run(_get_user(user_id))
    assert pre["subscription_plan"] == "Presale", pre

    fake_session_id = f"cs_test_helper_{uuid.uuid4().hex[:12]}"
    meta = {
        "user_id": user_id,
        "user_email": email,
        "tier_key": tier_key,
        "plan_key": plan_key,
        "billing": exp_billing,
        "kind": "tier_purchase",
        "consent_waiver": "true",
        "consent_at": datetime.now(timezone.utc).isoformat(),
        "amount_eur": "0.00",
    }

    try:
        _run(_provision_tier_purchase(
            user_id=user_id,
            meta=meta,
            stripe_subscription="sub_test_x" if exp_billing == "monthly" else None,
            stripe_customer="cus_test_x" if exp_billing == "monthly" else None,
            event_type="pytest_direct_invoke",
            session_id=fake_session_id,
        ))

        post = _run(_get_user(user_id))
        assert post["subscription_plan"] == plan_key, post
        assert post["subscription_status"] == "active", post
        assert post["is_lifetime"] is exp_lifetime, post
        assert post["billing_model"] == exp_billing, post
        assert post["ai_credits_limit"] == exp_credits, post
        assert post["ai_credits_used_this_period"] == 0, post
        assert post.get("consent_waiver") is True, post
        assert post.get("consent_waiver_at"), post

        if exp_days is not None:
            ends_at = post.get("ai_credits_period_ends_at")
            assert ends_at, f"expected ai_credits_period_ends_at set for {tier_key}"
            ends_dt = datetime.fromisoformat(ends_at)
            delta_days = (ends_dt - datetime.now(timezone.utc)).total_seconds() / 86400
            # Allow ±1 day tolerance.
            assert abs(delta_days - exp_days) < 1.5, (
                f"{tier_key}: expected ~{exp_days}d, got {delta_days:.2f}d"
            )
        else:
            # Lifetime + Compleet: no expiry.
            assert post.get("ai_credits_period_ends_at") is None, post

        if exp_billing == "monthly":
            assert post.get("stripe_subscription_id") == "sub_test_x"
            assert post.get("stripe_customer_id") == "cus_test_x"
    finally:
        _run(_reset_user_to_presale(user_id))
        cleanup = _run(_get_user(user_id))
        assert cleanup["subscription_plan"] == "Presale", cleanup


# ----------------------------------------------------- idempotency regression
def test_provision_tier_purchase_idempotent():
    """Calling `_provision_tier_purchase` twice in a row for the same user
    must not corrupt the record — the second call should end in the same
    valid post-state, and ai_credits_used_this_period must remain 0."""
    email, password, tier_key, plan_key = (
        "qa-kickstart1@zynthoro.io", "QaKick1!Test", "kickstart_1", "Kickstart 1"
    )
    login = _login(email, password)
    user_id = login["user"]["id"]
    _run(_reset_user_to_presale(user_id))

    meta = {
        "user_id": user_id,
        "user_email": email,
        "tier_key": tier_key,
        "plan_key": plan_key,
        "billing": "lifetime",
        "kind": "tier_purchase",
        "consent_waiver": "true",
        "consent_at": datetime.now(timezone.utc).isoformat(),
        "amount_eur": "79.00",
    }

    try:
        for i in range(2):
            _run(_provision_tier_purchase(
                user_id=user_id, meta=meta,
                stripe_subscription=None, stripe_customer=None,
                event_type="pytest_idempotency",
                session_id=f"cs_idem_{i}_{uuid.uuid4().hex[:8]}",
            ))

        post = _run(_get_user(user_id))
        assert post["subscription_plan"] == "Kickstart 1"
        assert post["ai_credits_limit"] == 50
        assert post["ai_credits_used_this_period"] == 0
        assert post["is_lifetime"] is True
        assert post["subscription_status"] == "active"
    finally:
        _run(_reset_user_to_presale(user_id))


# ------------------------------------------------------ status endpoint smoke
def test_status_endpoint_404_for_unknown_session():
    email, password, _tk, _pk, *_ = TIER_MATRIX[0]
    login = _login(email, password)
    token = login["access_token"]

    resp = requests.get(
        f"{BASE_URL}/api/checkout/tier/status/cs_fake_{uuid.uuid4().hex}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert resp.status_code == 404, resp.text


def test_status_endpoint_returns_initiated_for_fresh_session():
    """Create a real checkout session (do NOT complete it), then hit the
    status endpoint. Expected: payment_status='initiated', provisioned=False.

    NOTE: we intentionally use consent_waiver=True + kickstart_1 → live Stripe
    session URL comes back; we never open the URL, so no charge occurs.
    """
    email, password, tier_key, *_ = TIER_MATRIX[0]
    login = _login(email, password)
    token = login["access_token"]

    create = requests.post(
        f"{BASE_URL}/api/checkout/tier/session",
        json={
            "tier_key": tier_key,
            "origin_url": BASE_URL,
            "consent_waiver": True,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    assert create.status_code == 200, create.text
    session_id = create.json().get("session_id")
    assert session_id and session_id.startswith("cs_"), create.json()

    status = requests.get(
        f"{BASE_URL}/api/checkout/tier/status/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["session_id"] == session_id
    assert body["provisioned"] is False, body
    # For a freshly-created unpaid session, Stripe returns payment_status='unpaid'
    # and status='open'. The DB row stores payment_status='initiated' until the
    # webhook (or self-heal) fires. Accept either value defensively.
    assert body["payment_status"] in ("initiated", "unpaid", "open", None), body
    assert body["tier_key"] == tier_key


# --------------------------------- regression: consent_waiver=false → 400 -----
def test_consent_waiver_false_still_rejected():
    email, password, tier_key, *_ = TIER_MATRIX[0]
    login = _login(email, password)
    token = login["access_token"]

    resp = requests.post(
        f"{BASE_URL}/api/checkout/tier/session",
        json={"tier_key": tier_key, "origin_url": BASE_URL, "consent_waiver": False},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert resp.status_code == 400, resp.text
    assert "herroepingsrecht" in resp.text.lower(), resp.text


# --------------------------------- regression: QA bypass login still stage='ok'
def test_qa_bypass_login_still_ok():
    for email, password, *_ in TIER_MATRIX:
        r = _login(email, password)
        assert r["stage"] == "ok", (email, r)


# --------------------------------- iter27: InvalidRequestError → clean error ---
def test_invalid_price_id_raises_stripe_invalid_request(monkeypatch):
    """Directly call create_tier_checkout_session with a monkey-patched
    bogus (but format-valid) price_id. Assert that Stripe raises
    InvalidRequestError (which the API handler converts to HTTP 400)."""
    import tier_catalog as _tc  # noqa: WPS433
    import stripe as _stripe  # noqa: WPS433

    original = _tc.TIER_CATALOG["kickstart_1"]["price_id"]
    monkeypatch.setitem(
        _tc.TIER_CATALOG["kickstart_1"],
        "price_id",
        "price_1FakeButFormatValid00000000000",
    )
    assert _tc.TIER_CATALOG["kickstart_1"]["price_id"] != original

    with pytest.raises(_stripe.error.InvalidRequestError):
        _run(_tc.create_tier_checkout_session(
            tier_key="kickstart_1",
            origin_url=BASE_URL,
            user_id="test_user_iter27",
            user_email="qa-kickstart1@zynthoro.io",
            consent_at=datetime.now(timezone.utc).isoformat(),
        ))


def test_unknown_tier_key_returns_422_or_400():
    """Hitting POST /api/checkout/tier/session with an unknown tier_key
    should be rejected by Pydantic (422) or the ValueError branch (400)
    — NEVER 502."""
    email, password, _tk, *_ = TIER_MATRIX[0]
    login = _login(email, password)
    token = login["access_token"]

    resp = requests.post(
        f"{BASE_URL}/api/checkout/tier/session",
        json={
            "tier_key": "totally_bogus_tier",
            "origin_url": BASE_URL,
            "consent_waiver": True,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 502


def test_timeout_branch_returns_504(monkeypatch):
    """Simulate Stripe hanging past the 8s wait_for by monkey-patching
    asyncio.wait_for inside tier_catalog to raise TimeoutError. Calling the
    helper should raise asyncio.TimeoutError (which the API handler maps to
    HTTP 504)."""
    import tier_catalog as _tc  # noqa: WPS433

    async def _fake_wait_for(_coro, timeout):  # noqa: ARG001
        # Close the underlying coroutine so we don't leak a warning.
        try:
            _coro.close()
        except Exception:
            pass
        raise asyncio.TimeoutError()

    monkeypatch.setattr(asyncio, "wait_for", _fake_wait_for)

    with pytest.raises(asyncio.TimeoutError):
        _run(_tc.create_tier_checkout_session(
            tier_key="kickstart_1",
            origin_url=BASE_URL,
            user_id="test_user_iter27_timeout",
            user_email="qa-kickstart1@zynthoro.io",
            consent_at=datetime.now(timezone.utc).isoformat(),
        ))
