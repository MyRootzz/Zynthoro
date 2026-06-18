"""Backend tests for Zynthoro Phase 1 - Presale signup API."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://zynthoro-foundation.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4().hex[:10]}@zynthoro-test.com"


# ===== Root =====
class TestRoot:
    def test_root_returns_zynthoro_api(self, api_client):
        r = api_client.get(f"{API}/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("message") == "Zynthoro API"


# ===== Presale signup =====
class TestPresaleSignup:
    def test_signup_valid(self, api_client, unique_email):
        payload = {
            "name": "TEST Founder",
            "email": unique_email,
            "company": "TEST Co BV",
            "plan_interest": "Business",
        }
        r = api_client.post(f"{API}/presale/signup", json=payload)
        assert r.status_code == 201, r.text
        data = r.json()
        assert "id" in data and isinstance(data["id"], str) and len(data["id"]) > 0
        assert data["name"] == "TEST Founder"
        assert data["email"] == unique_email.lower()
        assert data["company"] == "TEST Co BV"
        assert data["plan_interest"] == "Business"
        # Ensure no Mongo _id leakage
        assert "_id" not in data

    def test_duplicate_email_returns_409(self, api_client, unique_email):
        payload = {"name": "TEST Dup", "email": unique_email, "plan_interest": "Starter"}
        r1 = api_client.post(f"{API}/presale/signup", json=payload)
        assert r1.status_code == 201, r1.text
        r2 = api_client.post(f"{API}/presale/signup", json=payload)
        assert r2.status_code == 409, r2.text
        body = r2.json()
        assert "detail" in body

    def test_duplicate_email_case_insensitive(self, api_client, unique_email):
        payload = {"name": "TEST Case", "email": unique_email}
        r1 = api_client.post(f"{API}/presale/signup", json=payload)
        assert r1.status_code == 201
        payload2 = {"name": "TEST Case 2", "email": unique_email.upper()}
        r2 = api_client.post(f"{API}/presale/signup", json=payload2)
        assert r2.status_code == 409

    def test_invalid_email_returns_422(self, api_client):
        r = api_client.post(f"{API}/presale/signup", json={"name": "x", "email": "not-an-email"})
        assert r.status_code == 422

    def test_missing_name_returns_422(self, api_client, unique_email):
        r = api_client.post(f"{API}/presale/signup", json={"email": unique_email})
        assert r.status_code == 422


# ===== Presale count =====
class TestPresaleCount:
    def test_count_increments(self, api_client, unique_email):
        before = api_client.get(f"{API}/presale/count").json()["count"]
        api_client.post(f"{API}/presale/signup", json={"name": "TEST Count", "email": unique_email})
        after = api_client.get(f"{API}/presale/count").json()["count"]
        assert after == before + 1
        assert isinstance(after, int)
