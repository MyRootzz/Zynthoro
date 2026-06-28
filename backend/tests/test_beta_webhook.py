"""Backend tests for the Beta signup webhook notifier feature.

Covers (per review_request iteration_21):
- GET  /api/founder/feature-flags includes 'beta_webhook_url' (default '').
- PATCH /api/founder/feature-flags persists beta_webhook_url + GET reflects it.
- POST /api/founder/beta-webhook/test:
    * 400 when no URL configured
    * 200 + {sent: false, kind: 'slack'} with obviously-fake Slack URL
    * 403 when called by a non-founder
- webhook_notifier module:
    * _detect_kind() for slack / discord / generic
    * _format() shapes: Slack Block Kit, Discord embeds, Generic JSON
    * send() with empty URL returns False without raising or network call
"""
import os
import sys
import asyncio
from unittest.mock import patch, AsyncMock

import pyotp
import pytest
import requests
from pymongo import MongoClient

# Make /app/backend importable for direct module tests
sys.path.insert(0, "/app/backend")

import webhook_notifier  # noqa: E402

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or
            "https://zynthoro-foundation.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

FOUNDER_EMAIL = "regie@myrootzz.com"
FOUNDER_PASSWORD = "Zynthoro2026!"

JURY_EMAIL = "jury@zynthoro.ai"
JURY_PASSWORD = "ZynthoroDemo2026!"


def _mongo_db():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "test_database")]


# ---------- auth helpers ----------
def _login_with_totp(email: str, password: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    db = _mongo_db()
    user = db.users.find_one({"email": email})
    if not user:
        pytest.skip(f"User {email} missing in DB")

    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed {r.status_code}: {r.text}"
    body = r.json()
    stage = body.get("stage")

    if stage == "ok":
        token = body.get("token") or body.get("access_token")
        # If no token in body, cookies are sufficient (httpOnly access_token)
        if not token and "access_token" not in s.cookies:
            pytest.fail(f"Login ok but no token or cookie: {body}")
    elif stage == "2fa_required":
        pre_token = body["pre_token"]
        method = (body.get("methods") or ["totp"])[0]
        if method == "totp":
            secret = user.get("totp_secret")
            assert secret, "TOTP enabled but no secret on user doc"
            code = pyotp.TOTP(secret).now()
            r2 = s.post(f"{API}/auth/2fa/verify",
                        json={"pre_token": pre_token, "method": "totp", "code": code})
            assert r2.status_code == 200, f"2FA verify failed: {r2.text}"
            token = r2.json()["token"]
        else:
            pytest.skip(f"Unexpected 2FA method: {method}")
    elif stage == "2fa_setup_required":
        pytest.skip("User requires 2FA setup — out of scope for this test")
    else:
        pytest.fail(f"Unexpected login stage: {body}")

    s.headers.update({"Content-Type": "application/json"})
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def founder():
    return _login_with_totp(FOUNDER_EMAIL, FOUNDER_PASSWORD)


@pytest.fixture(scope="module")
def jury():
    return _login_with_totp(JURY_EMAIL, JURY_PASSWORD)


@pytest.fixture(scope="module", autouse=True)
def restore_original_webhook_url(founder):
    """Snapshot beta_webhook_url before tests, restore after."""
    r = founder.get(f"{API}/founder/feature-flags")
    original = ""
    if r.status_code == 200:
        original = (r.json() or {}).get("beta_webhook_url") or ""
    yield
    founder.patch(f"{API}/founder/feature-flags",
                  json={"beta_webhook_url": original})


# ==================== Feature flags GET/PATCH ====================
class TestFeatureFlagsBetaWebhookField:
    def test_get_feature_flags_includes_beta_webhook_url(self, founder):
        r = founder.get(f"{API}/founder/feature-flags")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "beta_webhook_url" in data, f"key missing in response: {data}"
        assert isinstance(data["beta_webhook_url"], str)

    def test_patch_feature_flags_persists_beta_webhook_url(self, founder):
        target = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
        r = founder.patch(f"{API}/founder/feature-flags",
                          json={"beta_webhook_url": target})
        assert r.status_code == 200, r.text
        assert r.json().get("beta_webhook_url") == target

        # Re-GET to verify persistence
        r2 = founder.get(f"{API}/founder/feature-flags")
        assert r2.status_code == 200
        assert r2.json().get("beta_webhook_url") == target


# ==================== POST /founder/beta-webhook/test ====================
class TestBetaWebhookTestEndpoint:
    def test_test_endpoint_400_when_no_url(self, founder):
        # Clear URL first
        founder.patch(f"{API}/founder/feature-flags",
                      json={"beta_webhook_url": ""})
        r = founder.post(f"{API}/founder/beta-webhook/test")
        assert r.status_code == 400, r.text
        assert "No webhook URL configured" in r.text

    def test_test_endpoint_returns_sent_false_kind_slack_for_fake_url(self, founder):
        fake = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
        founder.patch(f"{API}/founder/feature-flags",
                      json={"beta_webhook_url": fake})
        r = founder.post(f"{API}/founder/beta-webhook/test")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("kind") == "slack"
        assert body.get("sent") is False, f"expected sent=False for fake URL, got {body}"

    def test_test_endpoint_detects_discord_kind(self, founder):
        fake = "https://discord.com/api/webhooks/0000000000/totally-fake-token-abc"
        founder.patch(f"{API}/founder/feature-flags",
                      json={"beta_webhook_url": fake})
        r = founder.post(f"{API}/founder/beta-webhook/test")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("kind") == "discord"

    def test_test_endpoint_detects_generic_kind(self, founder):
        fake = "https://example.com/webhooks/fake-endpoint"
        founder.patch(f"{API}/founder/feature-flags",
                      json={"beta_webhook_url": fake})
        r = founder.post(f"{API}/founder/beta-webhook/test")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("kind") == "generic"

    def test_test_endpoint_403_for_non_founder(self, jury):
        r = jury.post(f"{API}/founder/beta-webhook/test")
        assert r.status_code == 403, f"Expected 403 for non-founder, got {r.status_code}: {r.text}"

    def test_feature_flags_patch_403_for_non_founder(self, jury):
        r = jury.patch(f"{API}/founder/feature-flags",
                       json={"beta_webhook_url": "https://hooks.slack.com/x"})
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"


# ==================== webhook_notifier module unit tests ====================
class TestWebhookNotifierModule:
    def test_detect_kind_slack(self):
        assert webhook_notifier._detect_kind(
            "https://hooks.slack.com/services/T/B/X"
        ) == "slack"

    def test_detect_kind_discord(self):
        assert webhook_notifier._detect_kind(
            "https://discord.com/api/webhooks/123/abc"
        ) == "discord"
        assert webhook_notifier._detect_kind(
            "https://discordapp.com/api/webhooks/1/2"
        ) == "discord"

    def test_detect_kind_generic(self):
        assert webhook_notifier._detect_kind("https://example.com/hook") == "generic"
        assert webhook_notifier._detect_kind("") == "generic"
        assert webhook_notifier._detect_kind(None) == "generic"

    def test_format_slack_block_kit(self):
        payload = webhook_notifier._format(
            "slack", "Title!", "Body line", {"Plan": "Beta", "Country": "PT"}
        )
        assert "blocks" in payload and isinstance(payload["blocks"], list)
        assert payload.get("text") == "Title!"
        # header block
        assert payload["blocks"][0]["type"] == "header"
        assert payload["blocks"][0]["text"]["text"] == "Title!"
        # section with body
        assert payload["blocks"][1]["type"] == "section"
        assert payload["blocks"][1]["text"]["text"] == "Body line"
        # fields appended
        assert any(b.get("type") == "section" and "fields" in b for b in payload["blocks"])

    def test_format_discord_embeds(self):
        payload = webhook_notifier._format(
            "discord", "Title", "Body", {"Plan": "Beta"}
        )
        assert "embeds" in payload
        assert isinstance(payload["embeds"], list) and len(payload["embeds"]) == 1
        embed = payload["embeds"][0]
        assert embed["title"] == "Title"
        assert embed["description"] == "Body"
        assert "color" in embed
        assert isinstance(embed.get("fields"), list)
        assert embed["fields"][0]["name"] == "Plan"
        assert embed["fields"][0]["value"] == "Beta"

    def test_format_generic_json(self):
        payload = webhook_notifier._format(
            "generic", "Title", "Body", {"a": "b"}
        )
        assert payload == {"title": "Title", "body": "Body", "fields": {"a": "b"}}

    def test_send_empty_url_returns_false_no_network(self):
        # If httpx is invoked, this will raise — proving no network call happened
        with patch("webhook_notifier.httpx.AsyncClient") as mock_client:
            result = asyncio.run(webhook_notifier.send("", "t", "b", {}))
            assert result is False
            mock_client.assert_not_called()

        # None URL
        with patch("webhook_notifier.httpx.AsyncClient") as mock_client:
            result = asyncio.run(webhook_notifier.send(None, "t", "b", {}))  # type: ignore[arg-type]
            assert result is False
            mock_client.assert_not_called()

    def test_send_posts_correct_slack_payload_shape(self):
        """Patch AsyncClient.post and verify Slack payload structure is sent."""
        captured = {}

        class _FakeResp:
            status_code = 200
            text = "ok"

        class _FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, json=None):
                captured["url"] = url
                captured["json"] = json
                return _FakeResp()

        with patch("webhook_notifier.httpx.AsyncClient", _FakeClient):
            ok = asyncio.run(webhook_notifier.send(
                "https://hooks.slack.com/services/T/B/X",
                "Hello", "World", {"k": "v"},
            ))
        assert ok is True
        assert "blocks" in captured["json"]
        assert captured["json"]["text"] == "Hello"

    def test_send_posts_correct_discord_payload_shape(self):
        captured = {}

        class _FakeResp:
            status_code = 204
            text = ""

        class _FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, json=None):
                captured["url"] = url
                captured["json"] = json
                return _FakeResp()

        with patch("webhook_notifier.httpx.AsyncClient", _FakeClient):
            ok = asyncio.run(webhook_notifier.send(
                "https://discord.com/api/webhooks/1/2",
                "Hello", "World", {"k": "v"},
            ))
        # 204 is 2xx — should be considered success
        assert ok is True
        assert "embeds" in captured["json"]
        assert captured["json"]["embeds"][0]["title"] == "Hello"

    def test_send_returns_false_on_non_2xx_without_raising(self):
        class _FakeResp:
            status_code = 500
            text = "boom"

        class _FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, json=None):
                return _FakeResp()

        with patch("webhook_notifier.httpx.AsyncClient", _FakeClient):
            ok = asyncio.run(webhook_notifier.send(
                "https://example.com/x", "t", "b", {},
            ))
        assert ok is False

    def test_send_swallows_exceptions(self):
        class _ExplodingClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): raise RuntimeError("nope")
            async def __aexit__(self, *a): return False

        with patch("webhook_notifier.httpx.AsyncClient", _ExplodingClient):
            ok = asyncio.run(webhook_notifier.send(
                "https://example.com/x", "t", "b", {},
            ))
        assert ok is False  # never raises
