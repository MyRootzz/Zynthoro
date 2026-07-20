from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import hmac
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Literal
import uuid
import base64
import io
from datetime import datetime, timezone, timedelta

import pyotp
import qrcode

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from auth import (  # noqa: E402
    hash_password, verify_password,
    create_access_token, create_pretwofa_token, decode_token,
    get_current_user_full, get_optional_user, get_founder_user,
    check_lockout, record_failed_login, clear_failed_logins,
    gen_token_url_safe, gen_numeric_code,
)
import ai_assistants  # noqa: E402
import checkout as checkout_mod  # noqa: E402
import activity_log  # noqa: E402
import tier_catalog  # noqa: E402
import stripe_subscriptions as subs_mod  # noqa: E402
import stripe as stripe_sdk  # noqa: E402
import email_service  # noqa: E402
import asyncio  # noqa: E402

# Plan ordering for upgrade/downgrade classification in webhook alerts.
_PLAN_ORDER = [
    "Presale", "Starter", "Creator", "Business", "Agency",
    "Enterprise Basic", "Enterprise Plus", "Enterprise Advanced",
    "Enterprise Unlimited",
]


def _plan_rank(plan_key: Optional[str]) -> int:
    if not plan_key:
        return 0
    try:
        return _PLAN_ORDER.index(plan_key)
    except ValueError:
        # Unknown plan → rank just above Presale so 'subscribe' classification still works
        return 1
from fastapi import UploadFile, File  # noqa: E402

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# App
app = FastAPI(title="Zynthoro API", version="2.0.0")
api_router = APIRouter(prefix="/api")

logger = logging.getLogger("zynthoro")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# ========================================================================
#  Models
# ========================================================================
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


class PresaleSignupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: Optional[str] = Field(default=None, max_length=200)
    plan_interest: Optional[str] = Field(default=None, max_length=60)


class PresaleSignup(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: EmailStr
    company: Optional[str] = None
    plan_interest: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SignupIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company: str = Field(min_length=1, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TwoFAVerifyIn(BaseModel):
    pre_token: str
    method: Literal["totp", "email"]
    code: str


class TwoFASetupConfirmIn(BaseModel):
    code: str


class EmailCodeRequestIn(BaseModel):
    pre_token: str


class OnboardingIn(BaseModel):
    company_name: str
    country: Optional[str] = None
    industry: Optional[str] = None
    employees: Optional[str] = None
    website: Optional[str] = None
    first_action: Optional[str] = None


class AssistChatIn(BaseModel):
    assistant: Literal["zynthoro_assist", "zyntha", "thoro", "zyona"]
    session_id: Optional[str] = None
    message: str = Field(min_length=1, max_length=4000)


class CaptionIn(BaseModel):
    idea: str = Field(min_length=3, max_length=2000)
    platform: Literal["instagram", "facebook", "linkedin", "tiktok", "x", "youtube"] = "instagram"
    tone: Optional[str] = Field(default=None, max_length=80)


class SubscriptionCheckoutIn(BaseModel):
    plan_key: Literal[
        "Starter", "Creator", "Business", "Agency",
        "Enterprise Basic", "Enterprise Plus", "Enterprise Advanced",
    ]


class SeatsCheckoutIn(BaseModel):
    quantity: int = Field(ge=1, le=100)


class TeamInviteIn(BaseModel):
    email: EmailStr
    role: str = Field(default="Employee")
    level: int = Field(default=2, ge=1, le=10)


# Plan → max member level (Fix 7 — Employee hierarchy)
PLAN_MAX_LEVEL = {
    "Presale": 5,
    "Starter": 3,
    "Creator": 3,
    "Business": 5,
    "Agency": 7,
    "Enterprise Basic": 10,
    "Enterprise Plus": 10,
    "Enterprise Advanced": 10,
    "Enterprise Elite": 10,
    "Enterprise Unlimited": 10,
}

LEVEL_LABELS = {
    1: "Intern / Guest",
    2: "Employee",
    3: "Employee",
    4: "Manager",
    5: "Manager",
    6: "Senior Manager",
    7: "Senior Manager",
    8: "Director",
    9: "Director",
    10: "Owner",
}


def _serialize_user(u: dict) -> dict:
    out = {
        k: v for k, v in u.items()
        if k not in ("_id", "password_hash", "totp_secret", "email_2fa_code_hash", "email_2fa_expires_at")
    }
    return out


def _set_auth_cookies(response: Response, access_token: str):
    response.set_cookie(
        key="access_token", value=access_token, httponly=True,
        secure=False, samesite="lax", max_age=60 * 60 * 24, path="/",
    )


# ========================================================================
#  Public Routes
# ========================================================================
@api_router.get("/")
async def root():
    return {"message": "Zynthoro API", "status": "ok", "version": "2.0.0"}


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    obj = StatusCheck(**input.model_dump())
    doc = obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.status_checks.insert_one(doc)
    return obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    rows = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for r in rows:
        if isinstance(r['timestamp'], str):
            r['timestamp'] = datetime.fromisoformat(r['timestamp'])
    return rows


def _is_test_signup(email: str, name: Optional[str] = None, company: Optional[str] = None) -> bool:
    """Flag automated testing-agent / QA fixtures so they are excluded from
    real signup reports. Public-facing counters still see every row (social
    proof is preserved) — only founder dashboards filter on this flag.
    """
    e = (email or "").lower().strip()
    n = (name or "").strip()
    c = (company or "").strip()
    if e.endswith("@zynthoro-test.com"):
        return True
    if e in {"test@zynthoro.com", "test@zynthoro.ai"}:
        return True
    local = e.split("@", 1)[0] if "@" in e else e
    if local.startswith(("test_", "ui_test_", "dup_test_", "qa_", "qatest_")):
        return True
    if n.upper().startswith("TEST ") or n in {"UI Test User", "User One"}:
        return True
    if c == "TEST Co BV":
        return True
    return False


@api_router.post("/presale/signup", response_model=PresaleSignup, status_code=201)
async def create_presale_signup(payload: PresaleSignupCreate):
    email_norm = payload.email.lower().strip()
    existing = await db.presale_signups.find_one({"email": email_norm}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="This email is already on the presale list.")
    signup = PresaleSignup(
        name=payload.name.strip(),
        email=email_norm,
        company=(payload.company.strip() if payload.company else None),
        plan_interest=payload.plan_interest,
    )
    doc = signup.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['is_test'] = _is_test_signup(email_norm, signup.name, signup.company)
    await db.presale_signups.insert_one(doc)
    return signup


@api_router.get("/presale/count")
async def get_presale_count():
    # Public counter — keeps social proof (includes legacy test rows).
    count = await db.presale_signups.count_documents({})
    return {"count": count}


# =====================================================================
#  One-time admin seed — Kickstart tier QA test accounts
#  ----------------------
#  Protected by the `X-Admin-Key` header (must equal env `ADMIN_SEED_KEY`).
#  Fails closed if the env var is unset. Idempotent — safe to call
#  multiple times. Remove this endpoint after production seeding is done.
# =====================================================================
QA_SEED_ACCOUNTS = [
    ("qa-kickstart1@zynthoro.io", "QaKick1!Test", "Kickstart 1"),
    ("qa-kickstart2@zynthoro.io", "QaKick2!Test", "Kickstart 2"),
    ("qa-kickstart3@zynthoro.io", "QaKick3!Test", "Kickstart 3"),
    ("qa-compleet@zynthoro.io",   "QaComp!Test",  "Compleet"),
    ("qa-aiweek@zynthoro.io",     "QaWeek!Test",  "AI+Social Week"),
    ("qa-aimonth@zynthoro.io",    "QaMonth!Test", "AI+Social Month"),
]


@api_router.post("/admin/seed-qa-accounts")
async def admin_seed_qa_accounts(request: Request):
    """Idempotent seed of the 6 Kickstart QA test accounts.
    Header: X-Admin-Key: <ADMIN_SEED_KEY>
    """
    expected = os.environ.get("ADMIN_SEED_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="Seed endpoint disabled (ADMIN_SEED_KEY not set).")
    provided = request.headers.get("x-admin-key") or ""
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid admin key.")

    from auth import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    created, refreshed = 0, 0
    for email, password, target_tier in QA_SEED_ACCOUNTS:
        pw_hash = hash_password(password)
        first, _, _ = email.partition("@")
        base = {
            "email": email,
            "password_hash": pw_hash,
            "first_name": first.replace("qa-", "QA ").title(),
            "last_name": "Test",
            "email_verified": True,
            "twofa_enabled": False,
            "is_demo": False,
            "is_founder": False,
            "is_unlimited": False,
            "billing_exempt": False,
            "is_qa_test": True,
            "subscription_plan": "Presale",
            "company": f"QA Test — {target_tier}",
            "ai_credits_used_this_period": 0,
            "ai_credits_limit": None,
            "notes_qa_target_tier": target_tier,
            "updated_at": now_iso,
        }
        existing = await db.users.find_one({"email": email}, {"id": 1})
        if existing:
            await db.users.update_one(
                {"email": email},
                {
                    "$set": base,
                    "$unset": {
                        "totp_secret": "", "totp_secret_pending": "",
                        "email_2fa_code_hash": "", "email_2fa_expires_at": "",
                        "email_2fa_attempts": "", "twofa_backup_codes": "",
                        "twofa_method": "",
                    },
                },
            )
            refreshed += 1
        else:
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "created_at": now_iso,
                **base,
            })
            created += 1

    logger.warning("QA seed endpoint invoked — created=%d refreshed=%d", created, refreshed)
    return {"ok": True, "created": created, "refreshed": refreshed, "total": len(QA_SEED_ACCOUNTS)}


class DisableTwofaIn(BaseModel):
    email: EmailStr
    set_founder: bool = False


@api_router.post("/admin/disable-2fa")
async def admin_disable_2fa(payload: DisableTwofaIn, request: Request):
    """Emergency endpoint — disables 2FA for a single account by email.
    Also optionally sets `is_founder: True` (needed for the founder-bypass
    code path to skip the 2FA-setup wizard on future logins).

    Header: X-Admin-Key: <ADMIN_SEED_KEY>
    Remove this endpoint after use.
    """
    expected = os.environ.get("ADMIN_SEED_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="Endpoint disabled (ADMIN_SEED_KEY not set).")
    provided = request.headers.get("x-admin-key") or ""
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid admin key.")

    set_ops = {
        "twofa_enabled": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if payload.set_founder:
        set_ops.update({
            "is_founder": True,
            "is_unlimited": True,
            "billing_exempt": True,
            "email_verified": True,
        })

    res = await db.users.update_one(
        {"email": str(payload.email).lower()},
        {
            "$set": set_ops,
            "$unset": {
                "twofa_method": "",
                "totp_secret": "",
                "totp_secret_pending": "",
                "email_2fa_code_hash": "",
                "email_2fa_expires_at": "",
                "email_2fa_attempts": "",
                "twofa_backup_codes": "",
            },
        },
    )
    logger.warning("Admin disable-2fa invoked for %s — matched=%d modified=%d set_founder=%s",
                   payload.email, res.matched_count, res.modified_count, payload.set_founder)
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"No user found with email {payload.email}")
    return {
        "ok": True,
        "email": str(payload.email).lower(),
        "matched": res.matched_count,
        "modified": res.modified_count,
        "set_founder": payload.set_founder,
    }



#  ----------------------
#  Voice Tour lead capture
#  Anonymous visitors who interact with the homepage voice tryout get
#  logged here as warm leads (high-intent signal). Optional email turns
#  them into a follow-up segment for sales.
# =====================================================================
class VoiceTryoutIn(BaseModel):
    transcript: Optional[str] = Field(default=None, max_length=4000)
    email: Optional[str] = Field(default=None, max_length=320)
    language: Optional[str] = Field(default=None, max_length=16)


@api_router.post("/voice-tryout", status_code=201)
async def create_voice_tryout(payload: VoiceTryoutIn, request: Request):
    email_norm = (payload.email or "").lower().strip() or None
    is_test = _is_test_signup(email_norm or "", None, None) if email_norm else False
    ua = (request.headers.get("user-agent") or "")[:500]
    # Trust the first hop from the ingress for IP (best-effort).
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or (request.client.host if request.client else None)
    doc = {
        "id": str(uuid.uuid4()),
        "transcript": (payload.transcript or "").strip()[:4000] or None,
        "email": email_norm,
        "language": payload.language,
        "user_agent": ua,
        "ip": ip,
        "is_test": is_test,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.voice_tryout_leads.insert_one(doc)
    doc.pop("_id", None)
    return {"id": doc["id"], "captured": True}


@api_router.get("/founder/voice-tryouts")
async def founder_voice_tryouts(user=Depends(get_founder_user)):
    rows = await db.voice_tryout_leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    real = [r for r in rows if not r.get("is_test")]
    with_email = [r for r in real if r.get("email")]
    return {
        "leads": real,
        "count": len(real),
        "with_email_count": len(with_email),
        "anonymous_count": len(real) - len(with_email),
        "test_count": len(rows) - len(real),
    }


@api_router.post("/founder/digest/send")
async def founder_send_digest(user=Depends(get_founder_user), force: bool = False):
    """Manually trigger the daily pipeline digest email.

    By default, dedupes once per UTC day (matching the scheduler). Pass
    ``?force=true`` to re-send even if today's digest already went out.
    """
    import daily_digest  # noqa: WPS433
    return await daily_digest.send_digest_now(db, force=force)


@api_router.get("/founder/digest/preview")
async def founder_digest_preview(user=Depends(get_founder_user)):
    """Return the rendered HTML + payload without sending — handy for QA."""
    import daily_digest  # noqa: WPS433
    data = await daily_digest._collect(db)
    return {
        "html": daily_digest.render_html(data),
        "presale_count": len(data["presale"]),
        "voice_lead_count": len(data["voice_leads"]),
        "voice_anonymous_count": data["voice_anonymous_count"],
    }


# ========================================================================
#  Auth Routes
# ========================================================================
@api_router.post("/auth/signup", status_code=201)
async def auth_signup(payload: SignupIn, response: Response):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    verification_token = gen_token_url_safe(24)
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": email,
        "first_name": payload.first_name.strip(),
        "last_name": payload.last_name.strip(),
        "company": payload.company.strip(),
        "password_hash": hash_password(payload.password),
        "role": "Owner",
        "is_founder": False,
        "is_unlimited": False,
        "billing_exempt": False,
        "subscription_plan": "Presale",
        "email_verified": False,
        "verification_token": verification_token,
        "twofa_enabled": False,
        "twofa_method": None,
        "totp_secret": None,
        "onboarding_completed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)

    # Try to send a real verification email via Resend if configured.
    base = os.environ.get("PUBLIC_APP_URL", "https://zynthoro.ai").rstrip("/")
    verify_link = f"{base}/verify-email?token={verification_token}"
    email_id = await email_service.send_verification(email, verify_link)
    if email_id:
        logger.info("Verification email sent to %s id=%s", email, email_id)
    else:
        logger.info("[email-mock from=hello@zynthoro.ai to=%s] Verification link: /verify-email?token=%s", email, verification_token)

    resp = {
        "message": "We've sent you a verification link. Please check your inbox.",
        "user_id": user_id,
    }
    # Only expose the dev token when Resend is NOT configured (dev/test).
    if not email_service.is_enabled():
        resp["dev_verification_token"] = verification_token
    return resp


@api_router.get("/auth/verify-email")
async def auth_verify_email(token: str):
    user = await db.users.find_one({"verification_token": token})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token.")
    # Idempotent: keep token so React StrictMode / retried calls still succeed.
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"email_verified": True}},
    )
    return {"message": "Your email has been verified. You can now log in.", "email": user["email"]}


@api_router.post("/auth/login")
async def auth_login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.lower().strip()
    # Key brute-force lockout by email only (client IP varies across k8s ingress pods).
    ident = f"email:{email}"

    # Lookup user first so we can bypass lockout for demo accounts (jury, XPRIZE).
    user = await db.users.find_one({"email": email})
    is_demo_account = bool(user and user.get("is_demo"))

    # Demo accounts NEVER get rate-limited — judges need single-click access.
    if not is_demo_account:
        await check_lockout(db, ident)

    if not user or not verify_password(payload.password, user["password_hash"]):
        if not is_demo_account:
            await record_failed_login(db, ident)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.get("email_verified", False) and not user.get("is_founder") and not is_demo_account:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in.")

    await clear_failed_logins(db, ident)

    # If 2FA already enabled → require verification.
    if user.get("twofa_enabled"):
        pre = create_pretwofa_token(user["id"], user["email"])
        return {
            "stage": "2fa_required",
            "pre_token": pre,
            "twofa_method": user.get("twofa_method"),
            "available_methods": ["totp", "email"],
        }

    # Demo accounts (XPRIZE jury), the founder owner account, and QA test
    # accounts bypass the 2FA setup gate — they land in the dashboard with
    # a single click.
    # `is_demo`, `is_founder`, and `is_qa_test` are only set by seed
    # functions or direct MongoDB writes and can never be granted via the
    # API. `is_qa_test` accounts still count AI credits and can still be
    # charged — the flag ONLY relaxes the 2FA setup gate.
    if user.get("is_demo") or user.get("is_founder") or user.get("is_qa_test"):
        access = create_access_token(user["id"], user["email"], twofa_passed=True)
        _set_auth_cookies(response, access)
        return {
            "stage": "ok",
            "access_token": access,
            "user": _serialize_user(user),
        }

    # No 2FA yet → must set it up before issuing full access token.
    pre = create_pretwofa_token(user["id"], user["email"])
    return {
        "stage": "2fa_setup_required",
        "pre_token": pre,
        "user": _serialize_user(user),
    }


@api_router.post("/auth/logout")
async def auth_logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"message": "Logged out"}


def _tier_context(user: dict) -> dict:
    """Return the tier feature block appended to /api/auth/me.

    Never raises — an unknown plan falls back to "Presale" (base features
    only) so the frontend always gets a valid feature list.
    """
    plan_key = user.get("subscription_plan") or "Presale"
    features = tier_catalog.TIER_FEATURES.get(plan_key) or tier_catalog.TIER_FEATURES["Presale"]

    # Founder / demo / billing-exempt accounts get everything unlocked.
    if user.get("is_founder") or user.get("is_demo") or user.get("billing_exempt") or user.get("is_unlimited"):
        return {
            "plan_key": plan_key,
            "modules": tier_catalog.ALL_MODULES,
            "workspaces": features.get("workspaces", 1),
            "seats": features.get("seats", 1),
            "ai_credits_limit": None,
            "ai_credits_used": 0,
            "ai_credits_remaining": None,  # unlimited
            "is_lifetime": bool(user.get("is_lifetime")),
        }

    # Prefer the user-doc value when explicitly set to a positive number
    # (post-provisioning). An explicit `None` on Presale users (written by
    # the seed refresh path) must fall through to the plan's default —
    # otherwise Presale users appear unlimited.
    doc_limit = user.get("ai_credits_limit")
    limit = doc_limit if doc_limit is not None else features.get("ai_credits_limit")
    used = int(user.get("ai_credits_used_this_period") or 0)
    remaining = None if limit is None else max(0, int(limit) - used)
    return {
        "plan_key": plan_key,
        "modules": features["modules"],
        "workspaces": features.get("workspaces", 1),
        "seats": features.get("seats", 1),
        "ai_credits_limit": limit,
        "ai_credits_used": used,
        "ai_credits_remaining": remaining,
        "is_lifetime": bool(user.get("is_lifetime")),
    }


@api_router.get("/auth/me")
async def auth_me(user=Depends(get_current_user_full)):
    user["tier"] = _tier_context(user)
    return user


@api_router.get("/me/tier")
async def me_tier(user=Depends(get_current_user_full)):
    """Lightweight tier-only endpoint used by the dashboard sidebar to
    render the module lock badges without re-fetching the full user."""
    return _tier_context(user)


# ===== 2FA Setup (TOTP) =====
@api_router.post("/auth/2fa/totp/setup")
async def twofa_totp_setup(payload: EmailCodeRequestIn):
    p = decode_token(payload.pre_token)
    if p.get("type") != "pre_2fa":
        raise HTTPException(status_code=401, detail="Invalid token.")
    user = await db.users.find_one({"id": p["sub"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    secret = pyotp.random_base32()
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_secret_pending": secret}})

    otp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user["email"], issuer_name="Zynthoro"
    )
    img = qrcode.make(otp_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    return {"secret": secret, "otpauth_url": otp_uri, "qr_data_url": data_url}


@api_router.post("/auth/2fa/totp/confirm")
async def twofa_totp_confirm(payload: TwoFAVerifyIn, response: Response):
    p = decode_token(payload.pre_token)
    if p.get("type") != "pre_2fa":
        raise HTTPException(status_code=401, detail="Invalid token.")
    user = await db.users.find_one({"id": p["sub"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    secret = user.get("totp_secret_pending") or user.get("totp_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="2FA setup not initialized.")
    totp = pyotp.TOTP(secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid authenticator code.")

    await db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {
                "twofa_enabled": True,
                "twofa_method": "totp",
                "totp_secret": secret,
            },
            "$unset": {"totp_secret_pending": ""},
        },
    )

    access = create_access_token(user["id"], user["email"], twofa_passed=True)
    _set_auth_cookies(response, access)
    fresh = await db.users.find_one({"id": user["id"]})
    return {"stage": "ok", "token": access, "user": _serialize_user(fresh)}


# ===== 2FA via Email code (fallback) =====
@api_router.post("/auth/2fa/email/request")
async def twofa_email_request(payload: EmailCodeRequestIn):
    p = decode_token(payload.pre_token)
    if p.get("type") != "pre_2fa":
        raise HTTPException(status_code=401, detail="Invalid token.")
    user = await db.users.find_one({"id": p["sub"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    code = gen_numeric_code(6)
    code_hash = hash_password(code)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"email_2fa_code_hash": code_hash, "email_2fa_expires_at": expires}},
    )
    # Real email via Resend if configured; otherwise fall back to log + dev_code.
    email_id = await email_service.send_2fa_code(user["email"], code)
    if email_id:
        logger.info("2FA email sent to %s id=%s", user["email"], email_id)
    else:
        logger.info("[email-mock from=support@zynthoro.ai to=%s] 2FA email code: %s", user["email"], code)

    resp = {"message": "Code sent. Check your inbox."}
    if not email_service.is_enabled():
        resp["dev_code"] = code
    return resp


@api_router.post("/auth/2fa/verify")
async def twofa_verify(payload: TwoFAVerifyIn, response: Response):
    p = decode_token(payload.pre_token)
    if p.get("type") != "pre_2fa":
        raise HTTPException(status_code=401, detail="Invalid token.")
    user = await db.users.find_one({"id": p["sub"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.method == "totp":
        if not user.get("totp_secret"):
            raise HTTPException(status_code=400, detail="TOTP not configured.")
        if not pyotp.TOTP(user["totp_secret"]).verify(payload.code, valid_window=1):
            raise HTTPException(status_code=400, detail="Invalid authenticator code.")
    elif payload.method == "email":
        chash = user.get("email_2fa_code_hash")
        exp = user.get("email_2fa_expires_at")
        if not chash or not exp:
            raise HTTPException(status_code=400, detail="No code requested.")
        if datetime.fromisoformat(exp) < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Code expired.")
        if not verify_password(payload.code, chash):
            raise HTTPException(status_code=400, detail="Invalid email code.")
        # consume code
        await db.users.update_one(
            {"id": user["id"]},
            {"$unset": {"email_2fa_code_hash": "", "email_2fa_expires_at": ""}},
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported method.")

    access = create_access_token(user["id"], user["email"], twofa_passed=True)
    _set_auth_cookies(response, access)
    fresh = await db.users.find_one({"id": user["id"]})
    return {"stage": "ok", "token": access, "user": _serialize_user(fresh)}


# ===== Password reset (console-log) =====
class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


@api_router.post("/auth/forgot-password")
async def auth_forgot(payload: ForgotPasswordIn):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    # Always return ok to avoid email enumeration.
    if user:
        token = gen_token_url_safe(24)
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        await db.password_reset_tokens.insert_one({
            "token": token, "user_id": user["id"], "expires_at": expires, "used": False,
        })
        base = os.environ.get("PUBLIC_APP_URL", "https://zynthoro.ai").rstrip("/")
        reset_link = f"{base}/reset-password?token={token}"
        email_id = await email_service.send_password_reset(email, reset_link)
        if email_id:
            logger.info("Password reset email sent to %s id=%s", email, email_id)
        else:
            logger.info("[email-mock from=support@zynthoro.ai to=%s] Password reset link: /reset-password?token=%s", email, token)
        resp = {"message": "If the email exists, a reset link has been sent."}
        if not email_service.is_enabled():
            resp["dev_reset_token"] = token
        return resp
    return {"message": "If the email exists, a reset link has been sent."}


@api_router.post("/auth/reset-password")
async def auth_reset(payload: ResetPasswordIn):
    rec = await db.password_reset_tokens.find_one({"token": payload.token})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    if datetime.fromisoformat(rec["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired.")
    await db.users.update_one(
        {"id": rec["user_id"]},
        {"$set": {"password_hash": hash_password(payload.password)}},
    )
    await db.password_reset_tokens.update_one({"token": payload.token}, {"$set": {"used": True}})
    return {"message": "Password updated. You can now log in."}


# ========================================================================
#  Onboarding
# ========================================================================
@api_router.post("/onboarding/complete")
async def onboarding_complete(payload: OnboardingIn, user=Depends(get_current_user_full)):
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "company": payload.company_name,
            "company_country": payload.country,
            "company_industry": payload.industry,
            "company_employees": payload.employees,
            "company_website": payload.website,
            "first_action": payload.first_action,
            "onboarding_completed": True,
            "onboarded_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"message": "Onboarding complete."}


# ========================================================================
#  Dashboard
# ========================================================================
@api_router.get("/dashboard/summary")
async def dashboard_summary(user=Depends(get_current_user_full)):
    uid = user["id"]
    team_count = await db.team_members.count_documents({"workspace_owner": uid}) + 1

    # 1) Unified activity_events log — populated live by team invites,
    #    AI messages, invoices, etc.
    ev_rows = await db.activity_events.find(
        {"workspace_owner": uid},
        {"_id": 0, "event_type": 1, "icon": 1, "title": 1, "subtitle": 1,
         "href": 1, "timestamp": 1},
    ).sort("timestamp", -1).limit(20).to_list(length=20)
    activity: List[dict] = [
        {
            "type": r.get("event_type"),
            "icon": r.get("icon"),
            "title": r.get("title"),
            "subtitle": r.get("subtitle"),
            "href": r.get("href"),
            "timestamp": r.get("timestamp"),
        }
        for r in ev_rows
    ]

    # 2) Fall back to the demo workspace collections so the XPRIZE jury
    #    account still sees a rich feed without needing to trigger events.
    if user.get("is_demo"):
        tm_rows = await db.team_members.find(
            {"workspace_owner": uid},
            {"_id": 0, "name": 1, "email": 1, "role": 1, "created_at": 1},
        ).sort("created_at", -1).limit(5).to_list(length=5)
        for r in tm_rows:
            activity.append({
                "type": "team_member_added",
                "icon": "user_plus",
                "title": f"{r.get('name') or r.get('email') or 'Team member'} joined the workspace",
                "subtitle": r.get("role") or "Team",
                "timestamp": r.get("created_at"),
                "href": "/dashboard/team",
            })

        inv_rows = await db.demo_invoices.find(
            {"workspace_owner": uid},
            {"_id": 0, "number": 1, "client": 1, "amount_eur": 1, "status": 1, "issued": 1, "created_at": 1},
        ).sort("created_at", -1).limit(5).to_list(length=5)
        for r in inv_rows:
            amount = r.get("amount_eur") or 0
            status = (r.get("status") or "").lower()
            activity.append({
                "type": "invoice",
                "icon": "receipt",
                "title": f"Invoice {r.get('number') or ''} — {r.get('client') or ''}".strip(),
                "subtitle": f"€{amount:,.0f} · {status.title() or 'Draft'}",
                "timestamp": r.get("created_at") or r.get("issued"),
                "href": "/dashboard/finance",
            })

        proj_rows = await db.demo_projects.find(
            {"workspace_owner": uid},
            {"_id": 0, "name": 1, "status": 1, "created_at": 1},
        ).sort("created_at", -1).limit(5).to_list(length=5)
        for r in proj_rows:
            activity.append({
                "type": "project",
                "icon": "folder_plus",
                "title": f"Project “{r.get('name') or 'Untitled'}” created",
                "subtitle": r.get("status") or "Active",
                "timestamp": r.get("created_at"),
                "href": "/dashboard/projects",
            })

    # Sort by timestamp desc and keep the top 8
    def _ts(item):
        return item.get("timestamp") or ""
    activity.sort(key=_ts, reverse=True)
    activity = activity[:8]

    return {
        "user": user,
        "kpis": {
            "monthly_revenue": 0,
            "open_invoices": 0,
            "active_projects": 0,
            "team_members": team_count,
        },
        "ai_suggestions": [
            "Create your first invoice to see live revenue here.",
            "Invite a teammate to start collaborating.",
            "Ask Zyona how to price your first product.",
        ],
        "recent_activity": activity,
    }


# ========================================================================
#  Teams
# ========================================================================
@api_router.get("/team/members")
async def team_list(user=Depends(get_current_user_full)):
    rows = await db.team_members.find(
        {"workspace_owner": user["id"]}, {"_id": 0}
    ).to_list(500)
    plan = user.get("subscription_plan", "Presale")
    max_level = PLAN_MAX_LEVEL.get(plan, 5)
    # Always include the owner first (level 10 always)
    owner = {
        "id": user["id"],
        "name": f'{user.get("first_name","")} {user.get("last_name","")}'.strip() or user["email"],
        "email": user["email"],
        "role": user.get("role", "Owner"),
        "level": 10,
        "level_label": LEVEL_LABELS[10],
        "status": "active",
        "twofa": user.get("twofa_enabled", False),
        "last_login": user.get("created_at"),
        "is_owner": True,
    }
    # Backfill level on existing members
    for r in rows:
        lv = int(r.get("level") or 2)
        r["level"] = lv
        r["level_label"] = LEVEL_LABELS.get(lv, "Employee")
    return {"members": [owner] + rows, "plan": plan, "max_level": max_level}


@api_router.post("/team/invite", status_code=201)
async def team_invite(payload: TeamInviteIn, user=Depends(get_current_user_full)):
    email = payload.email.lower().strip()
    plan = user.get("subscription_plan", "Presale")
    max_level = PLAN_MAX_LEVEL.get(plan, 5)
    if payload.level > max_level:
        raise HTTPException(
            status_code=403,
            detail=f"Your {plan} plan only allows members up to level {max_level}. Upgrade to invite higher-level roles.",
        )
    existing = await db.team_members.find_one(
        {"workspace_owner": user["id"], "email": email}
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already invited.")
    invite_token = gen_token_url_safe(20)
    doc = {
        "id": str(uuid.uuid4()),
        "workspace_owner": user["id"],
        "email": email,
        "role": payload.role,
        "level": payload.level,
        "status": "invited",
        "twofa": False,
        "invite_token": invite_token,
        "last_login": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.team_members.insert_one(doc)
    await activity_log.log_event(
        db,
        workspace_owner=user["id"],
        actor_email=user["email"],
        event_type="team_member_invited",
        icon="user_plus",
        title=f"Invited {email} to the workspace",
        subtitle=f"{payload.role} · level {payload.level}",
        href="/dashboard/team",
    )
    base = os.environ.get("PUBLIC_APP_URL", "https://zynthoro.ai").rstrip("/")
    accept_link = f"{base}/accept-invite?token={invite_token}"
    email_id = await email_service.send_team_invite(email, user["email"], accept_link, payload.role)
    if email_id:
        logger.info("Team invite email sent to %s id=%s", email, email_id)
    else:
        logger.info("[email-mock from=hello@zynthoro.ai to=%s by=%s] Team invite token=%s", email, user["email"], invite_token)
    resp = {"id": doc["id"], "email": email, "role": payload.role}
    if not email_service.is_enabled():
        resp["dev_invite_token"] = invite_token
    return resp


# ========================================================================
#  AI Assistants
# ========================================================================
@api_router.get("/ai/assistants")
async def list_ai_assistants():
    return {"assistants": ai_assistants.list_assistants()}


async def _consume_ai_credit(user: dict) -> None:
    """Increment the user's AI credit counter and raise HTTP 402 if the
    tier's monthly / one-time limit has been reached.

    Bypass conditions: founder / demo / billing-exempt / is_unlimited, or
    the plan has no limit (Compleet / Starter → ai_credits_limit is None).
    """
    if user.get("is_founder") or user.get("is_demo") or user.get("billing_exempt") or user.get("is_unlimited"):
        return
    ctx = _tier_context(user)
    limit = ctx.get("ai_credits_limit")
    if limit is None:
        return
    # Monthly reset: if the period ended, reset the counter first.
    now = datetime.now(timezone.utc)
    period_end = user.get("ai_credits_period_ends_at")
    if user.get("ai_credits_period") == "month":
        started = user.get("ai_credits_period_started_at")
        try:
            started_dt = datetime.fromisoformat(started) if started else now
        except Exception:
            started_dt = now
        if (now - started_dt).days >= 30:
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {
                    "ai_credits_used_this_period": 0,
                    "ai_credits_period_started_at": now.isoformat(),
                }},
            )
            user["ai_credits_used_this_period"] = 0
    elif period_end:
        try:
            end_dt = datetime.fromisoformat(period_end)
            if now > end_dt:
                raise HTTPException(
                    status_code=402,
                    detail="Your AI+Social top-up has expired. Please renew to continue.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    used = int(user.get("ai_credits_used_this_period") or 0)
    if used >= int(limit):
        raise HTTPException(
            status_code=402,
            detail=f"You've reached your {limit} AI credit limit for this period. Upgrade to Compleet for unlimited access.",
        )
    await db.users.update_one(
        {"id": user["id"]},
        {"$inc": {"ai_credits_used_this_period": 1}},
    )


@api_router.post("/ai/chat")
async def ai_chat(payload: AssistChatIn, user=Depends(get_current_user_full)):
    await _consume_ai_credit(user)
    session_id = payload.session_id or f"{user['id']}:{payload.assistant}:{uuid.uuid4()}"
    try:
        result = await ai_assistants.chat_complete(
            db,
            payload.assistant,
            session_id,
            user["id"],
            payload.message,
            subscription_plan=user.get("subscription_plan"),
            user_context=user,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "session_id": session_id,
        "assistant": payload.assistant,
        "reply": result["reply"],
        "provider": result["provider"],
        "model": result["model"],
        "badge": result["badge"],
    }


@api_router.post("/ai/stream")
async def ai_stream(payload: AssistChatIn, user=Depends(get_current_user_full)):
    """Server-Sent Events stream of AI assistant tokens.

    Frames:
      event: meta  -> {provider, model, badge, session_id, assistant}
      event: delta -> {content}
      event: error -> {message}
      event: done  -> {latency_ms, chars}
    """
    import json as _json

    await _consume_ai_credit(user)
    session_id = payload.session_id or f"{user['id']}:{payload.assistant}:{uuid.uuid4()}"
    plan = user.get("subscription_plan")

    async def event_generator():
        try:
            async for frame in ai_assistants.chat_stream(
                db, payload.assistant, session_id, user["id"], payload.message,
                subscription_plan=plan,
                user_context=user,
            ):
                ev = frame.pop("type", "delta")
                yield f"event: {ev}\ndata: {_json.dumps(frame)}\n\n"
        except ValueError as e:
            yield f"event: error\ndata: {_json.dumps({'message': str(e)})}\n\n"
        except Exception:  # noqa: BLE001
            logger.exception("ai_stream failure")
            yield f"event: error\ndata: {_json.dumps({'message': 'AI service error.'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@api_router.post("/marketing/caption")
async def marketing_caption(payload: CaptionIn, user=Depends(get_current_user_full)):
    """Zyntha caption generator — returns {caption, hashtags} for a post idea.

    Plan: free for all paying tiers (Starter included). Always Gemini 2.5 Flash.
    """
    try:
        result = await ai_assistants.generate_caption(
            db,
            user_id=user["id"],
            idea=payload.idea,
            platform=payload.platform,
            tone=payload.tone,
            user_context=user,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "caption": result["caption"],
        "hashtags": result["hashtags"],
        "provider": result["provider"],
        "model": result["model"],
        "platform": payload.platform,
        "badge": "Generated by Zyntha · Gemini",
    }


@api_router.get("/ai/history")
async def ai_history(session_id: str, user=Depends(get_current_user_full)):
    rows = await db.ai_messages.find(
        {"session_id": session_id, "user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    return {"messages": rows}


@api_router.get("/ai/sessions")
async def ai_sessions(
    assistant: str,
    user=Depends(get_current_user_full),
    limit: int = 30,
):
    """Return the user's past sessions with an assistant, newest first."""
    pipeline = [
        {"$match": {"assistant": assistant, "user_id": user["id"]}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$session_id",
            "last_at": {"$first": "$created_at"},
            "first_at": {"$last": "$created_at"},
            "last_role": {"$first": "$role"},
            "last_content": {"$first": "$content"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"last_at": -1}},
        {"$limit": min(max(limit, 1), 100)},
    ]
    cursor = db.ai_messages.aggregate(pipeline)
    rows = await cursor.to_list(length=None)
    sessions = [{
        "session_id": r["_id"],
        "last_at": r["last_at"],
        "first_at": r["first_at"],
        "messages": r["count"],
        "preview": (r["last_content"] or "")[:120],
    } for r in rows]
    return {"assistant": assistant, "sessions": sessions}


# ========================================================================
#  Founder / Builder Mode (founder only)
# ========================================================================
@api_router.get("/founder/presale-signups")
async def founder_presale(user=Depends(get_founder_user)):
    rows = await db.presale_signups.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    real = [r for r in rows if not r.get("is_test")]
    test = [r for r in rows if r.get("is_test")]
    return {
        "signups": real,
        "count": len(real),
        "real_count": len(real),
        "test_count": len(test),
        "total_count": len(rows),
    }


@api_router.get("/founder/stats")
async def founder_stats(user=Depends(get_founder_user)):
    total_presale = await db.presale_signups.count_documents({})
    real_presale = await db.presale_signups.count_documents({"is_test": {"$ne": True}})
    return {
        "presale_count": real_presale,
        "presale_total_count": total_presale,
        "presale_test_count": total_presale - real_presale,
        "user_count": await db.users.count_documents({}),
        "team_members": await db.team_members.count_documents({}),
        "ai_messages": await db.ai_messages.count_documents({}),
        "ai_calls": await db.ai_logs.count_documents({}),
    }


@api_router.get("/admin/ai-logs")
async def admin_ai_logs(
    user=Depends(get_founder_user),
    limit: int = 200,
    assistant: Optional[str] = None,
    provider: Optional[str] = None,
):
    """XPRIZE: returns per-call AI execution logs for the platform.

    Founder-only. Use ?assistant=zyntha&provider=gemini&limit=500 to filter.
    """
    q = {}
    if assistant:
        q["assistant"] = assistant
    if provider:
        q["provider"] = provider
    cursor = db.ai_logs.find(q, {"_id": 0}).sort("timestamp", -1).limit(min(max(limit, 1), 1000))
    rows = await cursor.to_list(length=None)
    return {
        "count": len(rows),
        "total": await db.ai_logs.count_documents(q),
        "logs": rows,
    }


@api_router.get("/founder/feature-flags")
async def founder_flags(user=Depends(get_founder_user)):
    row = await db.feature_flags.find_one({"singleton": True}, {"_id": 0})
    if not row:
        row = {
            "singleton": True,
            "ai_assistants_enabled": True,
            "presale_open": True,
            "beta_modules_enabled": False,
            "stripe_enabled": False,
            "beta_webhook_url": "",
        }
        await db.feature_flags.insert_one(dict(row))
    row.setdefault("beta_webhook_url", "")
    return row


class FeatureFlagsIn(BaseModel):
    ai_assistants_enabled: Optional[bool] = None
    presale_open: Optional[bool] = None
    beta_modules_enabled: Optional[bool] = None
    stripe_enabled: Optional[bool] = None
    beta_webhook_url: Optional[str] = Field(default=None, max_length=500)


@api_router.patch("/founder/feature-flags")
async def founder_flags_update(payload: FeatureFlagsIn, user=Depends(get_founder_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if updates:
        await db.feature_flags.update_one(
            {"singleton": True}, {"$set": updates}, upsert=True
        )
    return await db.feature_flags.find_one({"singleton": True}, {"_id": 0})


@api_router.post("/founder/beta-webhook/test")
async def founder_test_beta_webhook(user=Depends(get_founder_user)):
    """Send a sample 'New Beta Founder' ping to the configured webhook URL."""
    import webhook_notifier  # noqa: WPS433
    row = await db.feature_flags.find_one({"singleton": True}, {"_id": 0}) or {}
    url = (row.get("beta_webhook_url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="No webhook URL configured.")
    ok = await webhook_notifier.send(
        url,
        title="🎉 New Beta Founding Member (TEST)",
        body="This is a test ping from your Zynthoro Builder Mode.",
        fields={"Plan": "Beta Founding Member", "Amount": "€4.99/mo (locked)", "Source": "Test trigger"},
    )
    return {"sent": ok, "kind": webhook_notifier._detect_kind(url)}


# ========================================================================
#  Stripe placeholder (per user choice: skip Stripe completely until launch)
# ========================================================================
@api_router.get("/checkout/status")
async def checkout_status():
    mode = checkout_mod.stripe_mode()
    return {
        "enabled": mode in ("live", "test"),
        "mode": mode,
        "live": mode == "live",
        "message": (
            "Stripe live mode active." if mode == "live"
            else "Stripe test mode active." if mode == "test"
            else "Stripe not configured."
        ),
    }


# ========================================================================
#  Starter checkout
# ========================================================================


class StarterCheckoutIn(BaseModel):
    package_id: Literal["starter_standard"]
    origin_url: str


@api_router.post("/checkout/starter/session")
async def checkout_starter_session(
    payload: StarterCheckoutIn,
    request: Request,
    user=Depends(get_current_user_full),
):
    host_url = str(request.base_url)
    try:
        session = await checkout_mod.create_subscription_checkout(
            package_id=payload.package_id,
            host_url=host_url,
            origin_url=payload.origin_url,
            user_id=user["id"],
            user_email=user["email"],
            verification_id=None,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Stripe session creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session["session_id"],
        "user_id": user["id"],
        "user_email": user["email"],
        "package_id": payload.package_id,
        "amount": session["amount"],
        "currency": session["currency"],
        "metadata": session["metadata"],
        "payment_status": "initiated",
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "session_id": session["session_id"],
        "url": session["url"],
        "package_id": payload.package_id,
        "amount": session["amount"],
        "currency": session["currency"],
    }


@api_router.get("/checkout/starter/status/{session_id}")
async def checkout_starter_status(
    session_id: str,
    request: Request,
    user=Depends(get_current_user_full),
):
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    host_url = str(request.base_url)
    try:
        status = await checkout_mod.get_session_status(host_url, session_id)
    except Exception as e:
        logger.exception("Stripe status check failed")
        raise HTTPException(status_code=502, detail=f"Stripe status error: {e}")

    new_payment_status = status["payment_status"]
    new_status = status["status"]
    update = {
        "payment_status": new_payment_status,
        "status": new_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Idempotent post-payment provisioning
    if new_payment_status == "paid" and not txn.get("provisioned"):
        update["provisioned"] = True
        prev_plan = user.get("subscription_plan") or "Presale"
        user_update = {
            "subscription_plan": "Starter",
            "subscription_status": "active",
            "subscription_started_at": datetime.now(timezone.utc).isoformat(),
            "billing_first_amount_eur": txn["amount"],
        }
        await db.users.update_one({"id": user["id"]}, {"$set": user_update})
        # Activity feed event
        _verb = "🎉 Subscribed to" if prev_plan in (None, "", "Presale") else "🎉 Upgraded to"
        _sub = "New subscription" if prev_plan in (None, "", "Presale") else f"From {prev_plan}"
        asyncio.create_task(activity_log.log_event(
            db,
            workspace_owner=user["id"],
            actor_email=user["email"],
            event_type="subscription_starter_paid",
            icon="sparkles",
            title=f"{_verb} Starter",
            subtitle=_sub,
            href="/dashboard/settings",
        ))

    await db.payment_transactions.update_one(
        {"session_id": session_id}, {"$set": update}
    )

    return {
        "session_id": session_id,
        "payment_status": new_payment_status,
        "status": new_status,
        "amount": txn["amount"],
        "currency": txn["currency"],
        "package_id": txn["package_id"],
    }


# ========================================================================
#  Tier checkout — Kickstart lifetime, Compleet monthly, AI+Social top-ups
# ========================================================================


class TierCheckoutIn(BaseModel):
    tier_key: Literal[
        "kickstart_1", "kickstart_2", "kickstart_3",
        "compleet", "ai_social_week", "ai_social_month",
    ]
    origin_url: str
    consent_waiver: bool  # herroepingsrecht — must be True to proceed


@api_router.get("/tier/catalog")
async def tier_catalog_endpoint():
    """Public catalog of the 6 tiers — used by the landing page and
    subscribe pages to render pricing and description."""
    plans = []
    for key, t in tier_catalog.TIER_CATALOG.items():
        plans.append({
            "tier_key": key,
            "plan_key": t["plan_key"],
            "label": t["label"],
            "amount_eur": t["amount_eur"],
            "currency": t["currency"],
            "billing": t["billing"],
            "mode": t["mode"],
            "tagline": t["tagline"],
            "description": t["description"],
        })
    return {"plans": plans}


@api_router.post("/checkout/tier/session")
async def checkout_tier_session(
    payload: TierCheckoutIn,
    user=Depends(get_current_user_full),
):
    if not payload.consent_waiver:
        raise HTTPException(
            status_code=400,
            detail="Je moet uitdrukkelijk afstand doen van je herroepingsrecht om verder te gaan.",
        )
    if user.get("billing_exempt"):
        raise HTTPException(status_code=400, detail="Your account is billing-exempt — no checkout required.")

    # Startup validation hard-block: if the local TIER_CATALOG has drifted
    # from live Stripe (stale product/price ID), refuse to create a session
    # that we know will fail. Emergency bypass: SKIP_STRIPE_STARTUP_CHECK=1.
    if _CATALOG_HEALTH.get("boot_status") == "failed":
        raise HTTPException(
            status_code=503,
            detail=(
                "Onze prijsplannen zijn tijdelijk niet beschikbaar (interne configuratie). "
                "Onze ops-team is al gealarmeerd. Probeer het over enkele minuten opnieuw."
            ),
        )

    consent_at = datetime.now(timezone.utc).isoformat()
    try:
        session = await tier_catalog.create_tier_checkout_session(
            tier_key=payload.tier_key,
            origin_url=payload.origin_url,
            user_id=user["id"],
            user_email=user["email"],
            consent_at=consent_at,
        )
    except ValueError as e:
        # Unknown tier_key (defensive — Pydantic Literal usually catches
        # this first with 422, but keep the branch in case of upstream
        # validation changes).
        raise HTTPException(status_code=400, detail=str(e))
    except asyncio.TimeoutError:
        logger.warning("Tier checkout timed out talking to Stripe for tier=%s", payload.tier_key)
        raise HTTPException(
            status_code=504,
            detail="De betaal-provider reageert traag. Probeer het opnieuw.",
        )
    except stripe_sdk.error.InvalidRequestError as e:
        # Stripe rejected the request — stale price ID, deactivated product,
        # misconfigured coupon, etc. Convert to a clean 400 so the browser
        # (and Cloudflare) never see a 502.
        stripe_msg = getattr(e, "user_message", None) or str(e)
        logger.exception("Tier checkout: Stripe InvalidRequestError")
        raise HTTPException(
            status_code=400,
            detail=(
                "Checkout kan momenteel niet gestart worden — "
                "een van onze prijsplannen is tijdelijk niet beschikbaar. "
                f"(ref: {stripe_msg})"
            ),
        )
    except stripe_sdk.error.AuthenticationError:
        logger.exception("Tier checkout: Stripe AuthenticationError")
        raise HTTPException(status_code=500, detail="Payment provider not configured.")
    except stripe_sdk.error.RateLimitError:
        logger.warning("Tier checkout: Stripe RateLimitError")
        raise HTTPException(status_code=429, detail="Too many payment requests — try again in a moment.")
    except Exception as e:
        # Fall-through: any other Stripe/network error → 502 (Bad Gateway)
        logger.exception("Tier checkout session creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session["session_id"],
        "user_id": user["id"],
        "user_email": user["email"],
        "package_id": payload.tier_key,
        "plan_key": tier_catalog.get_tier(payload.tier_key)["plan_key"],
        "amount": session["amount"],
        "currency": session["currency"],
        "metadata": session["metadata"],
        "payment_status": "initiated",
        "status": "open",
        "consent_waiver": True,
        "consent_at": consent_at,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "session_id": session["session_id"],
        "url": session["url"],
        "tier_key": payload.tier_key,
        "amount": session["amount"],
        "currency": session["currency"],
    }


@api_router.get("/checkout/tier/status/{session_id}")
async def checkout_tier_status(
    session_id: str,
    user=Depends(get_current_user_full),
):
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user["id"]},
        {"_id": 0},
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    # Self-heal: if the webhook was missed but Stripe already collected
    # payment (or the 100%-off coupon made it "no_payment_required"),
    # re-run provisioning here so the user isn't stuck on Presale.
    # Runs in a background thread with a strict 5-second budget so a slow
    # Stripe API can never wedge the FastAPI event loop or trip Cloudflare's
    # 502 threshold during rollout.
    if not txn.get("provisioned"):
        try:
            import stripe as _stripe
            _stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

            def _retrieve():
                return _stripe.checkout.Session.retrieve(session_id)

            session = await asyncio.wait_for(
                asyncio.to_thread(_retrieve),
                timeout=5.0,
            )
            payment_status = session.get("payment_status")
            status_val = session.get("status")
            if payment_status in ("paid", "no_payment_required") and status_val == "complete":
                meta = session.get("metadata") or {}
                if (meta.get("kind") == "tier_purchase") and (meta.get("user_id") == user["id"]):
                    await _provision_tier_purchase(
                        user_id=user["id"],
                        meta=meta,
                        stripe_subscription=session.get("subscription"),
                        stripe_customer=session.get("customer"),
                        event_type="status_self_heal",
                        session_id=session_id,
                    )
                    await db.payment_transactions.update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "payment_status": payment_status,
                            "status": "complete",
                            "provisioned": True,
                            "stripe_subscription_id": session.get("subscription"),
                            "stripe_customer_id": session.get("customer"),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                            "healed_by": "status_endpoint",
                        }},
                    )
                    txn["payment_status"] = payment_status
                    txn["status"] = "complete"
                    txn["provisioned"] = True
                    logger.warning(
                        "Self-heal provisioned tier for user=%s session=%s (webhook missed)",
                        user["id"], session_id,
                    )
        except asyncio.TimeoutError:
            logger.warning(
                "Tier status self-heal timed out for session %s — returning cached DB state; "
                "frontend will retry on next poll.",
                session_id,
            )
        except Exception:
            logger.exception("Tier status self-heal failed for session %s", session_id)

    return {
        "session_id": session_id,
        "payment_status": txn.get("payment_status"),
        "status": txn.get("status"),
        "amount": txn.get("amount"),
        "currency": txn.get("currency"),
        "plan_key": txn.get("plan_key"),
        "tier_key": txn.get("package_id"),
        "provisioned": bool(txn.get("provisioned")),
    }



@api_router.post("/checkout/subscription/session")
async def checkout_subscription_session(
    payload: SubscriptionCheckoutIn,
    request: Request,
    user=Depends(get_current_user_full),
):
    """Create a Stripe Checkout Session in `subscription` mode for plan upgrades (Fix 8)."""
    if user.get("billing_exempt"):
        raise HTTPException(status_code=400, detail="Your account is billing-exempt — no checkout required.")
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    try:
        session = subs_mod.create_subscription_session(
            plan_key=payload.plan_key,
            origin_url=origin,
            user_id=user["id"],
            user_email=user["email"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Stripe subscription session creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session["session_id"],
        "user_id": user["id"],
        "user_email": user["email"],
        "kind": "subscription_change",
        "plan_key": payload.plan_key,
        "amount_eur": session["amount_eur"],
        "payment_status": "initiated",
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"url": session["url"], "session_id": session["session_id"], "plan_key": payload.plan_key}


@api_router.post("/checkout/seats/session")
async def checkout_seats_session(
    payload: SeatsCheckoutIn,
    request: Request,
    user=Depends(get_current_user_full),
):
    """Create a Stripe Checkout Session for extra team-seat add-ons (Fix 9)."""
    if user.get("billing_exempt"):
        raise HTTPException(status_code=400, detail="Your account is billing-exempt — extra seats are free.")
    plan = user.get("subscription_plan") or "Presale"
    # Normalise Enterprise variants — they get unlimited seats, no checkout needed
    if plan.startswith("Enterprise"):
        raise HTTPException(status_code=400, detail="Your Enterprise plan already includes unlimited seats.")
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    try:
        session = subs_mod.create_seats_session(
            current_plan=plan,
            quantity=payload.quantity,
            origin_url=origin,
            user_id=user["id"],
            user_email=user["email"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Stripe seats session creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session["session_id"],
        "user_id": user["id"],
        "user_email": user["email"],
        "kind": "seat_addon",
        "plan_key": plan,
        "seat_quantity": payload.quantity,
        "unit_amount_eur": session["unit_amount_eur"],
        "payment_status": "initiated",
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "url": session["url"],
        "session_id": session["session_id"],
        "quantity": payload.quantity,
        "unit_amount_eur": session["unit_amount_eur"],
    }


@api_router.get("/checkout/session/{session_id}")
async def checkout_session_status(
    session_id: str,
    user=Depends(get_current_user_full),
):
    """Return high-level status for any Checkout Session this user owns."""
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Session not found.")
    try:
        summary = subs_mod.get_session_summary(session_id)
    except Exception as e:
        logger.warning("Stripe session lookup failed: %s", e)
        summary = {"status": "unknown"}
    return {"txn": txn, "stripe": summary}


@api_router.get("/founder/stripe-metrics")
async def founder_stripe_metrics(user=Depends(get_founder_user)):
    """Live Stripe MRR / ARR / breakdown for the Builder Mode panel."""
    try:
        data = subs_mod.compute_stripe_mrr()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Stripe metrics fetch failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")
    return data


# =====================================================================
#  Beta Founding Member program — public endpoints
# =====================================================================
class BetaCheckoutIn(BaseModel):
    origin_url: str = Field(min_length=8, max_length=500)
    email: Optional[str] = Field(default=None, max_length=320)


@api_router.get("/beta/status")
async def beta_status():
    """Public counter — how many beta spots remain."""
    try:
        return subs_mod.beta_status()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("beta_status failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")


@api_router.get("/pricing/catalog")
async def pricing_catalog():
    """Public catalog of plans with their Stripe Payment Links.

    Used by the marketing site to wire CTAs directly to Stripe without a
    backend round-trip.
    """
    return {
        "plans": [
            {
                "plan_key": key,
                "label": cfg.get("label", key),
                "amount_eur": cfg.get("amount_eur"),
                "payment_link": cfg.get("payment_link"),
            }
            for key, cfg in subs_mod.PLAN_CATALOG.items()
        ],
        "beta": {
            "amount_eur": "4.99",
            "payment_link": subs_mod.BETA_PAYMENT_LINK,
        },
    }


@api_router.post("/beta/checkout")
async def beta_checkout(payload: BetaCheckoutIn):
    """Create a Stripe Checkout session for the beta program.

    Returns 410 Gone if all 100 spots are filled.
    """
    try:
        status = subs_mod.beta_status()
    except Exception as e:
        logger.exception("beta_checkout: status fetch failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")
    if status["capped"]:
        raise HTTPException(
            status_code=410,
            detail="All 100 beta founding member spots are taken. Visit /#pricing for our Starter plan.",
        )
    try:
        session = subs_mod.create_beta_session(payload.origin_url, payload.email)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("beta_checkout: session creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")
    return {
        **session,
        "spots_remaining": status["spots_remaining"] - 1,
    }



async def _provision_tier_purchase(
    *,
    user_id: str,
    meta: dict,
    stripe_subscription: Optional[str],
    stripe_customer: Optional[str],
    event_type: str,
    session_id: str,
) -> None:
    """Idempotent provisioning for tier_purchase Stripe sessions.
    Called from the webhook AND from the status endpoint as a self-heal
    fallback (e.g. when a webhook was missed or dropped)."""
    tier_key = meta.get("tier_key") or ""
    plan_key = meta.get("plan_key") or ""
    tier_def = tier_catalog.get_tier(tier_key)
    # NOTE: TIER_CATALOG holds Stripe pricing metadata only; the credit
    # quota + period lives in TIER_FEATURES keyed by plan_key. Do NOT read
    # credit fields from tier_def — that was the source of a revenue leak
    # where every tier provisioned with ai_credits_limit=None (unlimited).
    features = tier_catalog.TIER_FEATURES.get(plan_key) or {}
    billing = (tier_def or {}).get("billing", "lifetime")

    prev_doc = await db.users.find_one(
        {"id": user_id}, {"subscription_plan": 1, "email": 1}
    )
    prev_plan = (prev_doc or {}).get("subscription_plan") or "Presale"
    user_email_x = (prev_doc or {}).get("email")

    credits_limit = features.get("ai_credits_limit")
    credits_period = features.get("ai_credits_period", "month")
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    period_end = None
    if billing == "one_time_week":
        period_end = (now_dt + timedelta(days=7)).isoformat()
    elif billing == "one_time_month":
        period_end = (now_dt + timedelta(days=30)).isoformat()

    update_fields = {
        "subscription_plan": plan_key,
        "subscription_status": "active",
        "subscription_started_at": now_iso,
        "is_lifetime": billing == "lifetime",
        "billing_model": billing,
        "consent_waiver": True,
        "consent_waiver_at": meta.get("consent_at") or now_iso,
        "ai_credits_limit": credits_limit,
        "ai_credits_period": credits_period,
        "ai_credits_used_this_period": 0,
        "ai_credits_period_started_at": now_iso,
        "ai_credits_period_ends_at": period_end,
    }
    if billing == "monthly":
        update_fields["stripe_subscription_id"] = stripe_subscription
        update_fields["stripe_customer_id"] = stripe_customer

    await db.users.update_one({"id": user_id}, {"$set": update_fields})

    feed_verb = "🎉 Purchased" if billing != "monthly" else "🎉 Subscribed to"
    feed_sub = "Lifetime access" if billing == "lifetime" else (
        f"From {prev_plan}" if prev_plan and prev_plan != plan_key else "New subscription"
    )
    asyncio.create_task(activity_log.log_event(
        db,
        workspace_owner=user_id,
        actor_email=user_email_x,
        event_type=f"tier_{tier_key}_activated",
        icon="sparkles",
        title=f"{feed_verb} {plan_key}",
        subtitle=feed_sub,
        href="/dashboard/settings",
    ))
    alert_kind_tier = "subscribe" if prev_plan in (None, "Presale", "") else "upgrade"
    asyncio.create_task(email_service.send_stripe_alert(
        kind=alert_kind_tier,
        event_type=event_type,
        user_email=user_email_x,
        user_id=user_id,
        plan_key=plan_key,
        amount_eur=float(meta.get("amount_eur") or 0) or None,
        stripe_session_id=session_id,
        stripe_subscription_id=stripe_subscription,
        extra={"Tier": tier_key, "Billing": billing},
    ))
    logger.info(
        "User %s activated tier %s (plan=%s billing=%s) via %s",
        user_id, tier_key, plan_key, billing, event_type,
    )


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    host_url = str(request.base_url)
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    # First try direct Stripe SDK verification — this works for ALL event types,
    # including subscription events from Fix 8 & 9 plus the legacy Starter flow.
    event = None
    if webhook_secret:
        try:
            stripe_sdk.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
            event = stripe_sdk.Webhook.construct_event(body, sig, webhook_secret)
        except Exception as e:
            logger.warning("Stripe webhook SDK verify failed: %s", e)

    if event:
        event_type = event.get("type")
        obj = event["data"]["object"] if event.get("data") else {}

        # === Subscription checkout completed (Fix 8 + Fix 9) ===
        # Also catches one-time-payment Checkout Sessions for Kickstart
        # lifetime tiers and AI+Social top-ups — those come in with
        # mode="payment" and kind="tier_purchase" in the metadata.
        _mode = obj.get("mode")
        _kind_hint = ((obj.get("metadata") or {}).get("kind") or "")
        if event_type == "checkout.session.completed" and (
            _mode == "subscription" or (_mode == "payment" and _kind_hint == "tier_purchase")
        ):
            session_id = obj.get("id")
            meta = obj.get("metadata") or {}
            user_id = meta.get("user_id") or obj.get("client_reference_id")
            kind = meta.get("kind", "")
            now_iso = datetime.now(timezone.utc).isoformat()

            # --- Beta Founding Member detection (Stripe Payment Link path) ---
            # Payment-link sessions don't carry our metadata. Identify by
            # the line-item product matching the beta product ID.
            items = []
            try:
                expanded = stripe_sdk.checkout.Session.retrieve(
                    session_id, expand=["line_items.data.price"]
                )
                items = (expanded.get("line_items") or {}).get("data") or []
            except Exception:
                items = []
            beta_hit = any(
                ((it.get("price") or {}).get("product") == subs_mod.BETA_PRODUCT_ID)
                for it in items
            )

            if beta_hit or kind == "beta_founder":
                email_addr = obj.get("customer_details", {}).get("email") or obj.get("customer_email")
                country = (obj.get("customer_details", {}).get("address") or {}).get("country")
                flags = await db.feature_flags.find_one({"singleton": True}, {"_id": 0}) or {}
                webhook_url = (flags.get("beta_webhook_url") or "").strip()
                # Persist for the founder digest + spot counting fallback
                await db.beta_signups.update_one(
                    {"session_id": session_id},
                    {"$set": {
                        "session_id": session_id,
                        "email": email_addr,
                        "country": country,
                        "stripe_subscription_id": obj.get("subscription"),
                        "stripe_customer_id": obj.get("customer"),
                        "created_at": now_iso,
                    }},
                    upsert=True,
                )
                # Count remaining spots for the message
                try:
                    status = subs_mod.beta_status()
                    remaining = status.get("spots_remaining")
                except Exception:
                    remaining = None
                if webhook_url:
                    import webhook_notifier  # noqa: WPS433
                    asyncio.create_task(webhook_notifier.send(
                        webhook_url,
                        title="🎉 New Beta Founding Member",
                        body=f"*{email_addr or 'A new founder'}* just claimed a Zynthoro Beta spot.",
                        fields={
                            "Plan":      "Beta Founding Member",
                            "Amount":    "€4.99/mo (locked for life)",
                            "Country":   country or "—",
                            "Remaining": f"{remaining}/100" if remaining is not None else "—",
                            "Session":   session_id,
                        },
                    ))
                    # Bonus ping when we hit the cap
                    if remaining == 0:
                        asyncio.create_task(webhook_notifier.send(
                            webhook_url,
                            title="🔒 Beta is SOLD OUT — all 100 spots taken!",
                            body="The Zynthoro Beta Founding Member program has just closed. New signups now route to standard pricing.",
                            fields={"Milestone": "100 / 100", "Action": "Auto-redirect to /#pricing is live"},
                        ))
                logger.info("Beta founder signup recorded: %s (remaining=%s)", email_addr, remaining)

            # --- Enterprise tier detection (€2,499+ /mo) ---
            hit_keys = []
            try:
                ent_product_ids = {
                    subs_mod.PLAN_CATALOG[k]["product_id"]
                    for k in ("Enterprise Basic", "Enterprise Plus", "Enterprise Advanced")
                }
                for it in items:
                    p = it.get("price") or {}
                    pid = p.get("product")
                    if pid in ent_product_ids:
                        for plan_key, cfg in subs_mod.PLAN_CATALOG.items():
                            if cfg["product_id"] == pid:
                                hit_keys.append(plan_key)
                                break
            except Exception:
                hit_keys = []

            if hit_keys:
                flags = await db.feature_flags.find_one({"singleton": True}, {"_id": 0}) or {}
                webhook_url = (flags.get("beta_webhook_url") or "").strip()
                email_addr = obj.get("customer_details", {}).get("email") or obj.get("customer_email")
                country = (obj.get("customer_details", {}).get("address") or {}).get("country")
                tier_label = hit_keys[0]
                tier_amount = subs_mod.PLAN_CATALOG.get(tier_label, {}).get("amount_eur", "?")
                if webhook_url:
                    import webhook_notifier  # noqa: WPS433
                    asyncio.create_task(webhook_notifier.send(
                        webhook_url,
                        title=f"💎 New {tier_label} subscription!",
                        body=f"*{email_addr or 'A new enterprise customer'}* just signed up for {tier_label}.",
                        fields={
                            "Plan":    tier_label,
                            "Amount":  f"€{tier_amount}/mo",
                            "Country": country or "—",
                            "Session": session_id,
                        },
                    ))
                logger.info("Enterprise signup recorded: %s tier=%s", email_addr, tier_label)

            if user_id and kind == "subscription_change":
                plan_key = meta.get("plan_key") or "Starter"
                # Look up prior plan so we can classify upgrade vs downgrade
                prev_doc = await db.users.find_one({"id": user_id}, {"subscription_plan": 1, "email": 1})
                prev_plan = (prev_doc or {}).get("subscription_plan") or "Presale"
                user_email = (prev_doc or {}).get("email")
                await db.users.update_one(
                    {"id": user_id},
                    {"$set": {
                        "subscription_plan": plan_key,
                        "subscription_status": "active",
                        "subscription_started_at": now_iso,
                        "stripe_subscription_id": obj.get("subscription"),
                        "stripe_customer_id": obj.get("customer"),
                        # New paid plan supersedes any founder window
                        "founder_pricing": False,
                    }},
                )
                logger.info("User %s plan -> %s via session %s", user_id, plan_key, session_id)
                # Alert email
                alert_kind = "subscribe" if prev_plan in (None, "Presale", "") else (
                    "upgrade" if _plan_rank(plan_key) > _plan_rank(prev_plan) else "downgrade"
                )
                # Activity feed event — show on the user's dashboard
                _feed_verb = {
                    "upgrade":   "🎉 Upgraded to",
                    "downgrade": "Downgraded to",
                    "subscribe": "🎉 Subscribed to",
                }.get(alert_kind, "Switched to")
                _feed_sub = f"From {prev_plan}" if prev_plan and prev_plan != plan_key else "New subscription"
                asyncio.create_task(activity_log.log_event(
                    db,
                    workspace_owner=user_id,
                    actor_email=user_email,
                    event_type=f"subscription_{alert_kind}",
                    icon="sparkles",
                    title=f"{_feed_verb} {plan_key}",
                    subtitle=_feed_sub,
                    href="/dashboard/settings",
                ))
                asyncio.create_task(email_service.send_stripe_alert(
                    kind=alert_kind,
                    event_type=event_type,
                    user_email=user_email,
                    user_id=user_id,
                    plan_key=plan_key,
                    amount_eur=float(meta.get("amount_eur") or 0) or None,
                    stripe_session_id=session_id,
                    stripe_subscription_id=obj.get("subscription"),
                    extra={"Previous plan": prev_plan} if prev_plan and prev_plan != plan_key else None,
                ))

            elif user_id and kind == "seat_addon":
                try:
                    qty = int(meta.get("seat_quantity") or 1)
                except Exception:
                    qty = 1
                prev_doc = await db.users.find_one({"id": user_id}, {"email": 1, "subscription_plan": 1})
                await db.users.update_one(
                    {"id": user_id},
                    {
                        "$inc": {"extra_seats": qty},
                        "$set": {
                            "stripe_seats_subscription_id": obj.get("subscription"),
                            "updated_at": now_iso,
                        },
                    },
                )
                logger.info("User %s purchased %d extra seats via session %s", user_id, qty, session_id)
                asyncio.create_task(email_service.send_stripe_alert(
                    kind="seats",
                    event_type=event_type,
                    user_email=(prev_doc or {}).get("email"),
                    user_id=user_id,
                    plan_key=(prev_doc or {}).get("subscription_plan"),
                    quantity=qty,
                    stripe_session_id=session_id,
                    stripe_subscription_id=obj.get("subscription"),
                ))

            elif user_id and kind == "tier_purchase":
                # Kickstart lifetime, Compleet, AI+Social top-ups.
                await _provision_tier_purchase(
                    user_id=user_id,
                    meta=meta,
                    stripe_subscription=obj.get("subscription"),
                    stripe_customer=obj.get("customer"),
                    event_type=event_type,
                    session_id=session_id,
                )

            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "payment_status": obj.get("payment_status") or "paid",
                    "status": "complete",
                    "provisioned": True,
                    "stripe_subscription_id": obj.get("subscription"),
                    "stripe_customer_id": obj.get("customer"),
                    "updated_at": now_iso,
                }},
            )
            return {"received": True, "kind": kind}

        # === Subscription cancelled / lapsed ===
        if event_type == "customer.subscription.deleted":
            sub_id = obj.get("id")
            cancelled_user = await db.users.find_one(
                {"stripe_subscription_id": sub_id}, {"id": 1, "email": 1, "subscription_plan": 1}
            )
            await db.users.update_one(
                {"stripe_subscription_id": sub_id},
                {"$set": {
                    "subscription_status": "cancelled",
                    "subscription_cancelled_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            if cancelled_user and cancelled_user.get("id"):
                asyncio.create_task(activity_log.log_event(
                    db,
                    workspace_owner=cancelled_user["id"],
                    actor_email=cancelled_user.get("email"),
                    event_type="subscription_cancelled",
                    icon="sparkles",
                    title=f"Subscription cancelled — {cancelled_user.get('subscription_plan') or 'Plan'}",
                    subtitle="You can resubscribe anytime from Settings",
                    href="/dashboard/settings",
                ))
            asyncio.create_task(email_service.send_stripe_alert(
                kind="cancel",
                event_type=event_type,
                user_email=(cancelled_user or {}).get("email"),
                user_id=(cancelled_user or {}).get("id"),
                plan_key=(cancelled_user or {}).get("subscription_plan"),
                stripe_subscription_id=sub_id,
            ))
            return {"received": True, "kind": "subscription_cancelled"}

        # === Payment failed ===
        if event_type == "invoice.payment_failed":
            cust_email = obj.get("customer_email") or ""
            amount_eur = (obj.get("amount_due") or 0) / 100 if obj.get("amount_due") else None
            asyncio.create_task(email_service.send_stripe_alert(
                kind="payment_failed",
                event_type=event_type,
                user_email=cust_email or None,
                amount_eur=amount_eur,
                stripe_subscription_id=obj.get("subscription"),
                extra={"Attempt": obj.get("attempt_count"), "Next attempt": obj.get("next_payment_attempt")},
            ))
            # Slack/Discord ping for the founder team
            flags = await db.feature_flags.find_one({"singleton": True}, {"_id": 0}) or {}
            webhook_url = (flags.get("beta_webhook_url") or "").strip()
            if webhook_url:
                import webhook_notifier  # noqa: WPS433
                asyncio.create_task(webhook_notifier.send(
                    webhook_url,
                    title="⚠️ Payment failed",
                    body=f"Stripe could not collect a payment from *{cust_email or 'a customer'}*.",
                    fields={
                        "Amount":       f"€{amount_eur:.2f}" if amount_eur is not None else "—",
                        "Attempt":      str(obj.get("attempt_count") or "—"),
                        "Next attempt": str(obj.get("next_payment_attempt") or "—"),
                        "Subscription": str(obj.get("subscription") or "—"),
                    },
                ))
            return {"received": True, "kind": "payment_failed"}

        # === Trial ending soon ===
        if event_type == "customer.subscription.trial_will_end":
            cust = obj.get("customer")
            user_doc = await db.users.find_one({"stripe_customer_id": cust}, {"email": 1, "id": 1, "subscription_plan": 1})
            asyncio.create_task(email_service.send_stripe_alert(
                kind="trial_end",
                event_type=event_type,
                user_email=(user_doc or {}).get("email"),
                user_id=(user_doc or {}).get("id"),
                plan_key=(user_doc or {}).get("subscription_plan"),
                stripe_subscription_id=obj.get("id"),
                extra={"Trial ends": obj.get("trial_end")},
            ))
            return {"received": True, "kind": "trial_end"}

        # === Catch-all: any other event we want to know about ===
        if event_type in (
            "customer.subscription.updated",
            "invoice.paid",
            "charge.refunded",
            "checkout.session.expired",
        ):
            asyncio.create_task(email_service.send_stripe_alert(
                kind="other",
                event_type=event_type,
                stripe_subscription_id=obj.get("subscription") or obj.get("id"),
            ))
            return {"received": True, "kind": event_type}

    # === Fallback: legacy Starter one-time flow via Emergent wrapper ===
    try:
        client = checkout_mod._client(host_url)
        legacy_event = await client.handle_webhook(body, sig)
    except Exception as e:
        if not event:
            logger.warning("Stripe webhook verify failed (both paths): %s", e)
            raise HTTPException(status_code=400, detail="Invalid webhook")
        return {"received": True, "kind": event.get("type") if event else "unknown"}

    session_id = getattr(legacy_event, "session_id", None)
    if session_id:
        txn = await db.payment_transactions.find_one({"session_id": session_id})
        if txn and not txn.get("provisioned") and getattr(legacy_event, "payment_status", "") == "paid":
            meta = txn.get("metadata") or {}
            months = int(meta.get("founder_window_months") or 0)
            founder_window = checkout_mod.founder_pricing_window(months)
            await db.users.update_one(
                {"id": txn["user_id"]},
                {"$set": {
                    "subscription_plan": "Starter",
                    "subscription_status": "active",
                    "subscription_started_at": datetime.now(timezone.utc).isoformat(),
                    "billing_first_amount_eur": txn["amount"],
                    **founder_window,
                }},
            )
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "payment_status": "paid",
                    "status": "complete",
                    "provisioned": True,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
    return {"received": True}


# ========================================================================
#  Account / Company Settings
# ========================================================================
import base64 as _b64  # noqa: E402

MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB raw upload
ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}


class CompanySettingsIn(BaseModel):
    company_name: Optional[str] = None
    company_country: Optional[str] = None
    company_industry: Optional[str] = None
    company_employees: Optional[str] = None
    company_website: Optional[str] = None
    vat_number: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None


@api_router.get("/account/me")
async def account_me(user=Depends(get_current_user_full)):
    # has_company_logo is already populated by get_current_user_full.
    return user


@api_router.get("/demo/projects")
async def demo_projects(user=Depends(get_current_user_full)):
    """List demo projects for the current workspace (jury demo + any future demo seeds)."""
    rows = await db.demo_projects.find(
        {"workspace_owner": user["id"]}, {"_id": 0}
    ).sort("due", 1).to_list(50)
    return {"projects": rows}


@api_router.get("/demo/invoices")
async def demo_invoices(user=Depends(get_current_user_full)):
    rows = await db.demo_invoices.find(
        {"workspace_owner": user["id"]}, {"_id": 0}
    ).sort("issued", -1).to_list(50)
    total = sum((r.get("amount_eur") or 0) for r in rows)
    paid = sum((r.get("amount_eur") or 0) for r in rows if r.get("status") == "Paid")
    return {"invoices": rows, "total_eur": total, "paid_eur": paid}


@api_router.patch("/account/company")
async def account_update_company(payload: CompanySettingsIn, user=Depends(get_current_user_full)):
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0, "totp_secret": 0, "company_logo_data": 0})
    return fresh


@api_router.post("/account/logo")
async def account_upload_logo(
    file: UploadFile = File(...),
    user=Depends(get_current_user_full),
):
    ctype = (file.content_type or "").lower()
    if ctype not in ALLOWED_LOGO_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG, JPEG, SVG or WebP images are accepted.")
    data = await file.read()
    if len(data) < 64:
        raise HTTPException(status_code=400, detail="File looks empty.")
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=413, detail="Logo too large (max 2 MB).")
    encoded = _b64.b64encode(data).decode("ascii")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "company_logo_data": encoded,
            "company_logo_mime": ctype,
            "company_logo_size": len(data),
            "company_logo_filename": file.filename,
            "company_logo_updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {
        "ok": True,
        "size": len(data),
        "mime": ctype,
        "url": f"/api/account/logo?u={user['id']}",
    }


@api_router.delete("/account/logo")
async def account_delete_logo(user=Depends(get_current_user_full)):
    await db.users.update_one(
        {"id": user["id"]},
        {"$unset": {
            "company_logo_data": "",
            "company_logo_mime": "",
            "company_logo_size": "",
            "company_logo_filename": "",
            "company_logo_updated_at": "",
        }},
    )
    return {"ok": True}


@api_router.get("/account/logo")
async def account_get_logo(u: Optional[str] = None, user=Depends(get_current_user_full)):
    """Stream the logo back. If `u` is supplied, must match the caller's id."""
    target_id = u or user["id"]
    if target_id != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    rec = await db.users.find_one({"id": target_id}, {"company_logo_data": 1, "company_logo_mime": 1})
    if not rec or not rec.get("company_logo_data"):
        raise HTTPException(status_code=404, detail="No logo uploaded.")
    from fastapi.responses import Response
    raw = _b64.b64decode(rec["company_logo_data"])
    return Response(content=raw, media_type=rec.get("company_logo_mime") or "image/png")


# ========================================================================
#  Startup
# ========================================================================
async def seed_founder():
    email = os.environ.get("FOUNDER_EMAIL", "regie@myrootzz.com").lower().strip()
    password = os.environ.get("FOUNDER_PASSWORD", "Zynthoro2026!")
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": email,
            "first_name": "Founder",
            "last_name": "",
            "company": "Casa Haya International BV",
            "password_hash": hash_password(password),
            "role": "Founder Owner Unlimited",
            "is_founder": True,
            "is_unlimited": True,
            "billing_exempt": True,
            "subscription_plan": "Enterprise Unlimited",
            "email_verified": True,
            "twofa_enabled": False,
            "twofa_method": None,
            "onboarding_completed": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Founder account seeded: %s", email)
    else:
        # Keep founder flags consistent with .env config
        await db.users.update_one(
            {"email": email},
            {"$set": {
                "is_founder": True,
                "is_unlimited": True,
                "billing_exempt": True,
                "role": "Founder Owner Unlimited",
                "email_verified": True,
            }},
        )


async def seed_jury_demo():
    """XPRIZE / investor demo account, pre-populated with realistic sample data.

    Always force-resets the user's auth state on each boot so judges land in
    the dashboard with one click — no email verification, no 2FA prompt, no
    onboarding wizard. The flag `is_demo=True` exempts the account from any
    real billing or destructive operations.
    """
    email = "jury@zynthoro.ai"
    password = "ZynthoroDemo2026!"
    now_iso = datetime.now(timezone.utc).isoformat()

    base_doc = {
        "email": email,
        "first_name": "XPRIZE",
        "last_name": "Jury",
        "company": "Zynthoro Demo Workspace",
        "password_hash": hash_password(password),
        "role": "Demo · Enterprise",
        "is_demo": True,
        "is_unlimited": True,
        "billing_exempt": True,
        "subscription_plan": "Enterprise Advanced",
        "subscription_status": "active",
        "email_verified": True,
        "twofa_enabled": False,
        "twofa_method": None,
        "onboarding_completed": True,
        "updated_at": now_iso,
    }

    existing = await db.users.find_one({"email": email})
    if not existing:
        user_id = str(uuid.uuid4())
        await db.users.insert_one({
            "id": user_id,
            **base_doc,
            "created_at": now_iso,
        })
        logger.info("Jury demo account seeded: %s", email)
    else:
        user_id = existing["id"]
        # Always force-reset password + flags so judges can never be locked out
        # even if a previous boot left the account in a half-state.
        await db.users.update_one({"id": user_id}, {"$set": base_doc})

    # ----- Demo data (idempotent — only inserts if absent) -----
    workspace_owner = user_id

    # Team members
    if await db.team_members.count_documents({"workspace_owner": workspace_owner}) == 0:
        demo_team = [
            ("amelia.chen@zynthoro-demo.ai",  "Amelia Chen",   "Director",        9, "active"),
            ("daniel.kruger@zynthoro-demo.ai","Daniel Krüger", "Senior Manager",  7, "active"),
            ("priya.shah@zynthoro-demo.ai",   "Priya Shah",    "Manager",         5, "active"),
            ("luca.rossi@zynthoro-demo.ai",   "Luca Rossi",    "Employee",        3, "active"),
            ("nina.adebayo@zynthoro-demo.ai", "Nina Adebayo",  "Intern",          1, "invited"),
        ]
        await db.team_members.insert_many([
            {
                "id": str(uuid.uuid4()),
                "workspace_owner": workspace_owner,
                "email": em.lower(),
                "name": nm,
                "role": role,
                "level": lv,
                "status": st,
                "twofa": True,
                "last_login": now_iso,
                "created_at": now_iso,
                "is_demo": True,
            }
            for (em, nm, role, lv, st) in demo_team
        ])
        logger.info("Seeded %d demo team members for jury workspace", len(demo_team))

    # Projects
    if await db.demo_projects.count_documents({"workspace_owner": workspace_owner}) == 0:
        demo_projects = [
            {"name": "Q1 Product Roadmap",      "domain": "Project Management", "status": "On track",  "progress": 72,  "owner": "Amelia Chen",   "due": "2026-03-31"},
            {"name": "Spring Marketing Launch", "domain": "Marketing & Content","status": "On track",  "progress": 48,  "owner": "Priya Shah",    "due": "2026-04-15"},
            {"name": "SOC 2 Type II Audit",     "domain": "Compliance",         "status": "At risk",   "progress": 31,  "owner": "Daniel Krüger", "due": "2026-05-30"},
            {"name": "EU Sales Pipeline 2026",  "domain": "Sales Admin",        "status": "On track",  "progress": 64,  "owner": "Luca Rossi",    "due": "2026-12-31"},
            {"name": "AI Caption Engine v2",    "domain": "Operations",         "status": "Completed", "progress": 100, "owner": "Amelia Chen",   "due": "2026-01-28"},
        ]
        await db.demo_projects.insert_many([
            {**p, "id": str(uuid.uuid4()), "workspace_owner": workspace_owner, "created_at": now_iso, "is_demo": True}
            for p in demo_projects
        ])
        logger.info("Seeded %d demo projects for jury workspace", len(demo_projects))

    # Invoices
    if await db.demo_invoices.count_documents({"workspace_owner": workspace_owner}) == 0:
        demo_invoices = [
            {"number": "ZY-2026-0042", "client": "Aurora Studios B.V.",       "amount_eur": 4990, "issued": "2026-01-04", "due": "2026-02-04", "status": "Paid"},
            {"number": "ZY-2026-0043", "client": "Helix Robotics GmbH",       "amount_eur": 8990, "issued": "2026-01-12", "due": "2026-02-12", "status": "Paid"},
            {"number": "ZY-2026-0044", "client": "Lumen Therapeutics PLC",    "amount_eur": 11990,"issued": "2026-01-21", "due": "2026-02-21", "status": "Sent"},
            {"number": "ZY-2026-0045", "client": "Sable & Co. Architects",    "amount_eur": 6990, "issued": "2026-01-28", "due": "2026-02-28", "status": "Sent"},
            {"number": "ZY-2026-0046", "client": "Verdant Foods Co-op",       "amount_eur": 3490, "issued": "2026-02-02", "due": "2026-03-02", "status": "Draft"},
            {"number": "ZY-2026-0047", "client": "Northwind Capital Partners","amount_eur": 24990,"issued": "2026-02-04", "due": "2026-03-04", "status": "Overdue"},
        ]
        await db.demo_invoices.insert_many([
            {**inv, "id": str(uuid.uuid4()), "workspace_owner": workspace_owner, "created_at": now_iso, "is_demo": True}
            for inv in demo_invoices
        ])
        logger.info("Seeded %d demo invoices for jury workspace", len(demo_invoices))

    # ----- Operations & Production demo data -----
    if await db.recipes.count_documents({"workspace_owner": workspace_owner}) == 0:
        demo_recipes = [
            {
                "name": "Sourdough Loaf · House Recipe",
                "code": "SD-001", "version": 1, "yield_qty": 12, "yield_unit": "loaves",
                "ingredients": [
                    {"name": "Organic flour", "quantity": 6000, "unit": "g", "cost_per_unit_eur": 0.0022},
                    {"name": "Sea salt",      "quantity":  120, "unit": "g", "cost_per_unit_eur": 0.0015},
                    {"name": "Sourdough starter", "quantity": 1200, "unit": "g", "cost_per_unit_eur": 0.0011},
                    {"name": "Filtered water", "quantity": 4200, "unit": "ml", "cost_per_unit_eur": 0.0003},
                ],
                "allergens": ["gluten"],
                "labour_cost_eur": 8.50, "overhead_eur": 4.20,
                "material_cost_eur": 17.36, "cost_total_eur": 30.06, "cost_per_unit_eur": 2.51,
            },
            {
                "name": "Cold-Press Apple Juice · 500ml",
                "code": "JUI-002", "version": 2, "yield_qty": 24, "yield_unit": "bottles",
                "ingredients": [
                    {"name": "Organic apples", "quantity": 18000, "unit": "g", "cost_per_unit_eur": 0.0024},
                    {"name": "Lemon juice",    "quantity":   240, "unit": "ml", "cost_per_unit_eur": 0.004},
                ],
                "allergens": [],
                "labour_cost_eur": 12.00, "overhead_eur": 6.00,
                "material_cost_eur": 44.16, "cost_total_eur": 62.16, "cost_per_unit_eur": 2.59,
            },
            {
                "name": "Lip Balm · Lavender Honey",
                "code": "CSM-104", "version": 3, "yield_qty": 200, "yield_unit": "tubes",
                "ingredients": [
                    {"name": "Beeswax",        "quantity": 800, "unit": "g", "cost_per_unit_eur": 0.018},
                    {"name": "Shea butter",    "quantity": 600, "unit": "g", "cost_per_unit_eur": 0.022},
                    {"name": "Coconut oil",    "quantity": 400, "unit": "g", "cost_per_unit_eur": 0.012},
                    {"name": "Lavender oil",   "quantity":  40, "unit": "ml", "cost_per_unit_eur": 0.480},
                    {"name": "Honey extract",  "quantity":  60, "unit": "ml", "cost_per_unit_eur": 0.220},
                ],
                "allergens": ["honey"],
                "labour_cost_eur": 24.00, "overhead_eur": 18.00,
                "material_cost_eur": 67.20, "cost_total_eur": 109.20, "cost_per_unit_eur": 0.55,
            },
        ]
        await db.recipes.insert_many([
            {**r, "id": str(uuid.uuid4()), "workspace_owner": workspace_owner,
             "created_at": now_iso, "updated_at": now_iso, "is_demo": True}
            for r in demo_recipes
        ])

    if await db.production_orders.count_documents({"workspace_owner": workspace_owner}) == 0:
        demo_orders = [
            {"order_no": "PO-20260201-A1B2C", "name": "Sourdough batch · Feb week 1",
             "status": "completed", "quantity": 240, "unit": "loaves", "scheduled_for": "2026-02-03",
             "location": "Bakery · Rotterdam", "cost_estimate_eur": 602.40, "cost_actual_eur": 615.10,
             "actual_quantity": 238},
            {"order_no": "PO-20260214-3F8K1", "name": "Cold-press juice run",
             "status": "in_progress", "quantity": 480, "unit": "bottles", "scheduled_for": "2026-02-15",
             "location": "Bottling line · Utrecht", "cost_estimate_eur": 1243.20, "cost_actual_eur": None,
             "actual_quantity": None},
            {"order_no": "PO-20260220-9C4D7", "name": "Lip balm production · Q1 batch",
             "status": "planned", "quantity": 4000, "unit": "tubes", "scheduled_for": "2026-02-22",
             "location": "Cosmetics lab · Amsterdam", "cost_estimate_eur": 2184.00, "cost_actual_eur": None,
             "actual_quantity": None},
        ]
        await db.production_orders.insert_many([
            {**o, "id": str(uuid.uuid4()), "workspace_owner": workspace_owner,
             "created_at": now_iso, "updated_at": now_iso, "is_demo": True}
            for o in demo_orders
        ])

    if await db.quality_inspections.count_documents({"workspace_owner": workspace_owner}) == 0:
        demo_qc = [
            {"production_order_id": "demo", "batch_lot": "LOT-260203-A1B2C9",
             "checklist": ["Crust colour", "Crumb structure", "Internal temp ≥ 96°C", "Weight 480-520g"],
             "results": ["pass", "pass", "pass", "pass"], "pass_count": 4, "fail_count": 0,
             "overall": "pass", "notes": "All loaves passed visual + temp checks."},
            {"production_order_id": "demo", "batch_lot": "LOT-260214-3F8K12",
             "checklist": ["Brix reading", "pH 3.4-3.8", "Visual clarity", "Cap seal torque"],
             "results": ["pass", "pass", "fail", "pass"], "pass_count": 3, "fail_count": 1,
             "overall": "fail", "notes": "Cloudy batch — re-strain step required before sealing."},
        ]
        await db.quality_inspections.insert_many([
            {**q, "id": str(uuid.uuid4()), "workspace_owner": workspace_owner,
             "created_at": now_iso, "is_demo": True}
            for q in demo_qc
        ])

    if await db.lots.count_documents({"workspace_owner": workspace_owner}) == 0:
        demo_lots = [
            {"lot_no": "LOT-260203-A1B2C9", "production_order_id": "demo",
             "expiry_date": "2026-02-10", "raw_material_lots": ["FLOUR-260120", "STARTER-260201"],
             "status": "active"},
            {"lot_no": "LOT-260214-3F8K12", "production_order_id": "demo",
             "expiry_date": "2026-04-14", "raw_material_lots": ["APPLE-260210", "LEMON-260212"],
             "status": "active"},
            {"lot_no": "LOT-260101-OLD45", "production_order_id": "demo",
             "expiry_date": "2026-01-25", "raw_material_lots": [], "status": "recalled"},
        ]
        await db.lots.insert_many([
            {**lot, "id": str(uuid.uuid4()), "workspace_owner": workspace_owner,
             "created_at": now_iso, "is_demo": True}
            for lot in demo_lots
        ])
        logger.info("Seeded operations demo data for jury workspace")


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.team_members.create_index([("workspace_owner", 1), ("email", 1)])
    await db.ai_messages.create_index([("session_id", 1), ("created_at", 1)])
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.ai_logs.create_index([("timestamp", -1)])
    await db.ai_logs.create_index([("assistant", 1), ("timestamp", -1)])
    await db.activity_events.create_index([("workspace_owner", 1), ("timestamp", -1)])
    await db.payment_transactions.create_index("session_id", unique=True)
    await seed_founder()
    await seed_jury_demo()
    # Validate Stripe tier catalog against live Stripe account.
    await _validate_stripe_catalog_on_startup()
    # Background scheduler: daily digest to info@zynthoro.ai at 07:00 UTC.
    import daily_digest  # noqa: WPS433
    app.state.digest_task = daily_digest.start_scheduler(db)


# Snapshot of the last catalog validation result. Set at startup and
# consumed by GET /api/tier/catalog/health + POST /api/checkout/tier/session.
# Missing prices/products are hard blockers on tier checkout (503).
_CATALOG_HEALTH: dict = {
    "checked_at": None,
    "ok": None,
    "report": None,
    "boot_status": "pending",  # 'pending' | 'ok' | 'failed' | 'skipped' | 'error'
}


async def _validate_stripe_catalog_on_startup() -> None:
    """Called from FastAPI startup. Fails LOUD (CRITICAL log + refuses tier
    checkouts) if any TIER_CATALOG entry is stale. Does NOT crash the
    process — the app still boots so unrelated endpoints (auth, dashboard)
    keep working while ops fixes the Stripe config.

    Set env `SKIP_STRIPE_STARTUP_CHECK=1` to bypass (emergency use only).
    """
    if os.environ.get("SKIP_STRIPE_STARTUP_CHECK", "").lower() in ("1", "true", "yes"):
        _CATALOG_HEALTH.update({
            "boot_status": "skipped",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "ok": None,
            "report": {"skipped": True},
        })
        logger.warning(
            "SKIP_STRIPE_STARTUP_CHECK is set — tier catalog was NOT validated against Stripe. "
            "Do not leave this on in production."
        )
        return

    try:
        report = await tier_catalog.validate_catalog_against_stripe()
    except asyncio.TimeoutError:
        _CATALOG_HEALTH.update({
            "boot_status": "error",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "ok": None,
            "report": {"error": "timeout talking to Stripe"},
        })
        logger.error(
            "Stripe catalog validation timed out — booting anyway. "
            "The tier checkout endpoint will still serve if the catalog is actually OK."
        )
        return
    except Exception as e:
        _CATALOG_HEALTH.update({
            "boot_status": "error",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "ok": None,
            "report": {"error": str(e)},
        })
        logger.exception(
            "Stripe catalog validation could not run — booting anyway. "
            "This is usually a transient network error."
        )
        return

    _CATALOG_HEALTH.update({
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ok": bool(report["ok"]),
        "report": report,
        "boot_status": "ok" if report["ok"] else "failed",
    })

    if report["ok"]:
        logger.info(
            "Stripe catalog validation ✅ — %d tier prices confirmed active in live Stripe.",
            report["checked"],
        )
    else:
        logger.critical(
            "STRIPE CATALOG VALIDATION FAILED — tier checkout endpoint will return 503 "
            "until this is fixed.\n"
            "  Missing prices:    %s\n"
            "  Missing products:  %s\n"
            "  Inactive prices:   %s\n"
            "  Amount mismatches: %s",
            report["missing_prices"],
            report["missing_products"],
            report["inactive_prices"],
            report["amount_mismatches"],
        )


@api_router.get("/tier/catalog/health")
async def tier_catalog_health():
    """Ops health endpoint — reports whether the local TIER_CATALOG still
    matches live Stripe. Public (safe, does not leak secrets)."""
    return _CATALOG_HEALTH


@app.on_event("shutdown")
async def shutdown():
    client.close()


app.include_router(api_router)

# Operations & Production module router
import operations_module  # noqa: E402
app.include_router(operations_module.build_router(db, get_current_user_full))

# Canva Connect integration router
import canva_module  # noqa: E402
app.include_router(canva_module.build_router(db, get_current_user_full))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
