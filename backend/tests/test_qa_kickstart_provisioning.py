"""
Iteration 24 — QA Kickstart provisioning tests.

Verifies:
  * The 6 QA test accounts (is_qa_test=true) can log in directly without
    the 2FA setup wizard.
  * Their /auth/me returns Presale tier with modules=['settings','team']
    and ai_credits_limit=10.
  * POST /checkout/tier/session with consent_waiver=true returns a
    stripe checkout URL with the correct amount.
  * Regression: founder + demo accounts still bypass 2FA.
  * Negative: consent_waiver=false → 400 with 'herroepingsrecht'.
  * Negative: a fresh non-flagged user must go through 2fa_setup_required.
"""
import os
import time
import uuid
import asyncio
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

QA_ACCOUNTS = [
    ("qa-kickstart1@zynthoro.io", "QaKick1!Test", "kickstart_1", 79.0),
    ("qa-kickstart2@zynthoro.io", "QaKick2!Test", "kickstart_2", 149.0),
    ("qa-kickstart3@zynthoro.io", "QaKick3!Test", "kickstart_3", 199.0),
    ("qa-compleet@zynthoro.io",   "QaComp!Test",  "compleet",    79.99),
    ("qa-aiweek@zynthoro.io",     "QaWeek!Test",  "ai_social_week",  24.99),
    ("qa-aimonth@zynthoro.io",    "QaMonth!Test", "ai_social_month", 59.99),
]


def _login(email: str, password: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    return r


# ---- QA accounts: direct login (no 2FA) ---------------------------------
@pytest.mark.parametrize("email,password,tier_key,amount", QA_ACCOUNTS)
def test_qa_account_direct_login(email, password, tier_key, amount):
    r = _login(email, password)
    assert r.status_code == 200, f"{email}: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("stage") == "ok", f"{email}: expected stage=ok, got {data}"
    assert data.get("access_token"), f"{email}: no access_token"
    assert data["user"]["email"] == email


# ---- /auth/me tier context for QA accounts ------------------------------
@pytest.mark.parametrize("email,password,tier_key,amount", QA_ACCOUNTS)
def test_qa_account_tier_context(email, password, tier_key, amount):
    r = _login(email, password)
    assert r.status_code == 200 and r.json().get("stage") == "ok"
    token = r.json()["access_token"]

    me = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert me.status_code == 200, me.text
    body = me.json()
    tier = body.get("tier")
    assert tier is not None, body
    assert tier["plan_key"] == "Presale", tier
    assert set(tier["modules"]) <= {"settings", "team"}, tier["modules"]
    assert tier["ai_credits_limit"] == 10, tier


# ---- Stripe checkout session per tier -----------------------------------
@pytest.mark.parametrize("email,password,tier_key,amount", QA_ACCOUNTS)
def test_qa_account_tier_checkout(email, password, tier_key, amount):
    r = _login(email, password)
    assert r.status_code == 200 and r.json().get("stage") == "ok"
    token = r.json()["access_token"]

    payload = {
        "tier_key": tier_key,
        "origin_url": BASE_URL,
        "consent_waiver": True,
    }
    resp = requests.post(
        f"{BASE_URL}/api/checkout/tier/session",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    assert resp.status_code == 200, f"{tier_key}: {resp.status_code} {resp.text}"
    body = resp.json()
    assert body["tier_key"] == tier_key
    assert body["amount"] == amount, f"{tier_key}: got amount={body['amount']}"
    url = body.get("url", "")
    # Live mode session URLs start with https://checkout.stripe.com/c/pay/cs_(live|test)_
    assert url.startswith("https://checkout.stripe.com/"), f"unexpected url: {url}"
    assert "cs_" in url


# ---- Negative: consent_waiver=false ------------------------------------
def test_consent_waiver_false_rejected():
    email, password, tier_key, _ = QA_ACCOUNTS[0]
    r = _login(email, password)
    token = r.json()["access_token"]

    resp = requests.post(
        f"{BASE_URL}/api/checkout/tier/session",
        json={"tier_key": tier_key, "origin_url": BASE_URL, "consent_waiver": False},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert resp.status_code == 400, resp.text
    assert "herroepingsrecht" in resp.text.lower(), resp.text


# ---- Regression: founder + demo still bypass 2FA ------------------------
@pytest.mark.parametrize("email,password", [
    ("regie@myrootzz.com", "Zynthoro2026!"),
    ("jury@zynthoro.ai",   "ZynthoroDemo2026!"),
])
def test_founder_demo_regression(email, password):
    r = _login(email, password)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("stage") == "ok", f"{email}: expected stage=ok, got {data}"
    assert data.get("access_token")


# ---- Negative: fresh non-flagged user must hit 2fa_setup_required -------
def test_non_flagged_user_requires_2fa_setup():
    """Create a user directly in mongo (bypassing signup email verify),
    with is_qa_test/is_demo/is_founder all False, and email_verified=True.
    Login must return stage='2fa_setup_required' (NOT 'ok').
    """
    import motor.motor_asyncio
    from passlib.context import CryptContext

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    ts = int(time.time())
    email = f"regression-test-{ts}@zynthoro.io"
    password = "RegPass1!"
    user_doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": pwd_ctx.hash(password),
        "first_name": "Reg",
        "last_name": "Test",
        "email_verified": True,
        "twofa_enabled": False,
        "is_qa_test": False,
        "is_demo": False,
        "is_founder": False,
        "billing_exempt": False,
        "is_unlimited": False,
        "subscription_plan": "Presale",
        "created_at": "2026-07-20T00:00:00Z",
    }

    async def _insert():
        client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        try:
            await client[db_name].users.insert_one(user_doc)
        finally:
            client.close()

    async def _cleanup():
        client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        try:
            await client[db_name].users.delete_one({"email": email})
        finally:
            client.close()

    asyncio.get_event_loop().run_until_complete(_insert())
    try:
        r = _login(email, password)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("stage") == "2fa_setup_required", (
            f"expected 2fa_setup_required for non-flagged user, got {data}"
        )
        assert data.get("access_token") in (None, ""), data
    finally:
        asyncio.get_event_loop().run_until_complete(_cleanup())
