"""Phase 2 backend tests: auth, 2FA, onboarding, dashboard, team, AI chat, founder, checkout."""
import os
import time
import uuid
import pytest
import requests
import pyotp
from pymongo import MongoClient

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if os.environ.get('REACT_APP_BACKEND_URL') else None
if not BASE_URL:
    # Fallback to frontend .env
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

FOUNDER_EMAIL = "regie@myrootzz.com"
FOUNDER_PASSWORD = "Zynthoro2026!"


@pytest.fixture(scope="session")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="session", autouse=True)
def clear_lockouts(db):
    """Clear brute-force lockouts before tests."""
    db.login_attempts.delete_many({})
    yield
    db.login_attempts.delete_many({})


@pytest.fixture(scope="session")
def unique_email():
    return f"signup_e2e_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture(scope="session")
def state():
    return {}


# ============ Signup / Verify Email ============
class TestSignupVerify:
    def test_signup_creates_user(self, unique_email, state):
        r = requests.post(f"{BASE_URL}/api/auth/signup", json={
            "first_name": "Test",
            "last_name": "User",
            "email": unique_email,
            "password": "Password123!",
            "company": "Test Co",
        })
        assert r.status_code == 201, r.text
        data = r.json()
        assert "user_id" in data
        assert "dev_verification_token" in data
        state["user_id"] = data["user_id"]
        state["verify_token"] = data["dev_verification_token"]
        state["email"] = unique_email

    def test_signup_duplicate_returns_409(self, unique_email):
        r = requests.post(f"{BASE_URL}/api/auth/signup", json={
            "first_name": "Test",
            "last_name": "User",
            "email": unique_email,
            "password": "Password123!",
            "company": "Test Co",
        })
        assert r.status_code == 409

    def test_verify_email(self, state):
        r = requests.get(f"{BASE_URL}/api/auth/verify-email", params={"token": state["verify_token"]})
        assert r.status_code == 200
        assert "verified" in r.json().get("message", "").lower()


# ============ Login + 2FA Setup ============
class TestLoginTwoFA:
    def test_login_returns_2fa_setup_required(self, state):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": state["email"], "password": "Password123!"
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["stage"] == "2fa_setup_required"
        assert "pre_token" in data
        state["pre_token"] = data["pre_token"]

    def test_totp_setup_returns_qr(self, state):
        r = requests.post(f"{BASE_URL}/api/auth/2fa/totp/setup",
                          json={"pre_token": state["pre_token"]})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["qr_data_url"].startswith("data:image/png;base64,")
        assert len(data["secret"]) > 10
        state["totp_secret"] = data["secret"]

    def test_totp_confirm_sets_access_cookie(self, state):
        code = pyotp.TOTP(state["totp_secret"]).now()
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/2fa/totp/confirm", json={
            "pre_token": state["pre_token"], "method": "totp", "code": code
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["stage"] == "ok"
        assert "access_token" in s.cookies
        assert data["user"]["email"] == state["email"]
        state["session"] = s

    def test_me_returns_user(self, state):
        s = state["session"]
        r = s.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["email"] == state["email"]
        assert "company" in u and "role" in u
        assert "subscription_plan" in u
        assert "onboarding_completed" in u
        assert "password_hash" not in u
        assert "_id" not in u

    def test_login_again_returns_2fa_required(self, state):
        # Now twofa_enabled=true, login should return 2fa_required
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": state["email"], "password": "Password123!"
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["stage"] == "2fa_required"
        state["pre_token2"] = data["pre_token"]

    def test_email_2fa_flow(self, state):
        r = requests.post(f"{BASE_URL}/api/auth/2fa/email/request",
                          json={"pre_token": state["pre_token2"]})
        assert r.status_code == 200, r.text
        code = r.json().get("dev_code")
        assert code and len(code) == 6
        # Verify with email code
        r2 = requests.post(f"{BASE_URL}/api/auth/2fa/verify", json={
            "pre_token": state["pre_token2"], "method": "email", "code": code
        })
        assert r2.status_code == 200, r2.text
        assert r2.json()["stage"] == "ok"


# ============ Brute force ============
class TestBruteForce:
    def test_brute_force_lockout(self, db):
        email = f"bf_{uuid.uuid4().hex[:6]}@example.com"
        # Create a user so we get past "user not found" path consistently
        requests.post(f"{BASE_URL}/api/auth/signup", json={
            "first_name": "BF", "last_name": "User", "email": email,
            "password": "Correct123!", "company": "X",
        })
        # 5 wrong attempts
        for i in range(5):
            r = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"email": email, "password": "wrong"})
            assert r.status_code == 401, f"Attempt {i+1}: {r.status_code} {r.text}"
        # 6th attempt locked out
        r6 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"email": email, "password": "wrong"})
        assert r6.status_code == 429, r6.text
        # Cleanup
        db.login_attempts.delete_many({})


# ============ Founder ============
@pytest.fixture(scope="session")
def founder_session(db):
    """Login as founder, set up TOTP if needed, return session."""
    db.login_attempts.delete_many({})
    # Reset founder 2FA to make test deterministic
    db.users.update_one({"email": FOUNDER_EMAIL},
                        {"$set": {"twofa_enabled": False, "twofa_method": None},
                         "$unset": {"totp_secret": "", "totp_secret_pending": ""}})

    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": FOUNDER_EMAIL, "password": FOUNDER_PASSWORD})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["stage"] == "2fa_setup_required"
    pre = data["pre_token"]

    r2 = s.post(f"{BASE_URL}/api/auth/2fa/totp/setup", json={"pre_token": pre})
    assert r2.status_code == 200, r2.text
    secret = r2.json()["secret"]
    code = pyotp.TOTP(secret).now()
    r3 = s.post(f"{BASE_URL}/api/auth/2fa/totp/confirm",
                json={"pre_token": pre, "method": "totp", "code": code})
    assert r3.status_code == 200, r3.text
    assert r3.json()["user"]["is_founder"] is True
    return s


class TestFounder:
    def test_founder_me(self, founder_session):
        r = founder_session.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        u = r.json()
        assert u["is_founder"] is True
        assert u["email"] == FOUNDER_EMAIL

    def test_founder_stats(self, founder_session):
        r = founder_session.get(f"{BASE_URL}/api/founder/stats")
        assert r.status_code == 200
        d = r.json()
        for k in ("presale_count", "user_count", "team_members", "ai_messages"):
            assert k in d

    def test_founder_flags_get_and_patch(self, founder_session):
        r = founder_session.get(f"{BASE_URL}/api/founder/feature-flags")
        assert r.status_code == 200
        assert "ai_assistants_enabled" in r.json()
        r2 = founder_session.patch(f"{BASE_URL}/api/founder/feature-flags",
                                   json={"beta_modules_enabled": True})
        assert r2.status_code == 200
        assert r2.json()["beta_modules_enabled"] is True

    def test_founder_presale_signups(self, founder_session):
        r = founder_session.get(f"{BASE_URL}/api/founder/presale-signups")
        assert r.status_code == 200
        assert "signups" in r.json()

    def test_founder_endpoints_block_normal_user(self, state):
        s = state["session"]
        for ep in ("/api/founder/stats", "/api/founder/feature-flags",
                   "/api/founder/presale-signups"):
            r = s.get(f"{BASE_URL}{ep}")
            assert r.status_code == 403, f"{ep}: {r.status_code}"


# ============ Onboarding / Dashboard / Team ============
class TestOnboardingDashboard:
    def test_onboarding_complete(self, state):
        s = state["session"]
        r = s.post(f"{BASE_URL}/api/onboarding/complete", json={
            "company_name": "Test Co", "country": "NL", "industry": "Tech",
            "employees": "1-10", "website": "https://x.test", "first_action": "invoice"
        })
        assert r.status_code == 200, r.text
        # verify persisted
        me = s.get(f"{BASE_URL}/api/auth/me").json()
        assert me["onboarding_completed"] is True
        assert me["company"] == "Test Co"

    def test_dashboard_summary(self, state):
        s = state["session"]
        r = s.get(f"{BASE_URL}/api/dashboard/summary")
        assert r.status_code == 200
        d = r.json()
        for k in ("monthly_revenue", "open_invoices", "active_projects", "team_members"):
            assert k in d["kpis"]
        assert isinstance(d["ai_suggestions"], list) and len(d["ai_suggestions"]) >= 1

    def test_team_list_owner_first(self, state):
        s = state["session"]
        r = s.get(f"{BASE_URL}/api/team/members")
        assert r.status_code == 200
        members = r.json()["members"]
        assert members[0]["is_owner"] is True
        assert members[0]["email"] == state["email"]

    def test_team_invite_and_duplicate(self, state):
        s = state["session"]
        invitee = f"invitee_{uuid.uuid4().hex[:6]}@example.com"
        r = s.post(f"{BASE_URL}/api/team/invite",
                   json={"email": invitee, "role": "Employee"})
        assert r.status_code == 201, r.text
        r2 = s.post(f"{BASE_URL}/api/team/invite",
                    json={"email": invitee, "role": "Employee"})
        assert r2.status_code == 409


# ============ AI Chat ============
class TestAIChat:
    @pytest.mark.parametrize("assistant", ["zynthoro_assist", "zyntha", "thoro", "zyon"])
    def test_ai_chat(self, state, assistant):
        s = state["session"]
        r = s.post(f"{BASE_URL}/api/ai/chat", json={
            "assistant": assistant,
            "message": "Reply with just the word OK."
        }, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["assistant"] == assistant
        assert data["reply"] and isinstance(data["reply"], str)
        assert "session_id" in data
        # save first session for history check
        if assistant == "zynthoro_assist":
            state["ai_session_id"] = data["session_id"]

    def test_ai_history(self, state):
        s = state["session"]
        sid = state.get("ai_session_id")
        assert sid
        r = s.get(f"{BASE_URL}/api/ai/history", params={"session_id": sid})
        assert r.status_code == 200
        msgs = r.json()["messages"]
        # Should contain user + assistant
        assert any(m["role"] == "user" for m in msgs)
        assert any(m["role"] == "assistant" for m in msgs)


# ============ Checkout status ============
class TestCheckout:
    def test_checkout_disabled(self):
        r = requests.get(f"{BASE_URL}/api/checkout/status")
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is False
        assert "june" in d["message"].lower() or "22" in d["message"]
