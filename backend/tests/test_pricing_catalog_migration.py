"""Stripe migration sanity tests (new account 2026-02-26).

Verifies:
  - GET /api/pricing/catalog (public) returns 7 plans in canonical order
    with new EUR amounts + buy.stripe.com payment links, plus beta block.
  - GET /api/beta/status returns the right product/payment_link/spots.
  - POST /api/beta/checkout returns a Stripe Payment Link URL.
  - GET /api/auth/me regression — jury login still works post key swap.
"""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

EXPECTED_PLANS = [
    ("Starter", "99"),
    ("Creator", "699"),
    ("Business", "899"),
    ("Agency", "1199"),
    ("Enterprise Basic", "2499"),
    ("Enterprise Plus", "3999"),
    ("Enterprise Advanced", "5999"),
]
BETA_LINK = "https://buy.stripe.com/4gM4gy23C8SR5sF5BY4Ni09"
BETA_PRODUCT = "prod_UmAQUfqoR63MYR"


class TestPricingCatalog:
    def test_pricing_catalog_public_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/pricing/catalog", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "plans" in data and "beta" in data
        # 7 plans, correct order, correct amounts
        assert len(data["plans"]) == 7
        for i, (plan_key, amount) in enumerate(EXPECTED_PLANS):
            p = data["plans"][i]
            assert p["plan_key"] == plan_key, f"#{i} expected {plan_key} got {p}"
            assert p["amount_eur"] == amount, f"#{i} amount mismatch: {p}"
            assert p["payment_link"].startswith("https://buy.stripe.com/"), p
        # Beta block
        assert data["beta"]["amount_eur"] == "4.99"
        assert data["beta"]["payment_link"] == BETA_LINK


class TestBetaStatus:
    def test_beta_status_shape(self):
        r = requests.get(f"{BASE_URL}/api/beta/status", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["product_id"] == BETA_PRODUCT
        assert data["amount_eur"] == "4.99"
        assert data["payment_link"] == BETA_LINK
        assert data["spots_total"] == 100
        assert isinstance(data["spots_filled"], int)
        assert data["spots_filled"] >= 0
        assert isinstance(data["spots_remaining"], int)
        assert isinstance(data["capped"], bool)
        assert data["price_id"].startswith("price_")


class TestBetaCheckout:
    def test_beta_checkout_returns_payment_link(self):
        r = requests.post(
            f"{BASE_URL}/api/beta/checkout",
            json={"origin_url": BASE_URL, "email": "TEST_beta@example.com"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "url" in data
        assert data["url"].startswith(BETA_LINK)
        assert "prefilled_email=TEST_beta@example.com" in data["url"]


class TestAuthMeRegression:
    def test_jury_login_and_me(self):
        s = requests.Session()
        r = s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "jury@zynthoro.ai", "password": "ZynthoroDemo2026!"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("stage") == "ok"
        assert body["user"]["email"] == "jury@zynthoro.ai"
        # Bearer fallback too
        token = body["access_token"]
        me = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert me.status_code == 200, me.text
        assert me.json()["email"] == "jury@zynthoro.ai"
