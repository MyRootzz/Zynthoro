"""Tests for the emergency POST /api/admin/disable-2fa endpoint.

Covers: auth (missing/wrong X-Admin-Key), 404 for unknown email, happy path
(set_founder=false and set_founder=true), Pydantic 422 for invalid email,
and DB-level verification via motor. Adjacent seed endpoint regression too.
"""
import os
import sys
import uuid
import asyncio
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load backend env for MONGO_URL/DB_NAME/ADMIN_SEED_KEY
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # Fallback to frontend env file
    from dotenv import dotenv_values
    fe = dotenv_values("/app/frontend/.env")
    BASE_URL = fe["REACT_APP_BACKEND_URL"].rstrip("/")

ADMIN_KEY = os.environ["ADMIN_SEED_KEY"]
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

EP = f"{BASE_URL}/api/admin/disable-2fa"
SEED_EP = f"{BASE_URL}/api/admin/seed-qa-accounts"


def _mongo_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(MONGO_URL)
    return client, client[DB_NAME]


async def _find_user(email):
    client, db = _mongo_db()
    try:
        return await db.users.find_one({"email": email})
    finally:
        client.close()


async def _insert_throwaway(email):
    client, db = _mongo_db()
    try:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": email,
            "password_hash": "x",
            "twofa_enabled": True,
            "twofa_method": "email",
            "totp_secret": "abc",
            "email_2fa_code_hash": "hashed",
            "email_2fa_expires_at": "2099-01-01",
            "email_2fa_attempts": 0,
            "twofa_backup_codes": ["a", "b"],
            "is_founder": False,
            "is_unlimited": False,
            "billing_exempt": False,
            "email_verified": False,
        })
    finally:
        client.close()


async def _delete_user(email):
    client, db = _mongo_db()
    try:
        await db.users.delete_one({"email": email})
    finally:
        client.close()


def _run(coro):
    return asyncio.run(coro)


# ---------- auth guard ----------

def test_missing_header_returns_401():
    r = requests.post(EP, json={"email": "any@x.com"})
    assert r.status_code == 401, r.text
    assert "Invalid admin key" in r.json().get("detail", "")


def test_wrong_key_returns_401():
    r = requests.post(EP, json={"email": "any@x.com"},
                      headers={"X-Admin-Key": "totally-wrong-key"})
    assert r.status_code == 401, r.text
    assert "Invalid admin key" in r.json().get("detail", "")


# ---------- 404 for unknown user ----------

def test_unknown_email_returns_404():
    r = requests.post(EP,
                      json={"email": f"nonexistent-{uuid.uuid4().hex[:8]}@zynthoro.io"},
                      headers={"X-Admin-Key": ADMIN_KEY})
    assert r.status_code == 404, r.text
    assert "No user found" in r.json().get("detail", "")


# ---------- 422 defensive validation ----------

def test_invalid_email_format_returns_422():
    r = requests.post(EP, json={"email": "not-an-email"},
                      headers={"X-Admin-Key": ADMIN_KEY})
    assert r.status_code == 422, r.text


# ---------- happy path set_founder=False on existing QA user ----------

def test_disable_2fa_on_existing_qa_user():
    email = "qa-kickstart2@zynthoro.io"
    # ensure the user exists (seed is idempotent)
    seed = requests.post(SEED_EP, headers={"X-Admin-Key": ADMIN_KEY})
    assert seed.status_code == 200, seed.text

    before = _run(_find_user(email))
    assert before is not None, "QA user should exist after seeding"

    r = requests.post(EP,
                      json={"email": email, "set_founder": False},
                      headers={"X-Admin-Key": ADMIN_KEY})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["matched"] == 1
    assert body["set_founder"] is False
    assert body["email"] == email

    after = _run(_find_user(email))
    assert after["twofa_enabled"] is False
    # 2FA fields must be unset
    for f in ("twofa_method", "totp_secret", "totp_secret_pending",
              "email_2fa_code_hash", "email_2fa_expires_at",
              "email_2fa_attempts", "twofa_backup_codes"):
        assert f not in after, f"{f} should be $unset but is still present"

    # must NOT accidentally promote to founder
    assert after.get("is_founder") is False
    assert after.get("is_unlimited") is False
    assert after.get("billing_exempt") is False

    # cleanup: restore is_qa_test flag if it was cleared (endpoint doesn't touch it,
    # but re-seed to be safe & idempotent)
    seed2 = requests.post(SEED_EP, headers={"X-Admin-Key": ADMIN_KEY})
    assert seed2.status_code == 200


# ---------- happy path set_founder=True on throwaway user ----------

def test_disable_2fa_with_set_founder_true_promotes_user():
    email = f"throwaway-{uuid.uuid4().hex[:10]}@zynthoro-throwaway.io"
    _run(_insert_throwaway(email))
    try:
        before = _run(_find_user(email))
        assert before["twofa_enabled"] is True
        assert before["is_founder"] is False

        r = requests.post(EP,
                          json={"email": email, "set_founder": True},
                          headers={"X-Admin-Key": ADMIN_KEY})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["matched"] == 1
        assert body["modified"] == 1
        assert body["set_founder"] is True

        after = _run(_find_user(email))
        assert after["twofa_enabled"] is False
        assert after["is_founder"] is True
        assert after["is_unlimited"] is True
        assert after["billing_exempt"] is True
        assert after["email_verified"] is True
        for f in ("twofa_method", "totp_secret", "email_2fa_code_hash",
                  "email_2fa_expires_at", "email_2fa_attempts",
                  "twofa_backup_codes"):
            assert f not in after, f"{f} should have been $unset"
    finally:
        _run(_delete_user(email))


# ---------- email case-insensitivity (endpoint lowercases) ----------

def test_email_is_lowercased_before_lookup():
    email = f"MixedCase-{uuid.uuid4().hex[:8]}@Zynthoro-Throwaway.io"
    lowered = email.lower()
    _run(_insert_throwaway(lowered))
    try:
        r = requests.post(EP,
                          json={"email": email, "set_founder": False},
                          headers={"X-Admin-Key": ADMIN_KEY})
        assert r.status_code == 200, r.text
        assert r.json()["email"] == lowered
    finally:
        _run(_delete_user(lowered))


# ---------- regression: seed endpoint still works ----------

def test_seed_endpoint_still_works():
    r = requests.post(SEED_EP, headers={"X-Admin-Key": ADMIN_KEY})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["total"] == 6


def test_seed_endpoint_wrong_key_401():
    r = requests.post(SEED_EP, headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 401
