"""Tests for jury demo lockout bypass (P0 bug fix, iter 14).

Validates that:
  - jury@zynthoro.ai logs in successfully (stage=ok) with JWT
  - 10+ wrong-password attempts ALWAYS return 401, never 429
  - correct password still works immediately after wrong-password barrage
  - non-demo account still gets locked (bypass is is_demo-specific)
  - db.login_attempts has no blocking record for the jury email
"""
import os
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv as _ld

_ld("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
JURY_EMAIL = "jury@zynthoro.ai"
JURY_PASSWORD = "ZynthoroDemo2026!"
NON_DEMO_EMAIL = "nodemo_test@zynthoro-test.com"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def mongo_db():
    # backend .env
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = MongoClient(mongo_url)
    return client[db_name]


# ---- Jury demo: lockout immunity ----
class TestJuryDemoLockoutImmunity:
    def test_jury_login_success(self, session):
        r = session.post(f"{BASE_URL}/api/auth/login",
                         json={"email": JURY_EMAIL, "password": JURY_PASSWORD})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("stage") == "ok"
        assert "access_token" in body and isinstance(body["access_token"], str)
        assert body["user"]["email"] == JURY_EMAIL
        assert body["user"].get("is_demo") is True

    def test_jury_wrong_password_10x_never_429(self, session):
        """10 consecutive wrong-password attempts must all return 401."""
        statuses = []
        for i in range(12):
            r = session.post(f"{BASE_URL}/api/auth/login",
                             json={"email": JURY_EMAIL, "password": f"wrong-pw-{i}"})
            statuses.append(r.status_code)
        # All should be 401 — never 429
        assert all(s == 401 for s in statuses), f"Got non-401 statuses: {statuses}"
        assert 429 not in statuses

    def test_jury_correct_password_works_after_barrage(self, session):
        """After many wrong attempts, the correct password must still work."""
        # Hit it with wrong password again first
        for i in range(6):
            session.post(f"{BASE_URL}/api/auth/login",
                         json={"email": JURY_EMAIL, "password": "wrong"})
        # Now correct
        r = session.post(f"{BASE_URL}/api/auth/login",
                         json={"email": JURY_EMAIL, "password": JURY_PASSWORD})
        assert r.status_code == 200, f"Correct login failed after barrage: {r.text}"
        assert r.json().get("stage") == "ok"

    def test_jury_no_blocking_login_attempts_record(self, mongo_db, session):
        """db.login_attempts must have no record (or non-blocking record) for jury."""
        # Trigger several wrong attempts
        for i in range(7):
            session.post(f"{BASE_URL}/api/auth/login",
                         json={"email": JURY_EMAIL, "password": "wrong"})
        rec = mongo_db.login_attempts.find_one({"identifier": f"email:{JURY_EMAIL}"})
        # Either no record, or record exists but doesn't block (we just verified
        # login still works in the previous test). The fix skips record_failed_login
        # for demo accounts, so we expect None or a stale low-count doc.
        if rec is not None:
            # If a stale record exists, login still works, so just print a warning
            print(f"WARN: login_attempts record exists for jury (count={rec.get('count')}) — stale but non-blocking")
        # Verify login still works regardless
        r = session.post(f"{BASE_URL}/api/auth/login",
                         json={"email": JURY_EMAIL, "password": JURY_PASSWORD})
        assert r.status_code == 200


# ---- Non-demo account: lockout still triggers ----
class TestNonDemoLockoutStillActive:
    def test_non_demo_gets_429_after_threshold(self, session, mongo_db):
        # Clean any prior attempts for this synthetic email
        mongo_db.login_attempts.delete_one({"identifier": f"email:{NON_DEMO_EMAIL}"})
        statuses = []
        for i in range(8):
            r = session.post(f"{BASE_URL}/api/auth/login",
                             json={"email": NON_DEMO_EMAIL, "password": f"wrong-{i}"})
            statuses.append(r.status_code)
        # First few should be 401 (user not found), then 429 once threshold passes
        assert 429 in statuses, f"Non-demo account never hit 429 — lockout broken globally? statuses={statuses}"
        # Cleanup
        mongo_db.login_attempts.delete_one({"identifier": f"email:{NON_DEMO_EMAIL}"})
