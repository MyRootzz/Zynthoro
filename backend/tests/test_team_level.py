"""Fix 7 — Team invite level hierarchy: plan-based max-level enforcement.

Founder (Enterprise Unlimited) -> max_level = 10
Starter user (signed up fresh)  -> max_level = 3
"""
import os
import time
import uuid

import pyotp
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://zynthoro-foundation.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

FOUNDER_EMAIL = "regie@myrootzz.com"
FOUNDER_PASS = "Zynthoro2026!"


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _login_founder(db):
    """Returns an authenticated requests.Session for the founder."""
    s = requests.Session()
    # Reset 2FA on founder to keep test deterministic
    db.users.update_one(
        {"email": FOUNDER_EMAIL},
        {"$set": {"twofa_enabled": False, "twofa_method": None},
         "$unset": {"totp_secret": "", "totp_secret_pending": ""}},
    )
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": FOUNDER_EMAIL, "password": FOUNDER_PASS})
    assert r.status_code == 200, r.text
    data = r.json()
    if data.get("stage") == "2fa_setup_required":
        pre = data["pre_token"]
        sr = s.post(f"{BASE_URL}/api/auth/2fa/totp/setup", json={"pre_token": pre})
        assert sr.status_code == 200, sr.text
        secret = sr.json()["secret"]
        code = pyotp.TOTP(secret).now()
        cr = s.post(f"{BASE_URL}/api/auth/2fa/totp/confirm",
                    json={"pre_token": pre, "method": "totp", "code": code})
        assert cr.status_code == 200, cr.text
    elif data.get("stage") == "2fa_required":
        # Should not happen because we reset above, but handle just in case
        pytest.skip("Founder still requires 2FA after reset.")
    return s


def _signup_fresh_starter(db):
    """Create a fresh Starter user (plan stays 'Presale' by default which has max_level=5).
    Force plan to 'Starter' in DB so we get max_level=3."""
    s = requests.Session()
    email = f"TEST_lvl_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "first_name": "Lvl", "last_name": "Test", "email": email,
        "password": "TestPass2026!", "company": "LvlCo",
    })
    assert r.status_code in (200, 201), r.text
    # Read verification token from db
    user = db.users.find_one({"email": email.lower()})
    assert user, f"user not found in db for {email.lower()}"
    token = user.get("verification_token")
    assert token, "no verification_token in db"
    vr = s.get(f"{BASE_URL}/api/auth/verify-email", params={"token": token})
    assert vr.status_code == 200, vr.text
    # Force plan to Starter so level cap = 3
    db.users.update_one({"email": email.lower()}, {"$set": {"subscription_plan": "Starter"}})
    # Login + 2FA setup
    lr = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "TestPass2026!"})
    assert lr.status_code == 200, lr.text
    ld = lr.json()
    assert ld.get("stage") == "2fa_setup_required", ld
    pre = ld["pre_token"]
    sr = s.post(f"{BASE_URL}/api/auth/2fa/totp/setup", json={"pre_token": pre})
    secret = sr.json()["secret"]
    code = pyotp.TOTP(secret).now()
    cr = s.post(f"{BASE_URL}/api/auth/2fa/totp/confirm",
                json={"pre_token": pre, "method": "totp", "code": code})
    assert cr.status_code == 200, cr.text
    return s, email


class TestTeamLevelHierarchy:
    def test_founder_team_list_reports_plan_and_max(self, db):
        s = _login_founder(db)
        r = s.get(f"{BASE_URL}/api/team/members")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["plan"] == "Enterprise Unlimited"
        assert body["max_level"] == 10
        owner = body["members"][0]
        assert owner["is_owner"] is True
        assert owner["level"] == 10
        assert owner["level_label"] == "Owner"

    def test_founder_can_invite_level_10(self, db):
        s = _login_founder(db)
        invite_email = f"TEST_lvl10_{uuid.uuid4().hex[:6]}@example.com"
        r = s.post(f"{BASE_URL}/api/team/invite", json={
            "email": invite_email, "role": "Director", "level": 10,
        })
        assert r.status_code == 201, r.text
        # Cleanup
        db.team_members.delete_many({"email": invite_email})

    def test_starter_cannot_invite_above_level_3(self, db):
        s, email = _signup_fresh_starter(db)
        try:
            # Level 3 should succeed
            ok_email = f"TEST_lvl3_{uuid.uuid4().hex[:6]}@example.com"
            r1 = s.post(f"{BASE_URL}/api/team/invite", json={
                "email": ok_email, "role": "Employee", "level": 3,
            })
            assert r1.status_code == 201, r1.text

            # Level 10 should be forbidden
            bad_email = f"TEST_lvl10_{uuid.uuid4().hex[:6]}@example.com"
            r2 = s.post(f"{BASE_URL}/api/team/invite", json={
                "email": bad_email, "role": "Director", "level": 10,
            })
            assert r2.status_code == 403, r2.text
            detail = r2.json().get("detail", "")
            assert "Starter" in detail and "level 3" in detail
        finally:
            db.team_members.delete_many({"workspace_owner": (db.users.find_one({"email": email}) or {}).get("id")})
            db.users.delete_one({"email": email})

    def test_invite_level_out_of_range_rejected_by_pydantic(self, db):
        s = _login_founder(db)
        r = s.post(f"{BASE_URL}/api/team/invite", json={
            "email": "TEST_outofrange@example.com", "role": "X", "level": 11,
        })
        assert r.status_code == 422, r.text
