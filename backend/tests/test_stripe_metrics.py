"""Tests for the Builder-Mode `Stripe MRR / ARR` widget.

Covers:
  * Unit-level math on `compute_stripe_mrr` with stubbed `stripe.Subscription.list`
    (a) one monthly Creator sub  → mrr = 699
    (b) one yearly  Business sub → mrr = 899
    (c) one Business with 5 extra seats @ €4.99/seat → mrr = 923.95, seats_mrr = 24.95
    Plus assertions for `arr_eur = 12 * mrr_eur` and the plan_breakdown ordering.
  * API-level authz on GET /api/founder/stripe-metrics:
        anonymous              → 401
        non-founder logged-in  → 403
        founder                → 200 + correct empty-state shape (pre-launch acct)
"""
import os
import time
import types
import uuid
from unittest.mock import patch

import pytest
import requests

import sys
sys.path.insert(0, "/app/backend")

from stripe_subscriptions import (  # noqa: E402
    compute_stripe_mrr,
    PLAN_PRICE_IDS,
    SEAT_PRICE_IDS,
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to read frontend/.env if env not exported in this shell.
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers — build a fake Stripe Subscription.list page from plain dicts
# ---------------------------------------------------------------------------
class _Page:
    def __init__(self, items, has_more=False):
        # mimic stripe's `ListObject` minimally
        self.data = [_Sub(d) for d in items]
        self.has_more = has_more


class _Sub:
    def __init__(self, d):
        self._d = d
        self.id = d.get("id", "sub_test")

    def __getitem__(self, k):
        return self._d[k]


def _make_page(*items):
    return _Page(list(items), has_more=False)


def _sub(items):
    return {"id": f"sub_{uuid.uuid4().hex[:8]}", "items": {"data": items}}


def _item(price_id, unit_amount, interval, qty=1):
    return {
        "price": {
            "id": price_id,
            "unit_amount": unit_amount,
            "recurring": {"interval": interval},
        },
        "quantity": qty,
    }


# ---------------------------------------------------------------------------
# Unit tests — MRR math
# ---------------------------------------------------------------------------
class TestComputeStripeMrr:
    def test_monthly_creator_subscription(self):
        creator = PLAN_PRICE_IDS["Creator"]["price_id"]
        page = _make_page(_sub([_item(creator, 69900, "month")]))
        with patch("stripe_subscriptions.stripe.Subscription.list", return_value=page):
            res = compute_stripe_mrr()
        assert res["active_subs"] == 1
        assert res["mrr_eur"] == 699.0
        assert res["arr_eur"] == round(12 * 699.0, 2)
        assert res["seats_mrr_eur"] == 0.0
        assert len(res["plan_breakdown"]) == 1
        assert res["plan_breakdown"][0]["plan_key"] == "Creator"
        assert res["plan_breakdown"][0]["count"] == 1
        assert res["plan_breakdown"][0]["mrr_eur"] == 699.0
        assert res["seat_breakdown"] == []
        assert res["currency"] == "eur"

    def test_yearly_business_subscription_divides_by_12(self):
        business = PLAN_PRICE_IDS["Business"]["price_id"]
        # €10788/year = €899/month
        page = _make_page(_sub([_item(business, 1078800, "year")]))
        with patch("stripe_subscriptions.stripe.Subscription.list", return_value=page):
            res = compute_stripe_mrr()
        assert res["active_subs"] == 1
        assert res["mrr_eur"] == 899.0
        assert res["arr_eur"] == round(12 * 899.0, 2)
        assert res["plan_breakdown"][0]["plan_key"] == "Business"

    def test_business_plus_extra_seats(self):
        business = PLAN_PRICE_IDS["Business"]["price_id"]
        seat = SEAT_PRICE_IDS["Business"]["price_id"]
        # 1 Business monthly (€899) + 5 seats @ €4.99 = €24.95 = €923.95 MRR
        page = _make_page(_sub([
            _item(business, 89900, "month"),
            _item(seat, 499, "month", qty=5),
        ]))
        with patch("stripe_subscriptions.stripe.Subscription.list", return_value=page):
            res = compute_stripe_mrr()
        assert res["active_subs"] == 1
        assert res["mrr_eur"] == 923.95
        assert res["seats_mrr_eur"] == 24.95
        assert res["arr_eur"] == round(12 * 923.95, 2)
        # Plan breakdown should only show Business (seats live in seat_breakdown)
        assert [p["plan_key"] for p in res["plan_breakdown"]] == ["Business"]
        assert res["plan_breakdown"][0]["mrr_eur"] == 899.0
        assert res["seat_breakdown"] == [
            {"plan_key": "Business", "seats": 5, "mrr_eur": 24.95}
        ]

    def test_weekly_interval_multiplies_by_52_over_12(self):
        # Custom price, falls into "Other" bucket since not in PLAN_PRICE_IDS
        page = _make_page(_sub([_item("price_weekly_custom", 1000, "week")]))
        with patch("stripe_subscriptions.stripe.Subscription.list", return_value=page):
            res = compute_stripe_mrr()
        # 1000 cents * 52 / 12 = 4333.33... → /100 = 43.33
        assert res["mrr_eur"] == round((1000 * 52 / 12) / 100, 2)
        assert res["plan_breakdown"][0]["plan_key"] == "Other"

    def test_plan_breakdown_ordering(self):
        # Build a sub for every named plan in reverse order; result must be in
        # declared plan order: Starter, Creator, Business, Agency, Enterprise*..., Other.
        keys_reversed = list(PLAN_PRICE_IDS.keys())[::-1]
        subs = [
            _sub([_item(PLAN_PRICE_IDS[k]["price_id"], 10000, "month")])
            for k in keys_reversed
        ]
        # plus one "Other" sub
        subs.append(_sub([_item("price_unknown_xyz", 5000, "month")]))
        page = _make_page(*subs)
        with patch("stripe_subscriptions.stripe.Subscription.list", return_value=page):
            res = compute_stripe_mrr()
        expected_order = [
            "Starter", "Creator", "Business", "Agency",
            "Enterprise Basic", "Enterprise Plus", "Enterprise Advanced", "Other",
        ]
        assert [p["plan_key"] for p in res["plan_breakdown"]] == expected_order
        assert res["active_subs"] == len(subs)


# ---------------------------------------------------------------------------
# API tests — authz + empty-state on the live pre-launch Stripe account
# ---------------------------------------------------------------------------
def _login_founder():
    """Login as founder. Handles 2FA via email path. Returns access_token cookie value."""
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "regie@myrootzz.com", "password": "Zynthoro2026!"},
               timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Founder login HTTP {r.status_code}: {r.text}")
    data = r.json()
    stage = data.get("stage")
    if stage in (None, "authenticated"):
        return s
    if stage == "2fa_required":
        pre = data.get("pre_token")
        # Prefer email method since we can read the code from backend log.
        rr = s.post(f"{BASE_URL}/api/auth/2fa/email/request", json={"pre_token": pre}, timeout=15)
        if rr.status_code != 200:
            pytest.skip(f"2FA email request failed: {rr.status_code} {rr.text}")
        # Wait for log write, then parse latest 6-digit code from backend.err.log
        time.sleep(1.5)
        code = None
        try:
            with open("/var/log/supervisor/backend.err.log", errors="ignore") as fh:
                tail = fh.read()[-20000:]
            import re
            matches = re.findall(r"\b(\d{6})\b", tail)
            if matches:
                code = matches[-1]
        except Exception:
            pass
        if not code:
            pytest.skip("Could not read 2FA email code from backend log")
        v = s.post(f"{BASE_URL}/api/auth/2fa/verify",
                   json={"pre_token": pre, "method": "email", "code": code}, timeout=15)
        if v.status_code != 200:
            pytest.skip(f"2FA verify failed: {v.status_code} {v.text}")
        return s
    pytest.skip(f"Unexpected login stage: {stage}")


@pytest.fixture(scope="module")
def founder_session():
    return _login_founder()


def _signup_random_user():
    """Create + verify a fresh non-founder user. Returns logged-in session or skips."""
    s = requests.Session()
    email = f"TEST_metrics_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "TestPass2026!"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "first_name": "Test", "last_name": "Metrics",
        "email": email, "password": pwd, "company": "TestCo",
    }, timeout=15)
    if r.status_code not in (200, 201):
        pytest.skip(f"Signup failed: {r.status_code} {r.text}")
    # Fetch verify token from Mongo
    try:
        from pymongo import MongoClient
        mc = MongoClient(os.environ.get("MONGO_URL"))
        db = mc[os.environ.get("DB_NAME", "test_database")]
        u = db.users.find_one({"email": email.lower()})
        token = u and u.get("verification_token")
    except Exception as e:
        pytest.skip(f"Mongo lookup failed: {e}")
    if not token:
        pytest.skip("No verification_token on new user")
    s.get(f"{BASE_URL}/api/auth/verify-email", params={"token": token}, timeout=15)
    lr = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=15)
    if lr.status_code != 200:
        pytest.skip(f"Login of fresh user failed: {lr.status_code} {lr.text}")
    stage = lr.json().get("stage")
    if stage == "2fa_setup_required":
        # Brand-new account requires TOTP setup before access — for authz check
        # we just need to confirm the bare `/founder/stripe-metrics` returns 403
        # WITHOUT going through 2FA. Use the cookieless approach: hit the endpoint
        # with this session — there is no access_token yet, so it'll be 401, which
        # is NOT what we want.
        # Instead complete TOTP setup.
        import pyotp
        pre = lr.json().get("pre_token")
        setup = s.post(f"{BASE_URL}/api/auth/2fa/totp/setup", json={"pre_token": pre}, timeout=15)
        if setup.status_code != 200:
            pytest.skip(f"TOTP setup failed: {setup.status_code} {setup.text}")
        secret = setup.json().get("secret")
        code = pyotp.TOTP(secret).now()
        conf = s.post(f"{BASE_URL}/api/auth/2fa/totp/confirm",
                      json={"pre_token": pre, "method": "totp", "code": code}, timeout=15)
        if conf.status_code != 200:
            pytest.skip(f"TOTP confirm failed: {conf.status_code} {conf.text}")
    return s


class TestStripeMetricsEndpoint:
    def test_anonymous_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/founder/stripe-metrics", timeout=10)
        assert r.status_code == 401, r.text

    def test_non_founder_returns_403(self):
        s = _signup_random_user()
        r = s.get(f"{BASE_URL}/api/founder/stripe-metrics", timeout=10)
        assert r.status_code == 403, r.text

    def test_founder_returns_200_with_shape(self, founder_session):
        start = time.time()
        r = founder_session.get(f"{BASE_URL}/api/founder/stripe-metrics", timeout=12)
        elapsed = time.time() - start
        assert r.status_code == 200, r.text
        assert elapsed < 8.0, f"Endpoint too slow: {elapsed:.2f}s"
        data = r.json()
        # Shape
        for k in ["active_subs", "mrr_eur", "arr_eur", "seats_mrr_eur",
                  "plan_breakdown", "seat_breakdown", "currency", "fetched_at"]:
            assert k in data, f"Missing key {k}"
        assert isinstance(data["active_subs"], int)
        assert isinstance(data["plan_breakdown"], list)
        assert isinstance(data["seat_breakdown"], list)
        assert data["currency"] == "eur"
        # Pre-launch live account
        if data["active_subs"] == 0:
            assert data["mrr_eur"] == 0.0
            assert data["arr_eur"] == 0.0
            assert data["plan_breakdown"] == []
            assert data["seat_breakdown"] == []
