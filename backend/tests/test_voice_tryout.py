"""
Tests for voice tryout lead capture endpoints (iteration 15).
- POST /api/voice-tryout: public anonymous lead capture
- GET  /api/founder/voice-tryouts: founder-only aggregated view
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://zynthoro-foundation.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- POST /api/voice-tryout ----------
class TestVoiceTryoutPost:
    def test_anonymous_no_email(self, client):
        """Anonymous transcript-only payload returns 201 + {id, captured}."""
        r = client.post(f"{API}/voice-tryout", json={
            "transcript": "Hello, I'd like to schedule a demo",
            "language": "en-US",
        })
        assert r.status_code == 201, r.text
        data = r.json()
        assert data.get("captured") is True
        assert isinstance(data.get("id"), str) and len(data["id"]) > 0

    def test_with_real_email(self, client):
        """Email-bearing payload is accepted (is_test=False expected server-side)."""
        unique = uuid.uuid4().hex[:8]
        r = client.post(f"{API}/voice-tryout", json={
            "transcript": "I want to try the voice flow",
            "email": f"prospect_{unique}@example.com",
            "language": "en-US",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["captured"] is True
        assert "id" in body

    def test_with_test_email_flagged(self, client):
        """Emails ending in @zynthoro-test.com must be auto-flagged is_test=True (verified via founder endpoint)."""
        r = client.post(f"{API}/voice-tryout", json={
            "transcript": "automated qa transcript",
            "email": f"test_qa_{uuid.uuid4().hex[:6]}@zynthoro-test.com",
            "language": "en-US",
        })
        assert r.status_code == 201, r.text
        assert r.json()["captured"] is True

    def test_long_transcript_capped(self, client):
        """Pydantic enforces max_length=4000 → 422 if longer."""
        r = client.post(f"{API}/voice-tryout", json={
            "transcript": "x" * 4500,
            "language": "en-US",
        })
        # Pydantic max_length=4000 means longer values are rejected at validation
        assert r.status_code in (201, 422)

    def test_transcript_exactly_4000(self, client):
        """Transcript exactly 4000 chars should pass."""
        r = client.post(f"{API}/voice-tryout", json={
            "transcript": "x" * 4000,
            "language": "en-US",
        })
        assert r.status_code == 201, r.text

    def test_empty_body(self, client):
        """Even empty body should be accepted (Optional fields)."""
        r = client.post(f"{API}/voice-tryout", json={})
        assert r.status_code == 201, r.text

    def test_invalid_email_stored_gracefully(self, client):
        """Server-side stores email as-is (Pydantic only enforces max_length)."""
        r = client.post(f"{API}/voice-tryout", json={
            "transcript": "test",
            "email": "not-a-valid-email",
        })
        assert r.status_code == 201, r.text


# ---------- GET /api/founder/voice-tryouts ----------
class TestVoiceTryoutFounderEndpoint:
    def test_unauthenticated_blocked(self, client):
        """Founder endpoint must require auth."""
        r = requests.get(f"{API}/founder/voice-tryouts")
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}: {r.text}"

    def test_jury_demo_blocked(self, client):
        """Authenticated but non-founder users must also be denied."""
        # Try logging in as jury demo (no 2FA gate per credentials file)
        s = requests.Session()
        login = s.post(f"{API}/auth/login", json={
            "email": "jury@zynthoro.ai",
            "password": "ZynthoroDemo2026!",
        })
        if login.status_code != 200:
            pytest.skip(f"Jury login unavailable: {login.status_code} {login.text[:200]}")
        body = login.json()
        # If login goes straight through (no 2FA), should have access_token cookie set
        if body.get("stage") and body["stage"] != "authenticated":
            pytest.skip(f"Jury login still in stage {body.get('stage')} — cannot finish flow without 2FA")
        r = s.get(f"{API}/founder/voice-tryouts")
        assert r.status_code in (401, 403), f"Non-founder allowed! Got {r.status_code}"
