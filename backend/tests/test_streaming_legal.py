"""Phase 3 tests: SSE streaming AI, system prompt fixes, history persistence."""
import json
import os
import re
import time
import uuid

import pyotp
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
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
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="session")
def founder_session(db):
    """Login as founder via TOTP reset path."""
    db.login_attempts.delete_many({})
    db.users.update_one(
        {"email": FOUNDER_EMAIL},
        {"$set": {"twofa_enabled": False, "twofa_method": None},
         "$unset": {"totp_secret": "", "totp_secret_pending": ""}},
    )
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": FOUNDER_EMAIL, "password": FOUNDER_PASSWORD})
    assert r.status_code == 200, r.text
    pre = r.json()["pre_token"]
    r2 = s.post(f"{BASE_URL}/api/auth/2fa/totp/setup", json={"pre_token": pre})
    assert r2.status_code == 200, r2.text
    secret = r2.json()["secret"]
    code = pyotp.TOTP(secret).now()
    r3 = s.post(f"{BASE_URL}/api/auth/2fa/totp/confirm",
                json={"pre_token": pre, "method": "totp", "code": code})
    assert r3.status_code == 200, r3.text
    return s


def _parse_sse(raw_text):
    """Parse SSE text into list of (event, data_dict)."""
    frames = []
    cur_event = None
    cur_data = []
    for line in raw_text.split("\n"):
        if line.startswith("event:"):
            cur_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            cur_data.append(line.split(":", 1)[1].strip())
        elif line == "" and cur_event is not None:
            data_raw = "\n".join(cur_data)
            try:
                data = json.loads(data_raw) if data_raw else {}
            except json.JSONDecodeError:
                data = {"_raw": data_raw}
            frames.append((cur_event, data))
            cur_event = None
            cur_data = []
    return frames


def _stream(session, assistant, message, session_id=None, timeout=180):
    payload = {"assistant": assistant, "message": message}
    if session_id:
        payload["session_id"] = session_id
    r = session.post(
        f"{BASE_URL}/api/ai/stream",
        json=payload,
        headers={"Accept": "text/event-stream"},
        stream=True,
        timeout=timeout,
    )
    return r


# ============ SSE Streaming ============
class TestSSEStreaming:
    @pytest.mark.parametrize("assistant", ["zynthoro_assist", "zyntha", "thoro", "zyona"])
    def test_stream_shape(self, founder_session, assistant, db):
        r = _stream(founder_session, assistant, "Reply with: OK then 5 short tips. Keep it brief.")
        assert r.status_code == 200, r.text[:500]
        # Headers
        ct = r.headers.get("content-type", "")
        assert "text/event-stream" in ct, ct
        # X-Accel-Buffering is set in backend code but may be stripped by edge proxy

        body = r.text  # full body read
        frames = _parse_sse(body)
        events = [e for e, _ in frames]
        assert "meta" in events, f"no meta frame, got {events[:5]}"
        assert events.count("delta") >= 1, f"no delta frames, got {events}"
        assert events[-1] == "done", f"last frame {events[-1]}"

        # meta payload
        meta = next(d for e, d in frames if e == "meta")
        for k in ("provider", "model", "badge", "session_id", "assistant"):
            assert k in meta, f"meta missing {k}: {meta}"
        assert meta["assistant"] == assistant

        # assemble reply
        reply = "".join(d.get("content", "") for e, d in frames if e == "delta")
        assert len(reply) > 5, f"reply too short: {reply!r}"

        # done frame
        done = next(d for e, d in frames if e == "done")
        assert "latency_ms" in done and "chars" in done

    def test_stream_long_form_not_truncated(self, founder_session, db):
        """Verify max_tokens raised to 4000 — long output exceeds 900 chars."""
        prompt = (
            "Write a detailed 1000-word strategic growth plan for a Dutch SaaS company "
            "selling project management software to small businesses. Include sections "
            "for market positioning, pricing strategy, go-to-market channels, content "
            "marketing, partnerships, and metrics. Be thorough."
        )
        r = _stream(founder_session, "zyona", prompt, timeout=240)
        assert r.status_code == 200
        frames = _parse_sse(r.text)
        reply = "".join(d.get("content", "") for e, d in frames if e == "delta")
        assert len(reply) > 900, f"reply too short ({len(reply)} chars) — max_tokens likely not 4000"

    def test_stream_persists_history(self, founder_session, db):
        sid = f"founder:zyntha:{uuid.uuid4()}"
        marker = f"TEST_MARKER_{uuid.uuid4().hex[:8]}"
        r = _stream(founder_session, "zyntha",
                    f"Say the word '{marker}' once and nothing else.",
                    session_id=sid)
        assert r.status_code == 200
        frames = _parse_sse(r.text)
        reply = "".join(d.get("content", "") for e, d in frames if e == "delta")
        assert len(reply) > 0

        # Allow async persistence
        time.sleep(1.5)

        # GET history endpoint
        h = founder_session.get(f"{BASE_URL}/api/ai/history", params={"session_id": sid})
        assert h.status_code == 200, h.text
        msgs = h.json()["messages"]
        assert any(m["role"] == "user" and marker in m["content"] for m in msgs), msgs
        assert any(m["role"] == "assistant" and len(m["content"]) > 0 for m in msgs), msgs

        # ai_logs row written
        log = db.ai_logs.find_one({"session_id": sid})
        assert log is not None
        assert log.get("status") == "ok"


# ============ System Prompt Fixes ============
class TestPromptFixes:
    def test_thoro_recommends_zynthoro_not_shopify(self, founder_session):
        r = _stream(founder_session, "thoro",
                    "How do I sell shoes online? Recommend the best approach.")
        assert r.status_code == 200
        frames = _parse_sse(r.text)
        reply = "".join(d.get("content", "") for e, d in frames if e == "delta").lower()

        # Must mention Zynthoro features
        zynthoro_hits = sum(1 for kw in (
            "zynthoro", "sales admin", "invoicing", "marketing", "content"
        ) if kw in reply)
        assert zynthoro_hits >= 1, f"Thoro didn't mention Zynthoro features:\n{reply[:800]}"

        # External tools must NOT be recommended as primary
        # Allow brief mention but not primary recommendation
        forbidden = ["shopify", "woocommerce", "bigcommerce", "wix", "squarespace"]
        found = [w for w in forbidden if w in reply]
        assert not found, f"Thoro recommended external tools: {found}\n{reply[:800]}"

    def test_zyona_only_real_assistants(self, founder_session):
        r = _stream(founder_session, "zyona",
                    "Which AI assistants should I use to grow my business? "
                    "List the assistants by name.")
        assert r.status_code == 200
        frames = _parse_sse(r.text)
        reply = "".join(d.get("content", "") for e, d in frames if e == "delta").lower()

        # Must mention real ones
        assert "zyntha" in reply or "thoro" in reply or "zyona" in reply or "assist" in reply, reply[:600]

        # Fake names must not appear
        fake_names = ["lexara", "finara", "creova", "marketa", "operea",
                      "legara", "salesa", "hrova", "procura", "brandara", "insighta"]
        found_fake = [n for n in fake_names if n in reply]
        assert not found_fake, f"Zyona invented fake assistants: {found_fake}\n{reply[:800]}"


# ============ Non-streaming regression ============
class TestRegressionChat:
    def test_chat_endpoint_still_works(self, founder_session):
        r = founder_session.post(f"{BASE_URL}/api/ai/chat", json={
            "assistant": "zynthoro_assist",
            "message": "Reply with just OK."
        }, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["reply"] and d["assistant"] == "zynthoro_assist"
        assert "session_id" in d
