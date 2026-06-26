"""Iteration 19 — Beta Founding Member program (Stripe LIVE).

Tests:
  - GET /api/beta/status (public, no auth)
  - POST /api/beta/checkout (public, no auth)
  - Idempotency of price (same price_id on repeat call)
  - 422 validation when origin_url is missing
  - email accepted (optional field)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://zynthoro-foundation.preview.emergentagent.com").rstrip("/")


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestBetaStatusPublic:
    """GET /api/beta/status — public, no auth header required."""

    def test_status_no_auth_succeeds(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/beta/status")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        for key in ["price_id", "product_id", "amount_eur", "spots_total", "spots_filled", "spots_remaining", "capped"]:
            assert key in data, f"missing key: {key} in {data}"
        assert data["spots_total"] == 100
        assert data["amount_eur"] == "4.99"
        assert isinstance(data["spots_filled"], int)
        assert isinstance(data["spots_remaining"], int)
        assert isinstance(data["capped"], bool)
        assert data["spots_filled"] + data["spots_remaining"] == 100
        assert data["price_id"].startswith("price_")
        assert data["product_id"].startswith("prod_")

    def test_status_idempotent_same_price_id(self, api_client):
        """Calling twice MUST return the same price_id (cached, not recreated)."""
        r1 = api_client.get(f"{BASE_URL}/api/beta/status")
        r2 = api_client.get(f"{BASE_URL}/api/beta/status")
        assert r1.status_code == 200 and r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        assert d1["price_id"] == d2["price_id"], f"price_id changed between calls! {d1['price_id']} vs {d2['price_id']}"
        assert d1["product_id"] == d2["product_id"]

    def test_status_rejects_no_token_silently(self, api_client):
        """Hitting without auth headers works — explicitly verify."""
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/beta/status")
        assert r.status_code == 200


class TestBetaCheckoutPublic:
    """POST /api/beta/checkout — public, creates Stripe Checkout session."""

    def test_checkout_basic_success(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/beta/checkout",
            json={"origin_url": "https://example.com", "email": None},
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        assert "session_id" in data
        assert "url" in data
        assert data["amount_eur"] == "4.99"
        assert "spots_remaining" in data
        assert data["session_id"].startswith("cs_")
        # LIVE mode -> cs_live_, test mode -> cs_test_
        # URL should be Stripe-hosted
        url = data["url"]
        assert url.startswith("https://checkout.stripe.com/") or url.startswith("https://buy.stripe.com/"), \
            f"unexpected URL: {url}"

    def test_checkout_with_email_accepted(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/beta/checkout",
            json={"origin_url": "https://example.com", "email": "founder@example.com"},
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
        data = r.json()
        assert data["session_id"].startswith("cs_")
        assert data["url"].startswith("https://")

    def test_checkout_missing_origin_url_422(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/beta/checkout", json={})
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"

    def test_checkout_no_auth_required(self, api_client):
        """Hitting without Bearer token works — public endpoint."""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(
            f"{BASE_URL}/api/beta/checkout",
            json={"origin_url": "https://example.com"},
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
