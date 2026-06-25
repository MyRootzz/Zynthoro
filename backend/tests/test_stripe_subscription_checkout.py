"""Fix 8 / Fix 9 — Stripe subscription & seats checkout sessions (LIVE)."""
import os
import pytest
import requests
import pyotp
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

FOUNDER_EMAIL = "regie@myrootzz.com"
FOUNDER_PASSWORD = "Zynthoro2026!"

ALL_PLAN_KEYS = [
    "Starter", "Creator", "Business", "Agency",
    "Enterprise Basic", "Enterprise Plus", "Enterprise Advanced",
]


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _login_founder(db):
    """Log in founder via 2FA setup -> TOTP confirm, return authenticated requests.Session."""
    db.login_attempts.delete_many({})
    db.users.update_one(
        {"email": FOUNDER_EMAIL},
        {"$set": {"twofa_enabled": False, "twofa_method": None},
         "$unset": {"totp_secret": "", "totp_secret_pending": ""}},
    )
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": FOUNDER_EMAIL, "password": FOUNDER_PASSWORD})
    assert r.status_code == 200, r.text
    pre = r.json()["pre_token"]
    r2 = s.post(f"{BASE_URL}/api/auth/2fa/totp/setup", json={"pre_token": pre})
    assert r2.status_code == 200
    secret = r2.json()["secret"]
    r3 = s.post(f"{BASE_URL}/api/auth/2fa/totp/confirm",
                json={"pre_token": pre, "method": "totp", "code": pyotp.TOTP(secret).now()})
    assert r3.status_code == 200
    return s


@pytest.fixture(scope="module")
def founder_session(db):
    """Founder session — but with billing_exempt toggled OFF and a chosen plan
    so that the checkout endpoints actually work. Restores defaults after."""
    s = _login_founder(db)
    # Save original
    orig = db.users.find_one({"email": FOUNDER_EMAIL},
                             {"billing_exempt": 1, "subscription_plan": 1})
    yield s, orig
    # Restore
    db.users.update_one(
        {"email": FOUNDER_EMAIL},
        {"$set": {"billing_exempt": True,
                  "subscription_plan": orig.get("subscription_plan") or "Enterprise Unlimited"}},
    )


def _set_founder(db, *, billing_exempt: bool, plan: str):
    db.users.update_one(
        {"email": FOUNDER_EMAIL},
        {"$set": {"billing_exempt": billing_exempt, "subscription_plan": plan}},
    )


# ============ Subscription session — happy paths ============
class TestSubscriptionSessionHappy:
    @pytest.mark.parametrize("plan_key", ALL_PLAN_KEYS)
    def test_each_plan_returns_stripe_url(self, founder_session, db, plan_key):
        s, _ = founder_session
        _set_founder(db, billing_exempt=False, plan="Business")  # any non-exempt
        r = s.post(f"{BASE_URL}/api/checkout/subscription/session",
                   json={"plan_key": plan_key})
        assert r.status_code == 200, f"{plan_key}: {r.status_code} {r.text}"
        body = r.json()
        assert body["plan_key"] == plan_key
        assert "session_id" in body and body["session_id"].startswith("cs_")
        assert body["url"].startswith("https://checkout.stripe.com/"), body["url"]

        # Verify MongoDB row was inserted
        txn = db.payment_transactions.find_one({"session_id": body["session_id"]})
        assert txn is not None
        assert txn["kind"] == "subscription_change"
        assert txn["plan_key"] == plan_key
        assert txn["payment_status"] == "initiated"
        assert txn["status"] == "open"


# ============ Subscription session — validation ============
class TestSubscriptionSessionValidation:
    def test_invalid_plan_key_returns_422(self, founder_session, db):
        s, _ = founder_session
        _set_founder(db, billing_exempt=False, plan="Business")
        r = s.post(f"{BASE_URL}/api/checkout/subscription/session",
                   json={"plan_key": "Snapchat"})
        assert r.status_code == 422, r.text

    def test_missing_auth_returns_401(self, db):
        r = requests.post(f"{BASE_URL}/api/checkout/subscription/session",
                          json={"plan_key": "Creator"})
        assert r.status_code == 401, r.text

    def test_billing_exempt_returns_400(self, founder_session, db):
        s, _ = founder_session
        _set_founder(db, billing_exempt=True, plan="Enterprise Unlimited")
        r = s.post(f"{BASE_URL}/api/checkout/subscription/session",
                   json={"plan_key": "Creator"})
        assert r.status_code == 400, r.text
        assert "billing-exempt" in r.json().get("detail", "").lower()


# ============ Seats session — happy paths ============
class TestSeatsSessionHappy:
    def test_business_plan_returns_499(self, founder_session, db):
        s, _ = founder_session
        _set_founder(db, billing_exempt=False, plan="Business")
        r = s.post(f"{BASE_URL}/api/checkout/seats/session", json={"quantity": 5})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["quantity"] == 5
        assert body["unit_amount_eur"] == "4.99"
        assert body["url"].startswith("https://checkout.stripe.com/")
        txn = db.payment_transactions.find_one({"session_id": body["session_id"]})
        assert txn and txn["kind"] == "seat_addon" and txn["seat_quantity"] == 5

    def test_agency_plan_returns_399(self, founder_session, db):
        s, _ = founder_session
        _set_founder(db, billing_exempt=False, plan="Agency")
        r = s.post(f"{BASE_URL}/api/checkout/seats/session", json={"quantity": 3})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["unit_amount_eur"] == "3.99"
        assert body["quantity"] == 3
        assert body["url"].startswith("https://checkout.stripe.com/")


# ============ Seats session — validation / disabled plans ============
class TestSeatsSessionValidation:
    def test_enterprise_plan_returns_400_unlimited(self, founder_session, db):
        s, _ = founder_session
        _set_founder(db, billing_exempt=False, plan="Enterprise Basic")
        r = s.post(f"{BASE_URL}/api/checkout/seats/session", json={"quantity": 2})
        assert r.status_code == 400, r.text
        assert "unlimited seats" in r.json().get("detail", "").lower()

    @pytest.mark.parametrize("plan", ["Starter", "Creator"])
    def test_starter_creator_returns_400_not_available(self, founder_session, db, plan):
        s, _ = founder_session
        _set_founder(db, billing_exempt=False, plan=plan)
        r = s.post(f"{BASE_URL}/api/checkout/seats/session", json={"quantity": 2})
        assert r.status_code == 400, r.text
        assert "not available" in r.json().get("detail", "").lower()

    def test_quantity_zero_returns_422(self, founder_session, db):
        s, _ = founder_session
        _set_founder(db, billing_exempt=False, plan="Business")
        r = s.post(f"{BASE_URL}/api/checkout/seats/session", json={"quantity": 0})
        assert r.status_code == 422, r.text

    def test_quantity_101_returns_422(self, founder_session, db):
        s, _ = founder_session
        _set_founder(db, billing_exempt=False, plan="Business")
        r = s.post(f"{BASE_URL}/api/checkout/seats/session", json={"quantity": 101})
        assert r.status_code == 422, r.text

    def test_missing_auth_returns_401(self):
        r = requests.post(f"{BASE_URL}/api/checkout/seats/session", json={"quantity": 5})
        assert r.status_code == 401, r.text

    def test_billing_exempt_returns_400(self, founder_session, db):
        s, _ = founder_session
        _set_founder(db, billing_exempt=True, plan="Enterprise Unlimited")
        r = s.post(f"{BASE_URL}/api/checkout/seats/session", json={"quantity": 5})
        assert r.status_code == 400, r.text


# ============ Webhook smoke test ============
class TestWebhookSmoke:
    def test_no_signature_returns_400(self):
        r = requests.post(f"{BASE_URL}/api/webhook/stripe", data=b'{"x":1}')
        assert r.status_code == 400, r.text

    def test_invalid_signature_returns_400(self):
        r = requests.post(f"{BASE_URL}/api/webhook/stripe",
                          data=b'{"x":1}',
                          headers={"Stripe-Signature": "t=123,v1=deadbeef"})
        assert r.status_code == 400, r.text
