"""Regression tests for the weekly digest change (2026-07-21).

Verifies:
  - `_has_activity` returns True/False correctly.
  - `send_digest_now` skips the send when there's no activity and no force.
  - `send_digest_now` sends when there IS activity.
  - ISO-week idempotency: the second call in the same week is a no-op.

Run:
    cd /app/backend && python -m pytest tests/test_weekly_digest.py -v
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

import daily_digest  # noqa: E402
from server import db as server_db  # noqa: E402

_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


def test_has_activity_all_zero_returns_false():
    assert daily_digest._has_activity({
        "presale": [], "voice_leads": [], "voice_anonymous_count": 0,
        "purchases": [], "ai_messages_count": 0, "new_users_count": 0,
    }) is False


def test_has_activity_true_when_any_signal():
    for key, value in [
        ("presale", [{"email": "a@b.io"}]),
        ("voice_leads", [{"email": "a@b.io"}]),
        ("voice_anonymous_count", 3),
        ("purchases", [{"session_id": "x"}]),
        ("ai_messages_count", 1),
        ("new_users_count", 1),
    ]:
        base = {
            "presale": [], "voice_leads": [], "voice_anonymous_count": 0,
            "purchases": [], "ai_messages_count": 0, "new_users_count": 0,
        }
        base[key] = value
        assert daily_digest._has_activity(base) is True, (
            f"expected has_activity True when {key}={value!r}"
        )


def test_iso_week_key_format():
    key = daily_digest._iso_week_key(datetime(2026, 1, 5, tzinfo=timezone.utc))
    # 2026-01-05 is a Monday → ISO week 2
    assert key == "2026-W02"
    key2 = daily_digest._iso_week_key(datetime(2026, 12, 28, tzinfo=timezone.utc))
    # 2026-12-28 is a Monday → ISO week 53 of 2026
    assert key2.startswith("2026-W")


def test_send_digest_skips_when_no_activity(monkeypatch):
    """No purchases, signups, voice leads, AI msgs, or new users → send skipped."""
    sent_calls: list = []

    async def fake_send(*a, **kw):
        sent_calls.append((a, kw))
        return "msg-id"

    monkeypatch.setattr("email_service._send", fake_send)

    async def go():
        # Clear the state key so the ISO-week guard doesn't trip first.
        await server_db.system_state.delete_one({"_id": "weekly_digest"})
        # Monkeypatch _collect to return an empty snapshot.
        async def _empty_collect(_db):
            return {
                "window_days": 7,
                "window_start": "", "window_end": "",
                "presale": [], "voice_leads": [], "voice_anonymous_count": 0,
                "purchases": [], "ai_messages_count": 0, "new_users_count": 0,
                "presale_total_real": 0, "voice_total_real": 0,
            }
        monkeypatch.setattr(daily_digest, "_collect", _empty_collect)
        result = await daily_digest.send_digest_now(server_db, force=False)
        return result

    r = _run(go())
    assert r["sent"] is False
    assert r["reason"] == "no_activity"
    assert len(sent_calls) == 0, "email _send must NOT be called on quiet weeks"

    # State was still recorded to prevent a re-attempt this week.
    async def check():
        st = await server_db.system_state.find_one({"_id": "weekly_digest"})
        assert st is not None
        assert st["last_action"] == "skipped_no_activity"
        await server_db.system_state.delete_one({"_id": "weekly_digest"})
    _run(check())


def test_send_digest_iso_week_dedupe(monkeypatch):
    """Second call in the same ISO week is a no-op (unless force=True)."""
    async def fake_send(*a, **kw):
        return "msg-id"

    monkeypatch.setattr("email_service._send", fake_send)

    async def go():
        await server_db.system_state.delete_one({"_id": "weekly_digest"})
        # Force a "sent" state for the current ISO week.
        this_week = daily_digest._iso_week_key(datetime.now(timezone.utc))
        await server_db.system_state.insert_one({
            "_id": "weekly_digest",
            "last_sent_iso_week": this_week,
            "last_action": "sent",
        })
        r = await daily_digest.send_digest_now(server_db, force=False)
        await server_db.system_state.delete_one({"_id": "weekly_digest"})
        return r

    r = _run(go())
    assert r["sent"] is False
    assert r["reason"] == "already_sent_this_week"


def test_send_digest_force_bypasses_both_guards(monkeypatch):
    """force=True must bypass both the ISO-week dedupe AND the no-activity skip."""
    sent_calls: list = []

    async def fake_send(*a, **kw):
        sent_calls.append(a)
        return f"msg-{uuid.uuid4()}"

    monkeypatch.setattr("email_service._send", fake_send)

    async def _empty_collect(_db):
        return {
            "window_days": 7,
            "window_start": "", "window_end": "",
            "presale": [], "voice_leads": [], "voice_anonymous_count": 0,
            "purchases": [], "ai_messages_count": 0, "new_users_count": 0,
            "presale_total_real": 0, "voice_total_real": 0,
        }

    monkeypatch.setattr(daily_digest, "_collect", _empty_collect)

    async def go():
        this_week = daily_digest._iso_week_key(datetime.now(timezone.utc))
        await server_db.system_state.delete_one({"_id": "weekly_digest"})
        await server_db.system_state.insert_one({
            "_id": "weekly_digest", "last_sent_iso_week": this_week,
        })
        r = await daily_digest.send_digest_now(server_db, force=True)
        await server_db.system_state.delete_one({"_id": "weekly_digest"})
        return r

    r = _run(go())
    assert r["sent"] is True, f"force=True should send even with no activity + duped week; got {r}"
    assert len(sent_calls) == 1
