"""Iteration 18 — Auto-injected company context for AI assistants.

The chat must AUTOMATICALLY inject the user's company + industry + country +
headcount + website + plan into the system prompt. The user never types it,
but the AI demonstrably knows the company from turn 1.

Covers:
  - /api/auth/me returns the company profile fields for the jury demo
  - POST /api/ai/chat with jury -> reply mentions company name + industry
  - POST /api/ai/chat (thoro) -> reply mentions Netherlands
  - POST /api/ai/stream (zyntha SSE) -> stream mentions "Enterprise Advanced" + headcount
  - POST /api/marketing/caption -> returns valid caption + hashtags
  - Non-demo user with empty company profile -> still receives a valid reply (no error)
"""
import os
import re
import json
import uuid
import time
import requests
import pytest

try:
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    load_dotenv("/app/frontend/.env")
except Exception:
    pass

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

JURY_EMAIL = "jury@zynthoro.ai"
JURY_PASSWORD = "ZynthoroDemo2026!"


# ---------- Helpers ----------

def _login_jury():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": JURY_EMAIL, "password": JURY_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("stage") == "ok", body
    return s


def _chat_with_retry(session, payload, retries=2):
    """Call /api/ai/chat once; if reply is empty or unrelated, retry up to
    `retries` extra times (AI replies are non-deterministic)."""
    last_reply = ""
    last_status = None
    for _ in range(retries + 1):
        r = session.post(f"{BASE_URL}/api/ai/chat", json=payload, timeout=60)
        last_status = r.status_code
        if r.status_code != 200:
            time.sleep(1)
            continue
        body = r.json()
        last_reply = body.get("reply", "") or ""
        if last_reply.strip():
            return r.status_code, body, last_reply
        time.sleep(1)
    return last_status, {}, last_reply


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def jury_session():
    return _login_jury()


@pytest.fixture(scope="module")
def jury_me(jury_session):
    r = jury_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ========================================================================
#  TEST 1 — Profile fields are present on /api/auth/me
# ========================================================================
class TestAuthMeCompanyFields:
    def test_jury_me_returns_full_company_profile(self, jury_me):
        # The reviewer spec says these fields MUST be set on the seeded jury
        assert jury_me.get("company") == "Zynthoro Demo Workspace", jury_me.get("company")
        industry = jury_me.get("company_industry") or ""
        assert "AI" in industry or "SaaS" in industry or "ERP" in industry, industry
        assert jury_me.get("company_country") == "Netherlands", jury_me.get("company_country")
        # Headcount can be "10-50" or "10 to 50" — both acceptable
        head = jury_me.get("company_employees") or ""
        assert "10" in head and ("50" in head), head
        website = jury_me.get("company_website") or ""
        assert "zynthoro" in website.lower(), website
        assert jury_me.get("subscription_plan") == "Enterprise Advanced", jury_me.get("subscription_plan")


# ========================================================================
#  TEST 2 — /api/ai/chat injects company + industry into the system prompt
# ========================================================================
class TestChatCompanyInjection:
    def test_chat_knows_company_and_industry(self, jury_session):
        session_id = f"TEST_ctx_{uuid.uuid4().hex[:8]}"
        payload = {
            "assistant": "zynthoro_assist",
            "session_id": session_id,
            "message": "In one short sentence, what company am I and what industry?",
        }
        status, body, reply = _chat_with_retry(jury_session, payload, retries=2)
        assert status == 200, f"status={status} body={body}"
        assert reply, "Empty reply after 3 attempts"
        low = reply.lower()
        # Must mention the company name (or a tight variation)
        assert ("zynthoro demo workspace" in low) or ("zynthoro demo" in low and "workspace" in low), \
            f"Reply did not mention company. Reply='{reply}'"
        # Must mention something about the industry
        assert any(tok in low for tok in ("ai", "saas", "erp", "sme")), \
            f"Reply did not mention industry. Reply='{reply}'"

    def test_thoro_knows_country(self, jury_session):
        session_id = f"TEST_ctx_thoro_{uuid.uuid4().hex[:8]}"
        payload = {
            "assistant": "thoro",
            "session_id": session_id,
            "message": "In one short sentence, what country is my business based in?",
        }
        status, body, reply = _chat_with_retry(jury_session, payload, retries=2)
        assert status == 200, f"status={status} body={body}"
        assert reply, "Empty reply after 3 attempts"
        low = reply.lower()
        assert any(tok in low for tok in ("netherlands", "dutch", "the netherlands", " nl ", " nl.", "(nl)")), \
            f"Reply did not mention Netherlands. Reply='{reply}'"


# ========================================================================
#  TEST 3 — /api/ai/stream (SSE) injects plan + headcount
# ========================================================================
class TestStreamCompanyInjection:
    def _consume_sse(self, session, payload, timeout=60):
        accumulated = []
        last_meta = None
        with session.post(
            f"{BASE_URL}/api/ai/stream",
            json=payload,
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=timeout,
        ) as r:
            assert r.status_code == 200, f"stream status={r.status_code} body={r.text[:300]}"
            cur_event = None
            for raw in r.iter_lines(decode_unicode=True):
                if raw is None:
                    continue
                if raw == "":
                    cur_event = None
                    continue
                if raw.startswith("event: "):
                    cur_event = raw[7:].strip()
                elif raw.startswith("data: "):
                    payload_data = raw[6:]
                    try:
                        data = json.loads(payload_data)
                    except Exception:
                        continue
                    if cur_event == "meta":
                        last_meta = data
                    elif cur_event == "delta":
                        accumulated.append(data.get("content", ""))
                    elif cur_event == "error":
                        return last_meta, "".join(accumulated), data
                    elif cur_event == "done":
                        return last_meta, "".join(accumulated), None
        return last_meta, "".join(accumulated), None

    def test_zyntha_stream_knows_plan_and_headcount(self, jury_session):
        accumulated_full = ""
        err = None
        meta = None
        # Retry up to 3 times (AI is non-deterministic)
        for attempt in range(3):
            session_id = f"TEST_ctx_stream_{uuid.uuid4().hex[:8]}"
            payload = {
                "assistant": "zyntha",
                "session_id": session_id,
                "message": "In one short sentence, what's my Zynthoro subscription plan and what's my company headcount?",
            }
            meta, accumulated_full, err = self._consume_sse(jury_session, payload)
            if err is not None:
                time.sleep(1)
                continue
            if accumulated_full.strip():
                low = accumulated_full.lower()
                has_plan = "enterprise advanced" in low
                # Accept "10-50", "10 to 50", "between 10 and 50", "10 and 50"
                has_head = bool(re.search(r"10\s*(?:-|to|and|–|—|/)\s*50", low)) or ("10-50" in low)
                if has_plan and has_head:
                    return
            time.sleep(1)

        # Final assertion (will fail with the last reply for diagnostics)
        low = accumulated_full.lower()
        assert err is None, f"stream returned error frame: {err}"
        assert accumulated_full.strip(), "stream returned empty content after 3 attempts"
        assert "enterprise advanced" in low, f"Plan missing. Got='{accumulated_full[:400]}'"
        assert (
            bool(re.search(r"10\s*(?:-|to|and|–|—|/)\s*50", low))
            or "10-50" in low
        ), f"Headcount 10-50 missing. Got='{accumulated_full[:400]}'"


# ========================================================================
#  TEST 4 — /api/marketing/caption tailored to industry
# ========================================================================
class TestCaptionWithContext:
    def test_caption_returns_caption_and_hashtags(self, jury_session):
        payload = {
            "idea": "Quick win for our customers",
            "platform": "instagram",
        }
        r = jury_session.post(f"{BASE_URL}/api/marketing/caption", json=payload, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        caption = body.get("caption") or ""
        hashtags = body.get("hashtags") or []
        assert isinstance(caption, str)
        assert caption.strip(), f"Empty caption. body={body}"
        assert isinstance(hashtags, list)
        # Reviewer said 0+ hashtags is fine — just confirm the field is a list
        assert all(isinstance(t, str) for t in hashtags)
        # Provider and badge should come back
        assert body.get("provider") == "gemini"
        assert body.get("badge", "").startswith("Generated by Zyntha"), body.get("badge")


# ========================================================================
#  TEST 5 — Empty-profile user still gets a clean reply (graceful skip)
# ========================================================================
class TestEmptyProfileGraceful:
    """A brand-new user whose company fields are empty/missing must still
    receive a valid AI reply — the context block is only injected if data
    exists; empty fields are skipped without errors."""

    def test_fresh_user_chat_does_not_500(self):
        # Create a new user, verify, log in (need to handle 2FA setup gate).
        em = f"TEST_ctx_empty_{uuid.uuid4().hex[:10]}@example.com"
        pw = "EmptyCtx2026!"
        s = requests.Session()
        r = s.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "first_name": "Empty", "last_name": "Profile",
                "email": em, "password": pw, "company": "EmptyCo",
            },
            timeout=20,
        )
        assert r.status_code == 201, r.text
        sb = r.json()
        user_id = sb.get("user_id")
        # Verify email
        tok = sb.get("dev_verification_token")
        if not tok:
            # Read from MongoDB
            from motor.motor_asyncio import AsyncIOMotorClient
            import asyncio

            async def _read():
                c = AsyncIOMotorClient(os.environ["MONGO_URL"])
                db = c[os.environ["DB_NAME"]]
                u = await db.users.find_one({"id": user_id})
                c.close()
                return (u or {}).get("verification_token")
            tok = asyncio.run(_read())
        assert tok, "no verification token available"
        v = s.get(f"{BASE_URL}/api/auth/verify-email", params={"token": tok}, timeout=20)
        assert v.status_code in (200, 302), v.text

        # Login → will get 2fa_setup_required; force-clear that gate via DB
        # so we can call /api/ai/chat as an authenticated user.
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio

        async def _force_no_2fa():
            c = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = c[os.environ["DB_NAME"]]
            await db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "twofa_enabled": False,
                    "require_2fa_setup": False,
                    "onboarding_completed": True,
                    "email_verified": True,
                    # is_demo bypasses the 2FA setup gate at login (server.py:456)
                    # so we can call /api/ai/chat as an authenticated user.
                    "is_demo": True,
                    # Force-clear ALL the context fields the reviewer cares about
                    "company": "",
                    "company_industry": "",
                    "company_country": "",
                    "company_employees": "",
                    "company_website": "",
                }},
            )
            c.close()
        asyncio.run(_force_no_2fa())

        # Now login should give stage='ok' (or at least a session cookie)
        login = s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": em, "password": pw},
            timeout=20,
        )
        assert login.status_code == 200, login.text
        body = login.json()
        if body.get("stage") != "ok":
            pytest.skip(f"Could not bypass 2FA for fresh user (stage={body.get('stage')}). "
                        f"Empty-profile graceful test requires unauthenticated path which isn't supported.")
        # Confirm /api/auth/me has empty company fields
        me = s.get(f"{BASE_URL}/api/auth/me", timeout=15).json()
        # All context fields should be empty after force-clear
        assert not (me.get("company") or ""), me.get("company")
        assert not (me.get("company_industry") or ""), me.get("company_industry")
        assert not (me.get("company_country") or ""), me.get("company_country")

        # Call /api/ai/chat — must NOT 500
        payload = {
            "assistant": "zynthoro_assist",
            "message": "Say hi in one short sentence.",
        }
        status, rb, reply = _chat_with_retry(s, payload, retries=1)
        assert status == 200, f"empty-profile chat failed: status={status} body={rb}"
        assert reply.strip(), "empty-profile chat returned empty reply"
