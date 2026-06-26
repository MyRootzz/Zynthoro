"""Daily founder digest tests.

Covers:
- GET /api/founder/digest/preview (founder auth + HTML payload + counts)
- POST /api/founder/digest/send (force=true/false dedupe + system_state persistence)
- is_test row exclusion in both presale_signups and voice_tryout_leads
- Anonymous voice tryouts count vs voice_leads list
- 403 for non-founder users
- 401/403 for unauthenticated requests
- Scheduler startup log line presence
"""
import os
import uuid
import time
import pyotp
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path("/app/backend/.env"))
load_dotenv(Path("/app/frontend/.env"))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

FOUNDER_EMAIL = "regie@myrootzz.com"
FOUNDER_PW = "Zynthoro2026!"
FOUNDER_TOTP = "DSU3VU4MKE46IVOLKP3CLILRA4K4HVS5"

JURY_EMAIL = "jury@zynthoro.ai"
JURY_PW = "ZynthoroDemo2026!"


# ---------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


def _wait_window_advance(secs=1):
    time.sleep(secs)


def _login_founder():
    """Two-step login: password + TOTP. Retries TOTP if window edge."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": FOUNDER_EMAIL, "password": FOUNDER_PW},
               timeout=30)
    assert r.status_code == 200, f"Founder login step1 failed: {r.status_code} {r.text}"
    body = r.json()
    pre_token = body.get("pre_token")
    assert pre_token, f"No pre_token in {body}"

    totp = pyotp.TOTP(FOUNDER_TOTP)
    for attempt in range(3):
        code = totp.now()
        r2 = s.post(
            f"{BASE_URL}/api/auth/2fa/verify",
            json={"pre_token": pre_token, "method": "totp", "code": code},
            timeout=30,
        )
        if r2.status_code == 200:
            tok = r2.json().get("token") or r2.json().get("access_token")
            assert tok, f"No token in {r2.json()}"
            return tok
        time.sleep(2)
    pytest.fail(f"Founder TOTP 2FA failed: {r2.status_code} {r2.text}")


def _login_jury():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": JURY_EMAIL, "password": JURY_PW},
        timeout=30,
    )
    assert r.status_code == 200, f"Jury login failed: {r.status_code} {r.text}"
    body = r.json()
    # Demo bypasses 2FA → access_token returned directly
    tok = body.get("access_token") or body.get("token")
    assert tok, f"No token in jury login response: {body}"
    return tok


@pytest.fixture(scope="session")
def founder_token():
    return _login_founder()


@pytest.fixture(scope="session")
def jury_token():
    return _login_jury()


@pytest.fixture(scope="session")
def founder_headers(founder_token):
    return {"Authorization": f"Bearer {founder_token}"}


# ---------------------------------------------------------------- tests
class TestAuthGuard:
    def test_preview_unauthenticated_rejected(self):
        r = requests.get(f"{BASE_URL}/api/founder/digest/preview", timeout=20)
        assert r.status_code in (401, 403), f"Expected 401/403 got {r.status_code}"

    def test_send_unauthenticated_rejected(self):
        r = requests.post(f"{BASE_URL}/api/founder/digest/send", timeout=20)
        assert r.status_code in (401, 403), f"Expected 401/403 got {r.status_code}"

    def test_preview_jury_forbidden(self, jury_token):
        r = requests.get(
            f"{BASE_URL}/api/founder/digest/preview",
            headers={"Authorization": f"Bearer {jury_token}"},
            timeout=20,
        )
        assert r.status_code == 403, f"Jury must get 403, got {r.status_code} {r.text}"

    def test_send_jury_forbidden(self, jury_token):
        r = requests.post(
            f"{BASE_URL}/api/founder/digest/send",
            headers={"Authorization": f"Bearer {jury_token}"},
            timeout=20,
        )
        assert r.status_code == 403, f"Jury must get 403, got {r.status_code} {r.text}"


class TestDigestPreview:
    """Seed real + test rows, then verify /preview excludes test ones and counts anonymous correctly."""

    SUFFIX = uuid.uuid4().hex[:8]

    @pytest.fixture(scope="class", autouse=True)
    def _seed(self, mongo_db):
        now = datetime.now(timezone.utc).isoformat()
        # presale: 1 real + 1 test (last 24h)
        mongo_db.presale_signups.insert_many([
            {
                "id": f"TEST_real_presale_{self.SUFFIX}",
                "name": f"Real Founder {self.SUFFIX}",
                "email": f"real_presale_{self.SUFFIX}@example.com",
                "company": "RealCo BV",
                "plan_interest": "Creator",
                "created_at": now,
                "is_test": False,
            },
            {
                "id": f"TEST_test_presale_{self.SUFFIX}",
                "name": f"TEST presale {self.SUFFIX}",
                "email": f"test_presale_{self.SUFFIX}@zynthoro-test.com",
                "company": "TEST Co BV",
                "plan_interest": "Creator",
                "created_at": now,
                "is_test": True,
            },
        ])
        # voice tryout: 1 real-with-email + 1 anonymous (no email) + 1 test row
        mongo_db.voice_tryout_leads.insert_many([
            {
                "id": f"TEST_real_voice_{self.SUFFIX}",
                "transcript": f"unique-transcript-real-{self.SUFFIX}",
                "email": f"real_voice_{self.SUFFIX}@example.com",
                "language": "en",
                "is_test": False,
                "created_at": now,
            },
            {
                "id": f"TEST_anon_voice_{self.SUFFIX}",
                "transcript": f"anon-transcript-{self.SUFFIX}",
                "email": None,
                "language": "en",
                "is_test": False,
                "created_at": now,
            },
            {
                "id": f"TEST_test_voice_{self.SUFFIX}",
                "transcript": "should-not-appear",
                "email": f"test_voice_{self.SUFFIX}@zynthoro-test.com",
                "language": "en",
                "is_test": True,
                "created_at": now,
            },
        ])
        yield
        # cleanup
        mongo_db.presale_signups.delete_many({"id": {"$regex": f"TEST_.*_{self.SUFFIX}"}})
        mongo_db.voice_tryout_leads.delete_many({"id": {"$regex": f"TEST_.*_{self.SUFFIX}"}})

    def test_preview_returns_html_and_counts(self, founder_headers):
        r = requests.get(
            f"{BASE_URL}/api/founder/digest/preview",
            headers=founder_headers, timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        # Required keys
        for k in ("html", "presale_count", "voice_lead_count", "voice_anonymous_count"):
            assert k in data, f"Missing key {k}"
        assert isinstance(data["html"], str) and len(data["html"]) > 100
        # HTML branding/title strings
        assert "Daily pipeline digest" in data["html"]
        assert "ZYNTHORO" in data["html"]
        # Counts must reflect our seeded real rows (>=1 each in last 24h)
        assert data["presale_count"] >= 1
        assert data["voice_lead_count"] >= 1
        assert data["voice_anonymous_count"] >= 1

    def test_preview_excludes_test_rows(self, founder_headers):
        r = requests.get(
            f"{BASE_URL}/api/founder/digest/preview",
            headers=founder_headers, timeout=30,
        )
        assert r.status_code == 200
        html = r.json()["html"]
        # Real seeded rows must appear
        assert f"real_presale_{self.SUFFIX}@example.com" in html, "Real presale row missing in HTML"
        assert f"real_voice_{self.SUFFIX}@example.com" in html, "Real voice lead missing in HTML"
        # Test rows must be filtered
        assert f"test_presale_{self.SUFFIX}@zynthoro-test.com" not in html, "Test presale leaked"
        assert f"test_voice_{self.SUFFIX}@zynthoro-test.com" not in html, "Test voice leaked"
        # Anonymous voice tryout transcript MUST NOT appear in the voice_leads list
        assert f"anon-transcript-{self.SUFFIX}" not in html, "Anonymous transcript leaked into list"


class TestDigestSend:
    @pytest.fixture(scope="class", autouse=True)
    def _reset_dedupe(self, mongo_db):
        # Wipe dedupe state so dedupe tests are deterministic
        mongo_db.system_state.delete_one({"_id": "daily_digest"})
        yield
        mongo_db.system_state.delete_one({"_id": "daily_digest"})

    def test_send_force_true_dispatches(self, founder_headers, mongo_db):
        r = requests.post(
            f"{BASE_URL}/api/founder/digest/send?force=true",
            headers=founder_headers, timeout=60,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("sent") is True
        assert body.get("to") == "info@zynthoro.ai"
        assert "presale_count" in body and "voice_lead_count" in body
        today = datetime.now(timezone.utc).date().isoformat()
        assert body.get("date") == today
        # system_state persisted
        st = mongo_db.system_state.find_one({"_id": "daily_digest"})
        assert st is not None
        assert st.get("last_sent_date") == today
        assert "last_sent_at" in st
        # last_msg_id may be None if Resend returns non-dict, which is acceptable
        assert "last_msg_id" in st

    def test_send_default_force_false_dedupes(self, founder_headers):
        # First call (after the force=true above already set today's date)
        r = requests.post(
            f"{BASE_URL}/api/founder/digest/send",
            headers=founder_headers, timeout=60,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("sent") is False
        assert body.get("reason") == "already_sent_today"

        # Second call must remain deduped
        r2 = requests.post(
            f"{BASE_URL}/api/founder/digest/send",
            headers=founder_headers, timeout=60,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2.get("sent") is False
        assert body2.get("reason") == "already_sent_today"

    def test_send_force_true_bypasses_dedupe(self, founder_headers):
        r = requests.post(
            f"{BASE_URL}/api/founder/digest/send?force=true",
            headers=founder_headers, timeout=60,
        )
        assert r.status_code == 200
        assert r.json().get("sent") is True


class TestScheduler:
    def test_scheduler_startup_log_present(self):
        log = Path("/var/log/supervisor/backend.err.log").read_text(errors="ignore")
        assert "Starting daily digest scheduler" in log, \
            "Expected scheduler startup line not found in backend.err.log"
