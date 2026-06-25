"""Backend tests for Zyntha caption endpoint POST /api/marketing/caption.

Covers:
- Auth: login with TOTP (founder has 2FA enabled)
- Happy path on each of the 6 supported platforms
- Validation 422 for short idea and invalid platform
- 401 when not authenticated
- ai_logs persistence with assistant=zyntha, provider=gemini, status=ok
"""
import os
import time
import pyotp
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://zynthoro-foundation.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

FOUNDER_EMAIL = "regie@myrootzz.com"
FOUNDER_PASSWORD = "Zynthoro2026!"


def _mongo_db():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "test_database")]


@pytest.fixture(scope="module")
def auth_session():
    """Login as founder, complete TOTP 2FA, return requests.Session with cookies + token."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})

    db = _mongo_db()
    founder = db.users.find_one({"email": FOUNDER_EMAIL})
    if not founder:
        pytest.skip("Founder user missing")

    # Step 1: login
    r = s.post(f"{API}/auth/login", json={"email": FOUNDER_EMAIL, "password": FOUNDER_PASSWORD})
    assert r.status_code == 200, f"Login failed {r.status_code}: {r.text}"
    body = r.json()

    if body.get("stage") == "ok":
        token = body["token"]
    elif body.get("stage") == "2fa_required":
        pre_token = body["pre_token"]
        secret = founder.get("totp_secret")
        assert secret, "TOTP enabled but no secret on user doc"
        code = pyotp.TOTP(secret).now()
        r2 = s.post(f"{API}/auth/2fa/verify", json={"pre_token": pre_token, "method": "totp", "code": code})
        assert r2.status_code == 200, f"2FA verify failed: {r2.text}"
        token = r2.json()["token"]
    elif body.get("stage") == "2fa_setup_required":
        pytest.skip("Founder requires 2FA setup — out of scope for this test")
    else:
        pytest.fail(f"Unexpected login stage: {body}")

    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ---------- happy path ----------
@pytest.mark.parametrize("platform", ["instagram", "facebook", "linkedin", "tiktok", "x", "youtube"])
def test_caption_happy_path_each_platform(auth_session, platform):
    """Caption should be returned for every supported platform with proper shape."""
    payload = {
        "idea": "Just launched our new sustainable coffee blend",
        "platform": platform,
    }
    r = auth_session.post(f"{API}/marketing/caption", json=payload, timeout=30)
    assert r.status_code == 200, f"{platform}: status={r.status_code} body={r.text[:300]}"
    body = r.json()

    # Shape assertions
    assert "caption" in body and isinstance(body["caption"], str)
    assert "hashtags" in body and isinstance(body["hashtags"], list)
    assert body["provider"] == "gemini"
    assert body["model"]
    assert body["platform"] == platform
    assert "badge" in body

    # Caption non-empty and not raw JSON
    caption = body["caption"].strip()
    assert len(caption) > 0, "caption is empty"
    assert not caption.startswith('{"caption"'), f"caption is raw JSON: {caption[:80]}"
    assert "```" not in caption, "caption contains code fence backticks"

    # Hashtags: lower-case, no leading '#'
    tags = body["hashtags"]
    if tags:  # may be empty fallback
        for t in tags:
            assert isinstance(t, str)
            assert not t.startswith("#"), f"hashtag has leading #: {t}"
            assert t == t.lower(), f"hashtag not lowercase: {t}"


# ---------- validation ----------
def test_caption_empty_idea_returns_422(auth_session):
    r = auth_session.post(f"{API}/marketing/caption", json={"idea": "", "platform": "instagram"})
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"


def test_caption_short_idea_returns_422(auth_session):
    r = auth_session.post(f"{API}/marketing/caption", json={"idea": "hi", "platform": "instagram"})
    assert r.status_code == 422, f"expected 422 for <3 chars, got {r.status_code}: {r.text}"


def test_caption_invalid_platform_returns_422(auth_session):
    r = auth_session.post(f"{API}/marketing/caption", json={"idea": "Some valid post idea", "platform": "snapchat"})
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"


def test_caption_unauthenticated_returns_401():
    """No auth headers/cookies => 401."""
    r = requests.post(f"{API}/marketing/caption", json={"idea": "Hello world from zynthoro", "platform": "instagram"})
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}: {r.text}"


# ---------- ai_logs persistence ----------
def test_caption_persists_ai_log(auth_session):
    """After a successful caption call, an ai_logs row with assistant=zyntha, provider=gemini, status=ok must exist."""
    db = _mongo_db()
    before = db.ai_logs.count_documents({"assistant": "zyntha", "provider": "gemini", "status": "ok"})

    r = auth_session.post(
        f"{API}/marketing/caption",
        json={"idea": "Testing ai_logs persistence pipeline", "platform": "instagram"},
        timeout=30,
    )
    assert r.status_code == 200, r.text

    # tiny wait — insert is awaited in the request handler so usually instant
    time.sleep(0.5)
    after = db.ai_logs.count_documents({"assistant": "zyntha", "provider": "gemini", "status": "ok"})
    assert after >= before + 1, f"ai_logs row not inserted: before={before} after={after}"

    latest = db.ai_logs.find_one(
        {"assistant": "zyntha", "provider": "gemini", "status": "ok"},
        sort=[("timestamp", -1)],
    )
    assert latest is not None
    assert latest["model"]
    assert latest["latency_ms"] >= 0
