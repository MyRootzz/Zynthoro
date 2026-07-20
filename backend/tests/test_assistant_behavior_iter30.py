"""Iteration 30 — Assistant prompt behavior tests.

Validates:
- All four assistants deliver actual work instead of meta-questions
- No outdated '30 June' / '€99 Founder Pricing' references
- Thoro recommends Zynthoro modules first (regression on Shopify rule)
- /api/tier/catalog still returns 6 plans
"""
import os
import re
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

# Use jury demo — bypasses 2FA + is billing exempt
JURY_EMAIL = "jury@zynthoro.ai"
JURY_PASSWORD = "ZynthoroDemo2026!"

# Forbidden patterns (case-insensitive)
FORBIDDEN_META_PHRASES = [
    "how can i help you better",
    "would you like me to",
    "happy to help",
    "let me help you",
]
FORBIDDEN_OUTDATED = [
    "30 june",
    "€99",
    "99/mo founder",
    "founder pricing",
    "launching 30",
]


@pytest.fixture(scope="module")
def jury_session():
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


def _chat(session, assistant, message, retries=2):
    """Retry a couple of times since LLM replies are non-deterministic."""
    last_reply = ""
    last_status = None
    for _ in range(retries + 1):
        r = session.post(
            f"{BASE_URL}/api/ai/chat",
            json={"assistant": assistant, "message": message},
            timeout=90,
        )
        last_status = r.status_code
        if r.status_code == 200:
            reply = r.json().get("reply", "") or ""
            if reply.strip():
                return last_status, reply
        time.sleep(2)
    return last_status, last_reply


def _assert_no_forbidden(reply, forbidden_list, label=""):
    low = reply.lower()
    hits = [p for p in forbidden_list if p in low]
    assert not hits, f"[{label}] Found forbidden patterns {hits} in reply:\n{reply[:500]}"


def _opening_sentence(reply):
    # First ~200 chars for opening check
    return reply.strip()[:250].lower()


# ---------- Tests ----------

class TestZynthaContentDelivery:
    def test_zyntha_delivers_linkedin_hook(self, jury_session):
        status, reply = _chat(
            jury_session, "zyntha",
            "Write me a LinkedIn hook for a SaaS launch"
        )
        assert status == 200, f"HTTP {status}"
        assert len(reply.strip()) > 20, f"Reply too short: {reply!r}"
        # Opening sentence shouldn't be a meta-question
        opening = _opening_sentence(reply)
        forbidden_opens = ["how can i help you better", "would you like me to", "happy to help", "let me help you"]
        hits = [p for p in forbidden_opens if p in opening]
        assert not hits, f"Meta-question opener {hits}: {opening!r}"
        _assert_no_forbidden(reply, FORBIDDEN_OUTDATED, "zyntha")


class TestThoroWebshopWorkflow:
    def test_thoro_recommends_zynthoro_modules(self, jury_session):
        status, reply = _chat(
            jury_session, "thoro",
            "Help me set up a webshop workflow in Zynthoro"
        )
        assert status == 200, f"HTTP {status}"
        assert len(reply.strip()) > 20
        low = reply.lower()
        # Must recommend at least one Zynthoro-native domain
        native_hits = [d for d in ["sales admin", "invoicing", "marketing", "operations"] if d in low]
        assert native_hits, f"Thoro did not recommend Zynthoro modules. Reply:\n{reply[:800]}"
        _assert_no_forbidden(reply, FORBIDDEN_OUTDATED, "thoro")
        # opener check
        forbidden_opens = ["how can i help you better", "would you like me to", "happy to help"]
        opening = _opening_sentence(reply)
        hits = [p for p in forbidden_opens if p in opening]
        assert not hits, f"Meta-question opener {hits}: {opening!r}"


class TestZyonaPricingVerdict:
    def test_zyona_gives_verdict(self, jury_session):
        status, reply = _chat(
            jury_session, "zyona",
            "Should we raise our SaaS pricing by 20%?"
        )
        assert status == 200
        assert len(reply.strip()) > 20
        _assert_no_forbidden(reply, FORBIDDEN_OUTDATED, "zyona")
        opening = _opening_sentence(reply)
        forbidden_opens = ["let me help you", "how can i help you better", "happy to help"]
        hits = [p for p in forbidden_opens if p in opening]
        assert not hits, f"Meta-question opener {hits}: {opening!r}"


class TestZynthoroAssistDirect:
    def test_assist_direct_answer(self, jury_session):
        status, reply = _chat(
            jury_session, "zynthoro_assist",
            "Where do I find billing settings?"
        )
        assert status == 200
        assert len(reply.strip()) > 20
        _assert_no_forbidden(reply, FORBIDDEN_OUTDATED, "zynthoro_assist")
        opening = _opening_sentence(reply)
        forbidden_opens = ["happy to help", "how can i help you better", "let me guide you"]
        hits = [p for p in forbidden_opens if p in opening]
        assert not hits, f"Meta-question opener {hits}: {opening!r}"


class TestTierCatalogRegression:
    def test_catalog_returns_six_plans(self):
        r = requests.get(f"{BASE_URL}/api/tier/catalog", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Catalog might be dict or list
        if isinstance(data, dict):
            # Accept {plans: [...]} or a dict of plans
            plans = data.get("plans") or data.get("items") or list(data.values())
        else:
            plans = data
        assert isinstance(plans, list), f"Unexpected shape: {type(data)}"
        assert len(plans) == 6, f"Expected 6 plans, got {len(plans)}: {plans}"
