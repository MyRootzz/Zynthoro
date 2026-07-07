"""Iteration 23 — Canva integration + 12-module smoke test.

Verifies:
- New Canva Connect endpoints (auth, status, connect URL, error callback, disconnect, unauth guards)
- All 12 module pages backend readiness (operations recipes endpoint, marketing caption LLM)
- AI chat smoke, dashboard summary regression, jury login.
"""
import os
import re
import requests
from urllib.parse import urlparse, parse_qs

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://zynthoro-foundation.preview.emergentagent.com").rstrip("/")
JURY_EMAIL = "jury@zynthoro.ai"
JURY_PASSWORD = "ZynthoroDemo2026!"


# --- Auth helper ---
def _jury_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": JURY_EMAIL, "password": JURY_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"jury login failed {r.status_code}: {r.text[:300]}"
    data = r.json()
    # jury has 2FA disabled → should return access_token or set cookie directly
    tok = data.get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s, data


# ===== AUTH regression =====
def test_jury_login_direct():
    s, data = _jury_session()
    assert data.get("stage") in (None, "success", "authenticated") or "access_token" in data, \
        f"jury login unexpected stage: {data}"


def test_auth_me():
    s, _ = _jury_session()
    r = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 200
    me = r.json()
    assert me.get("email") == JURY_EMAIL
    assert me.get("is_demo") is True


def test_dashboard_summary():
    s, _ = _jury_session()
    r = s.get(f"{BASE_URL}/api/dashboard/summary", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


# ===== CANVA =====
class TestCanva:
    def test_status_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/canva/status", timeout=15)
        assert r.status_code == 401, f"expected 401, got {r.status_code}"

    def test_connect_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/canva/connect", timeout=15)
        assert r.status_code == 401

    def test_designs_get_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/canva/designs", timeout=15)
        assert r.status_code == 401

    def test_designs_post_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/canva/designs", json={"preset": "doc"}, timeout=15)
        assert r.status_code == 401

    def test_disconnect_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/canva/disconnect", timeout=15)
        assert r.status_code == 401

    def test_status_configured_not_connected(self):
        s, _ = _jury_session()
        # start clean
        s.post(f"{BASE_URL}/api/canva/disconnect", timeout=15)
        r = s.get(f"{BASE_URL}/api/canva/status", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("configured") is True, f"canva not configured: {d}"
        assert d.get("connected") is False

    def test_connect_returns_valid_authorize_url(self):
        s, _ = _jury_session()
        r = s.get(f"{BASE_URL}/api/canva/connect", timeout=15)
        assert r.status_code == 200
        url = r.json().get("url", "")
        assert "www.canva.com/api/oauth/authorize" in url, f"bad url: {url}"
        parsed = urlparse(url)
        q = parse_qs(parsed.query)
        assert q.get("client_id"), "client_id missing"
        redir = q.get("redirect_uri", [""])[0]
        assert redir.endswith("/api/canva/callback"), f"bad redirect_uri: {redir}"
        assert q.get("response_type", [""])[0] == "code"
        assert q.get("code_challenge_method", [""])[0] == "S256"
        assert q.get("code_challenge"), "code_challenge missing"
        assert q.get("state"), "state missing"

    def test_callback_error_redirects(self):
        r = requests.get(f"{BASE_URL}/api/canva/callback?error=access_denied",
                         allow_redirects=False, timeout=15)
        assert r.status_code in (302, 307)
        loc = r.headers.get("location", "")
        assert "canva=error" in loc, f"loc: {loc}"
        assert "/dashboard/marketing" in loc

    def test_callback_invalid_state_redirects(self):
        r = requests.get(f"{BASE_URL}/api/canva/callback?code=fakecode&state=NOTREAL",
                         allow_redirects=False, timeout=15)
        assert r.status_code in (302, 307)
        assert "canva=error" in r.headers.get("location", "")

    def test_designs_get_when_not_connected(self):
        s, _ = _jury_session()
        s.post(f"{BASE_URL}/api/canva/disconnect", timeout=15)
        r = s.get(f"{BASE_URL}/api/canva/designs", timeout=15)
        assert r.status_code == 400
        assert "not connected" in (r.json().get("detail", "").lower())

    def test_designs_post_when_not_connected(self):
        s, _ = _jury_session()
        s.post(f"{BASE_URL}/api/canva/disconnect", timeout=15)
        r = s.post(f"{BASE_URL}/api/canva/designs",
                   json={"preset": "presentation", "title": "TEST_zynthoro"}, timeout=15)
        assert r.status_code == 400

    def test_disconnect_ok(self):
        s, _ = _jury_session()
        r = s.post(f"{BASE_URL}/api/canva/disconnect", timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ===== MODULE 9: Operations backend =====
def test_operations_endpoint():
    s, _ = _jury_session()
    # try common ops endpoints
    tried = []
    for path in ("/api/operations/recipes", "/api/operations/bom", "/api/operations/production"):
        r = s.get(f"{BASE_URL}{path}", timeout=15)
        tried.append((path, r.status_code))
        if r.status_code == 200:
            return
    raise AssertionError(f"no operations endpoint returned 200: {tried}")


# ===== MODULE 10: Marketing caption (LLM) =====
def test_marketing_caption_llm():
    s, _ = _jury_session()
    r = s.post(f"{BASE_URL}/api/marketing/caption",
               json={"idea": "Launching new AI dashboard for SMBs", "platform": "linkedin"},
               timeout=45)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    # response should include caption text and hashtags in some form
    text = (data.get("caption") or "") + " " + str(data.get("hashtags") or "")
    assert len(text.strip()) > 5


# ===== AI chat smoke =====
def test_ai_chat_smoke():
    s, _ = _jury_session()
    r = s.post(f"{BASE_URL}/api/ai/chat",
               json={"assistant": "zyntha", "message": "Say hi in 5 words."},
               timeout=60)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    reply = data.get("reply") or data.get("message") or data.get("content") or ""
    assert isinstance(reply, str) and len(reply) > 0
