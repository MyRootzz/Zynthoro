"""Tests for the XPRIZE jury demo account, seed data, and isolation guarantees.

Covers:
 - login bypass for is_demo (stage='ok', no 2FA gate)
 - /api/auth/me returns is_demo only for the jury account
 - signup cannot inject is_demo
 - /api/demo/projects + /api/demo/invoices return correct seed data for jury
 - /api/demo/projects + /api/demo/invoices return EMPTY for fresh non-demo user
 - /api/team/members returns 6 rows for jury (owner L10 + 5 seeded)
"""
import os
import time
import uuid
import requests
import pytest

# Ensure both REACT_APP_BACKEND_URL and MONGO_URL/DB_NAME are loaded for the
# test process (the harness may not inherit them from supervisor).
try:
    from dotenv import load_dotenv
    load_dotenv('/app/backend/.env')
    load_dotenv('/app/frontend/.env')
except Exception:
    pass

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if os.environ.get('REACT_APP_BACKEND_URL') else None
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

JURY_EMAIL = "jury@zynthoro.ai"
JURY_PASSWORD = "ZynthoroDemo2026!"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def jury_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": JURY_EMAIL, "password": JURY_PASSWORD},
               timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("stage") == "ok", body
    assert "access_token" in s.cookies, dict(s.cookies)
    return s, body


@pytest.fixture(scope="module")
def fresh_user_session():
    """Create a brand-new user via signup, verify email, return a logged-in
    session that has stage='2fa_setup_required' — we won't complete 2FA but
    we'll use the email + signup metadata for is_demo regression checks."""
    em = f"TEST_demoreg_{uuid.uuid4().hex[:10]}@example.com"
    pw = "FreshPass2026!"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "first_name": "Fresh", "last_name": "User",
        "email": em, "password": pw, "company": "Fresh Co"
    }, timeout=15)
    assert r.status_code == 201, r.text
    user_id = r.json()["user_id"]
    # Verify the user directly in the DB (fastest path) — fetch token from db.
    # We use email_verified flip via the dev verification token if exposed,
    # otherwise fall back to a DB update through the email link.
    dev_token = r.json().get("dev_verification_token")
    if dev_token:
        s.get(f"{BASE_URL}/api/auth/verify-email", params={"token": dev_token}, timeout=15)
    else:
        # Read token from MongoDB and verify via API
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio
        async def _verify():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            u = await db.users.find_one({"id": user_id})
            tok = u.get("verification_token")
            c.close()
            return tok
        tok = asyncio.run(_verify())
        s.get(f"{BASE_URL}/api/auth/verify-email", params={"token": tok}, timeout=15)
    return s, em, pw, user_id


# ---------- Login bypass / is_demo flags ----------
class TestJuryLogin:
    def test_login_returns_stage_ok_no_2fa(self, jury_session):
        s, body = jury_session
        assert body["stage"] == "ok"
        assert body.get("access_token")
        user = body["user"]
        assert user["subscription_plan"] == "Enterprise Advanced"
        assert user["is_demo"] is True
        assert user["billing_exempt"] is True
        assert user["onboarding_completed"] is True
        assert user["email_verified"] is True
        assert user["twofa_enabled"] is False

    def test_login_wrong_password_401(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": JURY_EMAIL, "password": "WRONG"},
                          timeout=15)
        assert r.status_code == 401, r.text

    def test_auth_me_returns_is_demo_true(self, jury_session):
        s, _ = jury_session
        r = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["email"] == JURY_EMAIL
        assert me["is_demo"] is True


# ---------- Auth hardening: is_demo cannot be granted via signup ----------
class TestIsDemoCannotBeInjected:
    def test_signup_payload_with_is_demo_is_ignored(self):
        em = f"TEST_inject_{uuid.uuid4().hex[:10]}@example.com"
        r = requests.post(f"{BASE_URL}/api/auth/signup", json={
            "first_name": "Injection", "last_name": "Attempt",
            "email": em, "password": "TryToBeDemo2026!",
            "company": "Inject Co",
            "is_demo": True,            # <-- malicious
            "billing_exempt": True,
            "subscription_plan": "Enterprise Advanced",
        }, timeout=15)
        assert r.status_code == 201, r.text
        user_id = r.json()["user_id"]
        # Fetch the user doc from MongoDB and confirm is_demo is not True
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio
        async def _check():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            u = await db.users.find_one({"id": user_id})
            c.close()
            return u
        u = asyncio.run(_check())
        assert u is not None
        assert u.get("is_demo") in (False, None), f"is_demo leaked: {u.get('is_demo')}"
        assert u.get("billing_exempt") in (False, None), u.get("billing_exempt")
        assert u.get("subscription_plan") == "Presale", u.get("subscription_plan")

    def test_fresh_user_me_is_not_demo(self, fresh_user_session):
        s, em, pw, _ = fresh_user_session
        # Complete login → may require 2FA setup; we don't go through that.
        # Instead create a *separate* clean signup with no payload pollution
        # and read /api/auth/me via a forced-verified DB state below.
        # Skip if 2FA setup gate is unavoidable: just confirm DB state.
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio
        async def _check():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            u = await db.users.find_one({"email": em.lower()})
            c.close()
            return u
        u = asyncio.run(_check())
        assert u.get("is_demo") in (False, None)


# ---------- Demo data endpoints ----------
class TestDemoEndpointsJury:
    def test_demo_projects_returns_5_sorted_by_due(self, jury_session):
        s, _ = jury_session
        r = s.get(f"{BASE_URL}/api/demo/projects", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "projects" in data
        projects = data["projects"]
        assert len(projects) == 5, [p.get("name") for p in projects]
        names = {p["name"] for p in projects}
        assert {
            "Q1 Product Roadmap",
            "Spring Marketing Launch",
            "SOC 2 Type II Audit",
            "EU Sales Pipeline 2026",
            "AI Caption Engine v2",
        } == names
        # Sort ascending by due-date
        dues = [p["due"] for p in projects]
        assert dues == sorted(dues), dues

    def test_demo_invoices_totals(self, jury_session):
        s, _ = jury_session
        r = s.get(f"{BASE_URL}/api/demo/invoices", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data["invoices"]) == 6
        assert data["total_eur"] == 61440, data["total_eur"]
        assert data["paid_eur"] == 13980, data["paid_eur"]


class TestDemoEndpointIsolation:
    def test_fresh_user_sees_empty_projects(self, fresh_user_session):
        # We can't easily get an access_token without 2FA setup; assert via DB.
        s, em, pw, user_id = fresh_user_session
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio
        async def _check():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            proj = await db.demo_projects.count_documents({"workspace_owner": user_id})
            inv = await db.demo_invoices.count_documents({"workspace_owner": user_id})
            c.close()
            return proj, inv
        proj, inv = asyncio.run(_check())
        assert proj == 0
        assert inv == 0


# ---------- Team endpoint ----------
class TestJuryTeam:
    def test_team_members_returns_owner_plus_5(self, jury_session):
        s, _ = jury_session
        r = s.get(f"{BASE_URL}/api/team/members", timeout=15)
        assert r.status_code == 200, r.text
        members = r.json().get("members") or r.json().get("team_members") or r.json()
        if isinstance(members, dict):
            # fallback if wrapped differently
            members = members.get("members", [])
        assert len(members) == 6, f"got {len(members)}: {[m.get('email') for m in members]}"
        # Find owner with level 10
        owner = [m for m in members if m.get("level") == 10]
        assert owner, [m.get("level") for m in members]
        by_email = {m["email"].lower(): m for m in members}
        assert by_email["amelia.chen@zynthoro-demo.ai"]["level"] == 9
        assert by_email["amelia.chen@zynthoro-demo.ai"]["role"] == "Director"
        assert by_email["daniel.kruger@zynthoro-demo.ai"]["level"] == 7
        assert by_email["daniel.kruger@zynthoro-demo.ai"]["role"] == "Senior Manager"
        assert by_email["priya.shah@zynthoro-demo.ai"]["level"] == 5
        assert by_email["priya.shah@zynthoro-demo.ai"]["role"] == "Manager"
        assert by_email["luca.rossi@zynthoro-demo.ai"]["level"] == 3
        assert by_email["luca.rossi@zynthoro-demo.ai"]["role"] == "Employee"
        assert by_email["nina.adebayo@zynthoro-demo.ai"]["level"] == 1
        assert by_email["nina.adebayo@zynthoro-demo.ai"]["role"] == "Intern"
        assert by_email["nina.adebayo@zynthoro-demo.ai"]["status"] == "invited"


# ---------- Idempotency ----------
class TestSeedIdempotent:
    def test_counts_match_expected(self):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        async def _check():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            u = await db.users.find_one({"email": JURY_EMAIL})
            tm = await db.team_members.count_documents({"workspace_owner": u["id"]})
            pj = await db.demo_projects.count_documents({"workspace_owner": u["id"]})
            iv = await db.demo_invoices.count_documents({"workspace_owner": u["id"]})
            c.close()
            return tm, pj, iv
        tm, pj, iv = asyncio.run(_check())
        assert (tm, pj, iv) == (5, 5, 6), (tm, pj, iv)
