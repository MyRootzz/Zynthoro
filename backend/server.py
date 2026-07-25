from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse
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
    # 24-hour free trial flag — set only when the landing-page CTA
    # deep-links to /signup?trial=1. Regular signups get is_trial=false.
    is_trial: bool = False


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
    # Optional list of ai_uploads.file_id values (from POST /api/ai/upload)
    # whose extracted text should be injected as context for this turn.
    file_ids: Optional[List[str]] = None


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
    # SEC-005 fix (2026-07-21): production is served over HTTPS behind
    # Cloudflare / k8s ingress, so the cookie MUST be marked Secure to
    # prevent leakage over a stray plaintext hop. Allow an explicit
    # opt-out ONLY for local dev via COOKIE_SECURE=false.
    secure_flag = os.environ.get("COOKIE_SECURE", "true").strip().lower() != "false"
    response.set_cookie(
        key="access_token", value=access_token, httponly=True,
        secure=secure_flag, samesite="lax", max_age=60 * 60 * 24, path="/",
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
    """Manually trigger the weekly pipeline digest email.

    By default, dedupes once per ISO week (matching the scheduler) and skips
    the send entirely if there is no activity in the window. Pass
    ``?force=true`` to bypass both the ISO-week and no-activity guards.
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
        "has_activity": daily_digest._has_activity(data),
        "presale_count": len(data["presale"]),
        "voice_lead_count": len(data["voice_leads"]),
        "voice_anonymous_count": data["voice_anonymous_count"],
        "purchase_count": len(data["purchases"]),
        "ai_messages_count": data["ai_messages_count"],
        "new_users_count": data["new_users_count"],
        "window_days": data["window_days"],
    }


@api_router.post("/founder/reset-jury-demo")
async def founder_reset_jury_demo(user=Depends(get_founder_user)):
    """Founder-only: wipe the jury demo workspace's Finance + Sales data
    and re-seed it with the original XPRIZE sample records.

    Only touches rows tagged `is_demo=True` for the jury user's workspace,
    so real work by any other account is never affected.
    """
    jury = await db.users.find_one({"email": "jury@zynthoro.ai"})
    if not jury:
        raise HTTPException(status_code=404, detail="Jury demo account not found.")
    wo = jury["id"]

    # 1) Wipe demo-flagged Finance + Sales + C2 records for the jury workspace.
    inv_del  = (await db.finance_invoices.delete_many({"workspace_owner": wo, "is_demo": True})).deleted_count
    pay_del  = (await db.finance_payments.delete_many({"workspace_owner": wo, "is_demo": True})).deleted_count
    lead_del = (await db.sales_leads.delete_many({"workspace_owner": wo, "is_demo": True})).deleted_count
    proj_del = (await db.projects.delete_many({"workspace_owner": wo, "is_demo": True})).deleted_count
    task_del = (await db.project_tasks.delete_many({"workspace_owner": wo, "is_demo": True})).deleted_count
    ms_del   = (await db.project_milestones.delete_many({"workspace_owner": wo, "is_demo": True})).deleted_count
    spr_del  = (await db.sprints.delete_many({"workspace_owner": wo, "is_demo": True})).deleted_count
    time_del = (await db.time_entries.delete_many({"workspace_owner": wo, "is_demo": True})).deleted_count
    # Also reset finance_settings so re-seed reinstalls the branded defaults
    # and the invoice sequence counter starts fresh.
    await db.finance_settings.delete_many({"workspace_owner": wo})

    # 2) Re-seed via the same helpers used at startup.
    now_iso = datetime.now(timezone.utc).isoformat()
    await _seed_finance_and_sales_demo(wo, now_iso)
    await _seed_projects_planning_time_demo(wo, now_iso)

    # 3) Count what we just re-seeded so the UI can confirm.
    inv_new  = await db.finance_invoices.count_documents({"workspace_owner": wo, "is_demo": True})
    pay_new  = await db.finance_payments.count_documents({"workspace_owner": wo, "is_demo": True})
    lead_new = await db.sales_leads.count_documents({"workspace_owner": wo, "is_demo": True})
    proj_new = await db.projects.count_documents({"workspace_owner": wo, "is_demo": True})
    task_new = await db.project_tasks.count_documents({"workspace_owner": wo, "is_demo": True})
    ms_new   = await db.project_milestones.count_documents({"workspace_owner": wo, "is_demo": True})
    spr_new  = await db.sprints.count_documents({"workspace_owner": wo, "is_demo": True})
    time_new = await db.time_entries.count_documents({"workspace_owner": wo, "is_demo": True})

    logger.info(
        "Founder %s reset jury demo — wiped inv=%d pay=%d lead=%d proj=%d task=%d ms=%d spr=%d time=%d, "
        "re-seeded inv=%d pay=%d lead=%d proj=%d task=%d ms=%d spr=%d time=%d.",
        user.get("email"),
        inv_del, pay_del, lead_del, proj_del, task_del, ms_del, spr_del, time_del,
        inv_new, pay_new, lead_new, proj_new, task_new, ms_new, spr_new, time_new,
    )
    return {
        "ok": True,
        "wiped":  {"invoices": inv_del,  "payments": pay_del,  "leads": lead_del,
                   "projects": proj_del, "tasks": task_del,    "milestones": ms_del,
                   "sprints": spr_del,   "time_entries": time_del},
        "seeded": {"invoices": inv_new,  "payments": pay_new,  "leads": lead_new,
                   "projects": proj_new, "tasks": task_new,    "milestones": ms_new,
                   "sprints": spr_new,   "time_entries": time_new},
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
    now_utc = datetime.now(timezone.utc)
    trial_expires_at = None
    if payload.is_trial:
        trial_expires_at = (now_utc + timedelta(hours=24)).isoformat()
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
        "created_at": now_utc.isoformat(),
        # Trial mode fields — only populated on `?trial=1` signups.
        "is_trial": bool(payload.is_trial),
        "trial_started_at": now_utc.isoformat() if payload.is_trial else None,
        "trial_expires_at": trial_expires_at,
        "trial_ai_daily": {},  # {"YYYY-MM-DD": {"zyntha": N, ...}}
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


# 24-hour free trial — daily AI message cap per assistant.
TRIAL_AI_DAILY_CAP = 10


async def _check_and_bump_trial_ai_cap(user: dict, assistant_key: str) -> None:
    """For trial users only: enforce a per-day, per-assistant message cap
    (currently 10). No-op for non-trial users. Raises HTTP 429 when hit.
    Increments the daily counter atomically."""
    if not user.get("is_trial"):
        return
    today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily = (user.get("trial_ai_daily") or {}).get(today_key) or {}
    current = int(daily.get(assistant_key) or 0)
    if current >= TRIAL_AI_DAILY_CAP:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "TRIAL_AI_DAILY_CAP",
                "message": (
                    f"You've hit today's {TRIAL_AI_DAILY_CAP}-message limit for this assistant during your free trial. "
                    "Upgrade to a Kickstart tier for unlimited access."
                ),
                "cap": TRIAL_AI_DAILY_CAP,
                "assistant": assistant_key,
            },
        )
    field = f"trial_ai_daily.{today_key}.{assistant_key}"
    await db.users.update_one(
        {"id": user["id"]},
        {"$inc": {field: 1}},
    )


async def _consume_ai_credit(user: dict) -> None:
    """Increment the user's AI credit counter and raise HTTP 402 if the
    tier's monthly / one-time limit has been reached.

    Bypass conditions: founder / demo / billing-exempt / is_unlimited, or
    the plan has no limit (Compleet / Starter → ai_credits_limit is None).
    Trial users bypass the plan credit system entirely — their usage is
    already gated by the per-assistant daily cap (`_check_and_bump_trial_ai_cap`).
    """
    if user.get("is_founder") or user.get("is_demo") or user.get("billing_exempt") or user.get("is_unlimited"):
        return
    if user.get("is_trial"):
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


async def _refund_ai_credit(user: dict) -> None:
    """Undo a `_consume_ai_credit` increment when the LLM call fails.

    CR-3 fix (2026-07-21): AI credits used to be charged up-front and
    never refunded if the provider returned an error, so a Kickstart user
    could burn their monthly quota during an outage without receiving a
    single reply. This helper is called from the error paths of ai_chat
    and ai_stream. Refund is skipped for users who never had a real
    counter incremented in the first place (founder / demo / unlimited /
    unlimited-plan or capped-at-zero users)."""
    if user.get("is_founder") or user.get("is_demo") or user.get("billing_exempt") or user.get("is_unlimited"):
        return
    ctx = _tier_context(user)
    if ctx.get("ai_credits_limit") is None:
        return
    # Never let the counter drop below zero (defensive — a concurrent
    # webhook reset could race with the refund).
    res = await db.users.update_one(
        {"id": user["id"], "ai_credits_used_this_period": {"$gt": 0}},
        {"$inc": {"ai_credits_used_this_period": -1}},
    )
    if res.modified_count:
        logger.info("Refunded 1 AI credit for user=%s (LLM failure)", user["id"])


# ------------------------------------------------------------------
# AI Assistant file uploads (PDF / DOCX / XLSX / PPTX / CSV)
# ------------------------------------------------------------------
AI_UPLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
AI_UPLOAD_ALLOWED_EXTS = {".pdf", ".docx", ".xlsx", ".pptx", ".csv"}


async def _load_ai_file_context(user_id: str, file_ids: Optional[List[str]]) -> str:
    """Fetch extracted text for the given uploads (owner-scoped) and format
    it as a single context block ready to prepend to the user message.
    Returns "" if no files or none matched.
    """
    if not file_ids:
        return ""
    # Cap the number of attachments per turn to avoid pathological prompts.
    ids = [str(f) for f in file_ids if f][:6]
    if not ids:
        return ""
    rows = await db.ai_uploads.find(
        {"file_id": {"$in": ids}, "user_id": user_id},
        {"_id": 0, "filename": 1, "text": 1, "truncated": 1},
    ).to_list(length=len(ids))
    if not rows:
        return ""
    blocks = []
    for r in rows:
        name = r.get("filename") or "attachment"
        text = r.get("text") or ""
        if not text:
            continue
        trunc_note = " (truncated)" if r.get("truncated") else ""
        blocks.append(f"===== FILE: {name}{trunc_note} =====\n{text}")
    if not blocks:
        return ""
    return (
        "The user attached the following file(s). Use them as authoritative "
        "context for this turn; refer to them by filename when relevant.\n\n"
        + "\n\n".join(blocks)
    )


@api_router.post("/ai/upload")
async def ai_upload(
    file: UploadFile = File(...),
    user=Depends(get_current_user_full),
):
    """Accept a single PDF/DOCX/XLSX/PPTX/CSV (≤10 MB), extract its text,
    and store it in `ai_uploads` for use as chat context. Records auto-expire
    after 24h via a TTL index — this is session-temporary storage, not a
    document library.
    """
    filename = (file.filename or "upload").strip()
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in AI_UPLOAD_ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Allowed: PDF, DOCX, XLSX, PPTX, CSV.",
        )

    # Read with an explicit ceiling — protects against memory exhaustion.
    data = await file.read(AI_UPLOAD_MAX_BYTES + 1)
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")
    if len(data) > AI_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")

    # Local import keeps server.py cold-start light.
    import file_extract  # noqa: WPS433

    try:
        text, truncated, mime = await asyncio.to_thread(
            file_extract.extract_text, filename, data
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted from this file. It may be a scan / image-only document.",
        )

    file_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    doc = {
        "file_id": file_id,
        "user_id": user["id"],
        "filename": filename,
        "mime": mime,
        "size": len(data),
        "text": text,
        "text_chars": len(text),
        "truncated": truncated,
        "created_at": now,  # datetime (not iso) so the TTL index expires it
    }
    await db.ai_uploads.insert_one(doc)

    return {
        "file_id": file_id,
        "filename": filename,
        "size": len(data),
        "mime": mime,
        "chars_extracted": len(text),
        "truncated": truncated,
        "preview": text[:400],
    }


@api_router.delete("/ai/upload/{file_id}")
async def ai_upload_delete(file_id: str, user=Depends(get_current_user_full)):
    res = await db.ai_uploads.delete_one({"file_id": file_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return {"ok": True, "file_id": file_id}



@api_router.post("/ai/chat")
async def ai_chat(payload: AssistChatIn, user=Depends(get_current_user_full)):
    await _check_and_bump_trial_ai_cap(user, payload.assistant)
    await _consume_ai_credit(user)
    session_id = payload.session_id or f"{user['id']}:{payload.assistant}:{uuid.uuid4()}"
    file_context = await _load_ai_file_context(user["id"], payload.file_ids)
    try:
        result = await ai_assistants.chat_complete(
            db,
            payload.assistant,
            session_id,
            user["id"],
            payload.message,
            subscription_plan=user.get("subscription_plan"),
            user_context=user,
            file_context=file_context,
        )
    except RuntimeError as e:
        # LLM outage / provider error — refund the credit we charged.
        await _refund_ai_credit(user)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        await _refund_ai_credit(user)
        raise
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

    await _check_and_bump_trial_ai_cap(user, payload.assistant)
    await _consume_ai_credit(user)
    session_id = payload.session_id or f"{user['id']}:{payload.assistant}:{uuid.uuid4()}"
    plan = user.get("subscription_plan")
    file_context = await _load_ai_file_context(user["id"], payload.file_ids)

    async def event_generator():
        # Track whether we actually delivered any tokens; if the entire
        # stream fails before the first delta, refund the AI credit
        # (CR-3 fix 2026-07-21). We refund on ANY error event too — a
        # partial stream that errors mid-way is not the value the user
        # paid for.
        errored = False
        delivered_any = False
        try:
            async for frame in ai_assistants.chat_stream(
                db, payload.assistant, session_id, user["id"], payload.message,
                subscription_plan=plan,
                user_context=user,
                file_context=file_context,
            ):
                ftype = frame.get("type", "delta")
                if ftype == "delta" and (frame.get("content") or ""):
                    delivered_any = True
                elif ftype == "error":
                    errored = True
                ev = frame.pop("type", "delta")
                yield f"event: {ev}\ndata: {_json.dumps(frame)}\n\n"
        except ValueError as e:
            errored = True
            yield f"event: error\ndata: {_json.dumps({'message': str(e)})}\n\n"
        except Exception:  # noqa: BLE001
            errored = True
            logger.exception("ai_stream failure")
            yield f"event: error\ndata: {_json.dumps({'message': 'AI service error.'})}\n\n"
        finally:
            if errored and not delivered_any:
                await _refund_ai_credit(user)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



# ------------------------------------------------------------------
# Social account connections (Meta = Facebook+Instagram, LinkedIn)
# ------------------------------------------------------------------
# Graceful-fallback stubs: if the app credentials env vars are set the
# endpoint returns a real OAuth authorize URL; otherwise a 501 with a
# `coming_soon: True` payload so the frontend can render a friendly
# "Connect coming soon" state without treating it as an error.
SOCIAL_PROVIDERS = {
    "facebook": {
        "env_id":  "META_APP_ID",
        "env_sec": "META_APP_SECRET",
        "authorize": "https://www.facebook.com/v20.0/dialog/oauth",
        "scopes": "pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,instagram_content_publish,business_management",
    },
    "instagram": {
        # Instagram Business uses the same Meta OAuth flow.
        "env_id":  "META_APP_ID",
        "env_sec": "META_APP_SECRET",
        "authorize": "https://www.facebook.com/v20.0/dialog/oauth",
        "scopes": "instagram_basic,instagram_content_publish,pages_show_list,business_management",
    },
    "linkedin": {
        "env_id":  "LINKEDIN_CLIENT_ID",
        "env_sec": "LINKEDIN_CLIENT_SECRET",
        "authorize": "https://www.linkedin.com/oauth/v2/authorization",
        "scopes": "openid profile email w_member_social",
    },
}


@api_router.get("/social/connections")
async def social_connections(user=Depends(get_current_user_full)):
    """List the user's connected social accounts. Empty list is a valid
    response and does not indicate an error."""
    rows = await db.social_connections.find(
        {"user_id": user["id"]},
        {"_id": 0, "provider": 1, "account_name": 1, "connected_at": 1, "expires_at": 1},
    ).to_list(length=50)
    return {"connections": rows}


@api_router.get("/social/oauth/start")
async def social_oauth_start(provider: str, user=Depends(get_current_user_full)):
    """Kick off the OAuth authorize redirect. If the platform's app
    credentials are not configured on the server, respond with
    501 + `coming_soon: True` so the client can show a friendly banner
    instead of an error toast."""
    cfg = SOCIAL_PROVIDERS.get(provider.lower())
    if not cfg:
        raise HTTPException(status_code=400, detail=f"Unknown social provider: {provider}")
    client_id = os.environ.get(cfg["env_id"])
    if not client_id:
        # Graceful fallback: the platform isn't configured yet.
        return JSONResponse(
            status_code=501,
            content={
                "coming_soon": True,
                "provider": provider,
                "message": (
                    "Social connect for this platform is coming soon — the OAuth app "
                    "is not yet configured. Check back shortly."
                ),
            },
        )
    # Build the authorize URL. Real callback endpoint is added when the
    # user configures the app; state carries the user id + provider for CSRF.
    import secrets, urllib.parse
    state = secrets.token_urlsafe(24)
    await db.social_oauth_states.insert_one({
        "state": state,
        "user_id": user["id"],
        "provider": provider,
        "created_at": datetime.now(timezone.utc),
    })
    redirect_uri = f"{os.environ.get('PUBLIC_APP_URL', 'https://zynthoro.ai')}/api/social/oauth/callback"
    params = {
        "client_id":     client_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         cfg["scopes"],
        "state":         state,
    }
    url = f"{cfg['authorize']}?{urllib.parse.urlencode(params)}"
    return {"authorize_url": url, "provider": provider}


@api_router.get("/social/oauth/callback")
async def social_oauth_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """OAuth callback landing route. Full token-exchange is intentionally
    stubbed — the platforms' app credentials aren't configured yet, so
    this route just closes the loop with a friendly redirect. When the
    apps are approved and creds are added, this handler is where the
    `requests.post(token_url, ...)` exchange goes."""
    frontend_url = f"{os.environ.get('PUBLIC_APP_URL', '')}/dashboard/marketing?social_status="
    if error:
        return RedirectResponse(url=f"{frontend_url}error&reason={error}")
    if not code or not state:
        return RedirectResponse(url=f"{frontend_url}error&reason=missing_params")
    st = await db.social_oauth_states.find_one_and_delete({"state": state})
    if not st:
        return RedirectResponse(url=f"{frontend_url}error&reason=invalid_state")
    # TODO(prod): exchange `code` for access_token + long-lived token,
    # fetch page/account metadata, then insert into social_connections.
    return RedirectResponse(url=f"{frontend_url}pending&provider={st['provider']}")


@api_router.post("/social/disconnect")
async def social_disconnect(payload: dict, user=Depends(get_current_user_full)):
    provider = (payload.get("provider") or "").lower()
    if not provider:
        raise HTTPException(status_code=400, detail="provider required")
    res = await db.social_connections.delete_one(
        {"user_id": user["id"], "provider": provider}
    )
    return {"ok": True, "deleted": res.deleted_count}



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
    promo_code: Optional[str] = None  # customer-typed Stripe promotion code


class TierPromoValidateIn(BaseModel):
    tier_key: Literal[
        "kickstart_1", "kickstart_2", "kickstart_3",
        "compleet", "ai_social_week", "ai_social_month",
    ]
    code: str


@api_router.post("/checkout/tier/validate-promo")
async def validate_tier_promo(
    payload: TierPromoValidateIn,
    user=Depends(get_current_user_full),
):
    """Validate a customer-typed promotion code and return a discount preview.

    Called live from the /subscribe/:tierKey page when the user clicks "Apply".
    Internal / QA-only codes (e.g. ZYNTHORO-QA) are refused on the server
    side for non-QA accounts.
    """
    try:
        preview = await tier_catalog.resolve_promotion_code(
            payload.code,
            tier_key=payload.tier_key,
            is_qa_test=bool(user.get("is_qa_test")),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Stripe reageert traag. Probeer het opnieuw.")
    except stripe_sdk.error.StripeError as e:
        logger.exception("validate-promo Stripe error")
        raise HTTPException(status_code=400, detail=f"Stripe fout: {getattr(e, 'user_message', None) or 'onbekend'}")
    # Never expose the promotion_code_id to the client — client cannot use
    # it to bypass server-side re-validation.
    return {
        "ok": True,
        "code": preview["code"],
        "percent_off": preview["percent_off"],
        "amount_off_eur": preview["amount_off_eur"],
        "discount_eur": preview["discount_eur"],
        "original_total_eur": preview["original_total_eur"],
        "discounted_total_eur": preview["discounted_total_eur"],
        "currency": preview["currency"],
    }


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
    # SECURITY (SEC-003) — the "Add promotion code" input on Stripe's own
    # checkout page is still gated to QA accounts (would let a user try any
    # code including ZYNTHORO-QA). Customers use our OWN promo field on
    # /subscribe/:tierKey → we validate server-side, then pre-apply via
    # `discounts=[{promotion_code}]`.
    allow_promo = bool(user.get("is_qa_test"))

    # Re-validate the customer-supplied code (never trust the client — a user
    # could bypass the "Apply" step and inject a code directly here).
    promotion_code_id: Optional[str] = None
    promotion_code_label: Optional[str] = None
    if payload.promo_code and payload.promo_code.strip():
        try:
            preview = await tier_catalog.resolve_promotion_code(
                payload.promo_code,
                tier_key=payload.tier_key,
                is_qa_test=bool(user.get("is_qa_test")),
            )
            promotion_code_id = preview["promotion_code_id"]
            promotion_code_label = preview["code"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except stripe_sdk.error.StripeError as e:
            logger.exception("Tier checkout: promo revalidation failed")
            raise HTTPException(
                status_code=400,
                detail=f"Promocode kon niet toegepast worden: {getattr(e, 'user_message', None) or 'onbekend'}",
            )

    try:
        session = await tier_catalog.create_tier_checkout_session(
            tier_key=payload.tier_key,
            origin_url=payload.origin_url,
            user_id=user["id"],
            user_email=user["email"],
            consent_at=consent_at,
            allow_promo=allow_promo,
            promotion_code_id=promotion_code_id,
            promotion_code_label=promotion_code_label,
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
                        amount_total_cents=session.get("amount_total"),
                    )
                    await db.payment_transactions.update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "payment_status": payment_status,
                            "status": "complete",
                            # `provisioned` is set inside _provision_tier_purchase
                            # via atomic CAS — don't overwrite here or we'd
                            # clobber `provisioning_blocked` for coupon-abuse
                            # blocks. See CR-4 / SEC-003 fix 2026-07-21.
                            "stripe_subscription_id": session.get("subscription"),
                            "stripe_customer_id": session.get("customer"),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                            "healed_by": "status_endpoint",
                        }},
                    )
                    txn["payment_status"] = payment_status
                    txn["status"] = "complete"
                    # Re-read the atomically-set flag so callers see the truth.
                    fresh_txn = await db.payment_transactions.find_one(
                        {"session_id": session_id}, {"provisioned": 1, "_id": 0}
                    ) or {}
                    txn["provisioned"] = bool(fresh_txn.get("provisioned"))
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
    amount_total_cents: Optional[int] = None,
) -> None:
    """Idempotent provisioning for tier_purchase Stripe sessions.
    Called from the webhook AND from the status endpoint as a self-heal
    fallback (e.g. when a webhook was missed or dropped).

    Guarantees (bugfixes 2026-07-21):
      • Atomic idempotency: uses conditional update on
        `payment_transactions.provisioned` so concurrent webhook + self-heal
        (or Stripe event replay) can never double-provision, double-email
        or reset `ai_credits_used_this_period`.
      • Top-ups (AI+Social Week/Month) NEVER overwrite subscription_plan
        or is_lifetime — they only grant/replace credit fields.
      • Amount-tamper guard: if the amount actually charged is <50% of the
        tier's list price AND the buyer is not an internal QA/founder
        account, refuse to provision (blocks promo abuse via ZYNTHORO-QA
        or any other unrestricted 100%-off coupon)."""
    tier_key = meta.get("tier_key") or ""
    plan_key = meta.get("plan_key") or ""
    tier_def = tier_catalog.get_tier(tier_key)
    # NOTE: TIER_CATALOG holds Stripe pricing metadata only; the credit
    # quota + period lives in TIER_FEATURES keyed by plan_key. Do NOT read
    # credit fields from tier_def — that was the source of a revenue leak
    # where every tier provisioned with ai_credits_limit=None (unlimited).
    features = tier_catalog.TIER_FEATURES.get(plan_key) or {}
    billing = (tier_def or {}).get("billing", "lifetime")
    top_up = tier_catalog.is_top_up(tier_key)

    prev_doc = await db.users.find_one(
        {"id": user_id},
        {
            "subscription_plan": 1, "email": 1, "is_lifetime": 1,
            "is_qa_test": 1, "is_founder": 1, "is_demo": 1, "billing_exempt": 1,
        },
    )
    prev_plan = (prev_doc or {}).get("subscription_plan") or "Presale"
    prev_is_lifetime = bool((prev_doc or {}).get("is_lifetime"))
    user_email_x = (prev_doc or {}).get("email")
    is_internal = any(
        (prev_doc or {}).get(k) for k in ("is_qa_test", "is_founder", "is_demo", "billing_exempt")
    )

    # ---- SEC-003 defense-in-depth: amount-tamper guard ------------------
    # If the amount actually captured by Stripe is materially below the
    # tier's list price and the buyer is not an internal account, refuse
    # to provision. Records the incident + emails ops so someone can
    # investigate + refund if needed.
    expected_cents = int(round(float((tier_def or {}).get("amount_eur") or 0) * 100))
    if (
        not is_internal
        and amount_total_cents is not None
        and expected_cents > 0
        and amount_total_cents < expected_cents // 2  # <50 % of list price
    ):
        logger.critical(
            "SECURITY: refusing to provision tier=%s user=%s session=%s — "
            "amount_paid=%s cents < 50%% of expected=%s cents (possible promo abuse)",
            tier_key, user_id, session_id, amount_total_cents, expected_cents,
        )
        await db.security_incidents.insert_one({
            "id": str(uuid.uuid4()),
            "type": "promo_abuse_blocked",
            "user_id": user_id,
            "user_email": user_email_x,
            "tier_key": tier_key,
            "plan_key": plan_key,
            "expected_cents": expected_cents,
            "amount_paid_cents": amount_total_cents,
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        asyncio.create_task(email_service.send_stripe_alert(
            kind="alert",
            event_type="promo_abuse_blocked",
            user_email=user_email_x,
            user_id=user_id,
            plan_key=plan_key,
            amount_eur=amount_total_cents / 100 if amount_total_cents is not None else None,
            stripe_session_id=session_id,
            stripe_subscription_id=stripe_subscription,
            extra={
                "Tier": tier_key,
                "Expected EUR": expected_cents / 100,
                "Reason": "Amount paid <50% of list — coupon likely misused. Entitlement NOT granted.",
            },
        ))
        # Record the block on the transaction so the self-heal / webhook
        # replay won't keep re-firing alert emails, WITHOUT setting
        # `provisioned=True` (which would leak entitlement if the block is
        # later lifted).
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "provisioning_blocked": True,
                "provisioning_blocked_reason": "amount_below_50pct_of_list",
                "provisioning_blocked_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        return

    # ---- CR-4 idempotency guard (2026-07-21) ----------------------------
    # Atomic check-and-set on `payment_transactions.provisioned`. If a
    # concurrent webhook / self-heal / event replay has already flipped
    # the flag, matched_count == 0 and we return WITHOUT touching the
    # user record or emitting duplicate side effects (email, activity
    # feed, ai_credits reset).
    guard = await db.payment_transactions.update_one(
        {
            "session_id": session_id,
            "provisioned": {"$ne": True},
            "provisioning_blocked": {"$ne": True},
        },
        {"$set": {
            "provisioned": True,
            "provisioned_at": datetime.now(timezone.utc).isoformat(),
            "provisioning_source": event_type,
        }},
    )
    if guard.matched_count == 0:
        # No unprovisioned+unblocked row matched. Two possibilities:
        #  (a) The txn row does not exist yet (rare edge case: webhook
        #      arrived before the checkout endpoint wrote the row; also
        #      the test-only direct-call path). Create it and continue.
        #  (b) A row exists but is already provisioned or blocked → skip.
        existing = await db.payment_transactions.find_one(
            {"session_id": session_id},
            {"provisioned": 1, "provisioning_blocked": 1, "_id": 0},
        )
        if existing is None:
            await db.payment_transactions.insert_one({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": user_id,
                "provisioned": True,
                "provisioned_at": datetime.now(timezone.utc).isoformat(),
                "provisioning_source": event_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            logger.info(
                "Provisioning skipped for session=%s — already provisioned or blocked (source=%s).",
                session_id, event_type,
            )
            return

    credits_limit = features.get("ai_credits_limit")
    credits_period = features.get("ai_credits_period", "month")
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    period_end = None
    if billing == "one_time_week":
        period_end = (now_dt + timedelta(days=7)).isoformat()
    elif billing == "one_time_month":
        period_end = (now_dt + timedelta(days=30)).isoformat()

    if top_up:
        # Bugfix 2026-07-21 — a top-up must not overwrite a paying
        # customer's lifetime or subscription plan. `prev_is_paying`
        # detects any pre-existing paid entitlement (Kickstart lifetime,
        # Compleet subscription, Starter/etc.). If the user has no paying
        # plan (Presale or brand-new), we fall through to the full
        # overwrite path so the top-up becomes their effective plan.
        prev_is_paying = prev_is_lifetime or (prev_plan not in (None, "", "Presale"))
    else:
        prev_is_paying = False

    if top_up and prev_is_paying:
        # ---- Top-up over paid plan: additive credits only --------------
        update_fields = {
            "ai_credits_limit": credits_limit,
            "ai_credits_period": credits_period,
            "ai_credits_used_this_period": 0,
            "ai_credits_period_started_at": now_iso,
            "ai_credits_period_ends_at": period_end,
            "consent_waiver": True,
            "consent_waiver_at": meta.get("consent_at") or now_iso,
            "active_top_up": {
                "tier_key": tier_key,
                "plan_key": plan_key,
                "started_at": now_iso,
                "ends_at": period_end,
            },
        }
    else:
        # ---- Regular plan purchase OR top-up-as-first-plan --------------
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

    if top_up and prev_is_paying:
        feed_verb = "⚡ Activated"
        feed_sub = f"On top of your {prev_plan}"
    else:
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
    alert_kind_tier = (
        "topup" if (top_up and prev_is_paying)
        else ("subscribe" if prev_plan in (None, "Presale", "") else "upgrade")
    )
    asyncio.create_task(email_service.send_stripe_alert(
        kind=alert_kind_tier,
        event_type=event_type,
        user_email=user_email_x,
        user_id=user_id,
        plan_key=plan_key,
        amount_eur=float(meta.get("amount_eur") or 0) or None,
        stripe_session_id=session_id,
        stripe_subscription_id=stripe_subscription,
        extra={"Tier": tier_key, "Billing": billing, "Top-up": top_up},
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
                    amount_total_cents=obj.get("amount_total"),
                )

            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "payment_status": obj.get("payment_status") or "paid",
                    "status": "complete",
                    # `provisioned` is now atomically set inside
                    # _provision_tier_purchase (CR-4). Do not overwrite it
                    # here — a promo-abuse block sets `provisioning_blocked`
                    # without provisioning, and overwriting `provisioned: True`
                    # would leak entitlement.
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
    # SEC-001 fix (2026-07-21): FOUNDER_PASSWORD must come from env, no
    # source-code default. If unset, refuse to seed (log CRITICAL). The
    # existing founder record in the DB is not touched.
    email = os.environ.get("FOUNDER_EMAIL", "regie@myrootzz.com").lower().strip()
    password = os.environ.get("FOUNDER_PASSWORD")
    if not password or len(password) < 12:
        logger.critical(
            "SECURITY: FOUNDER_PASSWORD env var is missing or shorter than 12 chars — "
            "refusing to seed founder account. Set a strong password in backend/.env "
            "(existing founder record is preserved if present)."
        )
        return
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
        # Keep founder flags consistent with .env config. Do NOT overwrite
        # the password_hash — password rotation goes through a dedicated
        # reset flow, not a boot-time overwrite.
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


async def _seed_finance_and_sales_demo(workspace_owner: str, now_iso: str) -> None:
    """Session C1 (2026-02-15) — seed realistic invoices + leads for the
    XPRIZE jury demo workspace so the Finance & Sales modules show
    populated data on first click. Idempotent: only inserts if empty.
    """
    from datetime import date, timedelta

    today = date.today()

    # ---- Finance settings (branding on PDFs) --------------------------
    if not await db.finance_settings.find_one({"workspace_owner": workspace_owner}):
        await db.finance_settings.insert_one({
            "workspace_owner": workspace_owner,
            "company_name": "Zynthoro Demo Workspace",
            "company_address": "Prinsengracht 263\n1016 GV Amsterdam\nNetherlands",
            "company_email": "billing@zynthoro-demo.ai",
            "company_vat": "NL 8590.12.345.B01",
            "logo_url": "",
            "default_payment_terms": "Payment due within 14 days of the invoice date. Late payments accrue 1.5% interest per month. Please reference the invoice number on your bank transfer.",
            "default_bank_details": "IBAN: NL91 ABNA 0417 1643 00\nBIC: ABNANL2A\nAccount name: Casa Haya International BV",
            "invoice_prefix": "ZY-",
            "next_invoice_seq": 1,
            "currency": "EUR",
            "created_at": now_iso,
        })

    # ---- Invoices ------------------------------------------------------
    if await db.finance_invoices.count_documents({"workspace_owner": workspace_owner}) == 0:
        def _mk_invoice(number, client, email, items, issued, due, status):
            subtotal = round(sum(it["quantity"] * it["unit_price"] for it in items), 2)
            tax = round(sum(it["quantity"] * it["unit_price"] * (it["tax_rate"] / 100.0) for it in items), 2)
            total = round(subtotal + tax, 2)
            return {
                "id": str(uuid.uuid4()),
                "workspace_owner": workspace_owner,
                "number": number,
                "client_name": client,
                "client_email": email,
                "client_address": "",
                "issue_date": issued,
                "due_date": due,
                "currency": "EUR",
                "items": items,
                "subtotal": subtotal, "tax_total": tax, "total": total,
                "status": status,
                "payment_terms": "Payment due within 14 days.",
                "bank_details": "IBAN: NL91 ABNA 0417 1643 00\nBIC: ABNANL2A",
                "notes": "",
                "sent_at": now_iso if status in ("sent", "paid", "overdue") else None,
                "paid_at": now_iso if status == "paid" else None,
                "created_at": now_iso, "updated_at": now_iso,
                "is_demo": True,
            }

        demo_invoices = [
            _mk_invoice(
                "ZY-2026-0001", "Aurora Studios B.V.", "finance@aurorastudios.demo",
                [
                    {"description": "Zynthoro Enterprise · Q1 subscription", "quantity": 3, "unit_price": 990, "tax_rate": 21},
                    {"description": "Onboarding & training workshop (2 days)", "quantity": 1, "unit_price": 2500, "tax_rate": 21},
                ],
                (today - timedelta(days=45)).isoformat(),
                (today - timedelta(days=15)).isoformat(),
                "paid",
            ),
            _mk_invoice(
                "ZY-2026-0002", "Helix Robotics GmbH", "accounts@helix-robotics.demo",
                [
                    {"description": "AI workflow automation setup", "quantity": 1, "unit_price": 5500, "tax_rate": 21},
                    {"description": "Custom integration hours", "quantity": 20, "unit_price": 145, "tax_rate": 21},
                ],
                (today - timedelta(days=30)).isoformat(),
                (today - timedelta(days=1)).isoformat(),
                "paid",
            ),
            _mk_invoice(
                "ZY-2026-0003", "Lumen Therapeutics PLC", "ap@lumen-therapeutics.demo",
                [
                    {"description": "Compliance & GDPR audit module — annual", "quantity": 1, "unit_price": 8990, "tax_rate": 21},
                    {"description": "SOC 2 evidence gathering support", "quantity": 12, "unit_price": 175, "tax_rate": 21},
                ],
                (today - timedelta(days=10)).isoformat(),
                (today + timedelta(days=20)).isoformat(),
                "sent",
            ),
            _mk_invoice(
                "ZY-2026-0004", "Sable & Co. Architects", "billing@sable-architects.demo",
                [
                    {"description": "Zynthoro Compleet · monthly (Feb 2026)", "quantity": 1, "unit_price": 79.99, "tax_rate": 21},
                    {"description": "AI+Social credit top-up (150 credits)", "quantity": 1, "unit_price": 59.99, "tax_rate": 21},
                ],
                (today - timedelta(days=5)).isoformat(),
                (today + timedelta(days=25)).isoformat(),
                "sent",
            ),
            _mk_invoice(
                "ZY-2026-0005", "Verdant Foods Co-op", "hello@verdant-foods.demo",
                [
                    {"description": "Marketing & Content Studio · 1-month pilot", "quantity": 1, "unit_price": 2490, "tax_rate": 21},
                ],
                today.isoformat(),
                (today + timedelta(days=30)).isoformat(),
                "draft",
            ),
            _mk_invoice(
                "ZY-2026-0006", "Northwind Capital Partners", "controller@northwind-capital.demo",
                [
                    {"description": "Zynthoro Enterprise Unlimited · Q4 2025 subscription", "quantity": 1, "unit_price": 24990, "tax_rate": 21},
                ],
                (today - timedelta(days=60)).isoformat(),
                (today - timedelta(days=30)).isoformat(),
                "overdue",
            ),
        ]
        await db.finance_invoices.insert_many(demo_invoices)

        # Payment history for the two paid invoices.
        paid_ids = [inv["id"] for inv in demo_invoices if inv["status"] == "paid"]
        payment_docs = []
        for iid in paid_ids:
            inv = next(x for x in demo_invoices if x["id"] == iid)
            payment_docs.append({
                "id": str(uuid.uuid4()),
                "workspace_owner": workspace_owner,
                "invoice_id": iid,
                "amount": inv["total"],
                "method": "bank_transfer",
                "date": inv["due_date"],
                "notes": "Received via SEPA",
                "created_at": now_iso,
                "is_demo": True,
            })
        if payment_docs:
            await db.finance_payments.insert_many(payment_docs)

        # Bump the invoice seq so the next real invoice starts at 0007.
        await db.finance_settings.update_one(
            {"workspace_owner": workspace_owner},
            {"$set": {"next_invoice_seq": 7}},
        )
        logger.info(
            "Seeded %d real finance_invoices (+ %d payments) for jury workspace",
            len(demo_invoices), len(payment_docs),
        )

    # ---- Sales leads across all 5 pipeline stages ---------------------
    if await db.sales_leads.count_documents({"workspace_owner": workspace_owner}) == 0:
        def _mk_lead(name, company, email, phone, source, stage, value, close_offset, notes):
            return {
                "id": str(uuid.uuid4()),
                "workspace_owner": workspace_owner,
                "name": name, "company": company,
                "email": email, "phone": phone,
                "source": source, "stage": stage,
                "value": float(value), "currency": "EUR",
                "expected_close": (today + timedelta(days=close_offset)).isoformat() if close_offset else None,
                "notes": notes,
                "stage_history": [
                    {"stage": "new", "at": now_iso, "by": "demo@zynthoro"},
                ] + (
                    [{"stage": stage, "at": now_iso, "by": "demo@zynthoro"}]
                    if stage != "new" else []
                ),
                "created_at": now_iso, "updated_at": now_iso,
                "is_demo": True,
            }

        demo_leads = [
            _mk_lead("Sophie Laurent", "Élégance Paris SAS",       "s.laurent@elegance-paris.demo", "+33 1 42 60 30 30", "Website form",     "new",       12500, 60,  "Boutique fashion chain — 8 stores across France. Interested in Compleet + AI+Social."),
            _mk_lead("Marco Bianchi",   "Bianchi Automotive S.p.A.","marco@bianchi-auto.demo",       "+39 02 5555 1234",  "LinkedIn outreach","new",       48000, 90,  "Mid-size car dealership group, needs full ERP replacement."),
            _mk_lead("Emma van der Berg","GreenGrocer B.V.",         "emma@greengrocer.demo",        "+31 20 555 0142",   "Referral",         "contacted", 8990,  30,  "Amsterdam organic grocery — 3 locations. Call scheduled next Tuesday 10:00."),
            _mk_lead("James O'Connor",  "Dublin Digital Studio",     "james@dublindigital.demo",     "+353 1 555 0198",   "Cold email",       "contacted", 15600, 45,  "Creative agency, 12 people. Booked a demo for Thursday."),
            _mk_lead("Isabella Rossi",  "Rossi Interiors Milano",    "isabella@rossi-interiors.demo","+39 02 5555 6789",  "Trade show",       "proposal",  22400, 21,  "Sent Enterprise Advanced proposal on Feb 8. Waiting on final sign-off from CFO."),
            _mk_lead("David Nakamura",  "Kyoto Sake Exports KK",     "d.nakamura@kyotosake.demo",    "+81 75 555 4321",   "Referral · partner","proposal", 34500, 30,  "Multi-country shipping compliance requirement. Proposal includes bespoke module."),
            _mk_lead("Fatima Al-Rashid", "Desert Bloom Cosmetics",   "fatima@desertbloom.demo",      "+971 4 555 8765",   "Website form",     "won",       18990, -10, "Signed! Kickoff scheduled next Monday. Enterprise Advanced + Marketing add-on."),
            _mk_lead("Klaus Weber",     "Weber Präzision GmbH",       "k.weber@weber-praezision.demo","+49 89 5555 9876", "Cold call",        "won",       27500, -5,  "Signed 3-year deal. Onboarding starts next week with priority support."),
            _mk_lead("Priya Menon",     "Bengaluru Textiles Pvt Ltd", "priya@bengaluru-textiles.demo","+91 80 5555 3210",  "LinkedIn Ads",     "lost",      9500,  None,"Went with a cheaper local competitor. Follow up in Q3."),
        ]
        await db.sales_leads.insert_many(demo_leads)
        logger.info(
            "Seeded %d real sales_leads across all 5 stages for jury workspace",
            len(demo_leads),
        )

    # ---- Session C2 demo seed: projects, tasks, milestones, sprints, time -
    await _seed_projects_planning_time_demo(workspace_owner, now_iso)


async def _seed_projects_planning_time_demo(workspace_owner: str, now_iso: str) -> None:
    """Session C2 (2026-02-15) — seed realistic projects, tasks, milestones,
    sprints, and time entries into the XPRIZE jury demo workspace. Idempotent.
    """
    from datetime import date, timedelta

    today = date.today()

    # ---- Projects (with realistic mix of statuses) --------------------
    if await db.projects.count_documents({"workspace_owner": workspace_owner}) == 0:
        proj_specs = [
            ("Q1 Product Roadmap",       "Product",     "on_track",  "Amelia Chen",   72,  today - timedelta(days=45), today + timedelta(days=45), "#1A4FFF",
             "Ship the Q1 roadmap for Zynthoro modules — Finance, Sales, Projects, Planning, Time Tracking."),
            ("Spring Marketing Launch",  "Marketing",   "on_track",  "Priya Shah",    48,  today - timedelta(days=20), today + timedelta(days=60), "#D97706",
             "March/April marketing campaign — website refresh, LinkedIn ads, launch event."),
            ("SOC 2 Type II Audit",      "Compliance",  "at_risk",   "Daniel Krüger", 31,  today - timedelta(days=90), today + timedelta(days=90), "#dc2626",
             "Achieve SOC 2 Type II certification — evidence collection, policy review, third-party audit."),
            ("EU Sales Pipeline 2026",   "Sales",       "on_track",  "Luca Rossi",    64,  today - timedelta(days=60), today + timedelta(days=300), "#16a34a",
             "Build a €1M+ EU pipeline by year end. Focus on FR/DE/NL manufacturing SMEs."),
            ("AI Caption Engine v2",     "Operations",  "completed", "Amelia Chen",   100, today - timedelta(days=120), today - timedelta(days=10), "#8b5cf6",
             "Rebuild the caption engine on Claude Sonnet 4.5 with brand-voice presets."),
        ]
        proj_docs = []
        for name, domain, status, owner, progress, sd, ed, color, desc in proj_specs:
            proj_docs.append({
                "id": str(uuid.uuid4()),
                "workspace_owner": workspace_owner,
                "name": name, "description": desc,
                "status": status, "domain": domain, "owner": owner,
                "start_date": sd.isoformat(), "end_date": ed.isoformat(),
                "progress": progress, "color": color,
                "created_at": now_iso, "updated_at": now_iso,
                "is_demo": True,
            })
        await db.projects.insert_many(proj_docs)

        # ---- Tasks distributed across projects ------------------------
        task_specs = [
            # (project_index, title, assignee, status, priority, due_offset)
            (0, "Finalise invoice PDF template",           "Amelia Chen",  "done",        "high",   -20),
            (0, "Build sales kanban drag-drop",            "Amelia Chen",  "done",        "high",   -15),
            (0, "Ship projects + planning modules",        "Amelia Chen",  "in_progress", "high",   +5),
            (0, "Ship time tracking module",               "Luca Rossi",   "in_progress", "high",   +7),
            (0, "Write jury-day rehearsal script",         "Priya Shah",   "todo",        "medium", +10),
            (1, "Homepage hero refresh",                   "Priya Shah",   "done",        "medium", -5),
            (1, "LinkedIn ad creative batch A",            "Priya Shah",   "in_progress", "medium", +3),
            (1, "Book launch venue in Amsterdam",          "Nina Adebayo", "todo",        "high",   +14),
            (2, "Encrypt customer data at rest",           "Daniel Krüger","in_progress", "high",   +21),
            (2, "Publish updated Privacy Policy",          "Daniel Krüger","done",        "medium", -8),
            (2, "Vendor risk questionnaire — Anthropic",   "Daniel Krüger","todo",        "medium", +30),
            (3, "Cold-email sequence for FR manufacturers","Luca Rossi",   "in_progress", "medium", +7),
            (3, "Discovery calls with 10 target accounts", "Luca Rossi",   "todo",        "high",   +14),
            (4, "Migrate captioning to Claude Sonnet 4.5", "Amelia Chen",  "done",        "high",   -30),
            (4, "Add EN/NL/DE brand-voice presets",         "Amelia Chen", "done",        "medium", -20),
        ]
        task_docs = []
        for pi, title, assignee, status, prio, due_off in task_specs:
            task_docs.append({
                "id": str(uuid.uuid4()),
                "workspace_owner": workspace_owner,
                "project_id": proj_docs[pi]["id"],
                "title": title, "description": "",
                "assignee": assignee, "status": status, "priority": prio,
                "due_date": (today + timedelta(days=due_off)).isoformat(),
                "sprint_id": None,
                "completed_at": now_iso if status == "done" else None,
                "created_at": now_iso, "updated_at": now_iso,
                "is_demo": True,
            })
        await db.project_tasks.insert_many(task_docs)

        # ---- Milestones per project -----------------------------------
        ms_specs = [
            (0, "XPRIZE jury demo day",           +30, False),
            (0, "Ship Session C2",                +7,  False),
            (1, "Launch event",                   +45, False),
            (2, "SOC 2 evidence deadline",        +60, False),
            (2, "Kick-off with auditor",          -60, True),
            (3, "€500K pipeline",                 +180, False),
            (4, "V2 shipped",                     -10, True),
        ]
        ms_docs = []
        for pi, title, due_off, completed in ms_specs:
            ms_docs.append({
                "id": str(uuid.uuid4()),
                "workspace_owner": workspace_owner,
                "project_id": proj_docs[pi]["id"],
                "title": title,
                "due_date": (today + timedelta(days=due_off)).isoformat(),
                "completed": completed,
                "completed_at": now_iso if completed else None,
                "created_at": now_iso, "updated_at": now_iso,
                "is_demo": True,
            })
        await db.project_milestones.insert_many(ms_docs)

        # ---- 1 active sprint pulling tasks from multiple projects -----
        sprint_id = str(uuid.uuid4())
        await db.sprints.insert_one({
            "id": sprint_id,
            "workspace_owner": workspace_owner,
            "name": "Sprint 12 · Jury week",
            "goal": "Finish Session C1+C2 modules and rehearse the XPRIZE demo end-to-end.",
            "start_date": (today - timedelta(days=3)).isoformat(),
            "end_date": (today + timedelta(days=11)).isoformat(),
            "status": "active",
            "capacity_hours": 80,
            "created_at": now_iso, "updated_at": now_iso,
            "is_demo": True,
        })
        # Pull the "in-progress" and "todo" roadmap + marketing tasks into it.
        sprint_task_ids = [t["id"] for t in task_docs if t["status"] in ("in_progress", "todo") and t["project_id"] in (proj_docs[0]["id"], proj_docs[1]["id"])][:6]
        if sprint_task_ids:
            await db.project_tasks.update_many(
                {"id": {"$in": sprint_task_ids}},
                {"$set": {"sprint_id": sprint_id, "updated_at": now_iso}},
            )

        # ---- Time entries this week for realism -----------------------
        # Use the workspace owner's email (jury user) as author.
        jury = await db.users.find_one({"id": workspace_owner}, {"email": 1})
        author_email = (jury or {}).get("email", "jury@zynthoro.ai")
        # Monday of this week
        monday = today - timedelta(days=today.weekday())
        time_specs = [
            # (day_offset_from_monday, project_index, task_index_in_that_project's_tasks, hours, notes, billable)
            (0, 0, 2, 3.5, "Finance module PR review",             True),
            (0, 3, 11, 2.0, "Cold email A/B test copy",             False),
            (1, 0, 3, 5.0, "Time Tracking backend build",           True),
            (1, 2, 8, 1.5, "SOC 2 evidence prep",                   False),
            (2, 0, 4, 2.0, "Jury rehearsal script draft",           True),
            (2, 1, 6, 3.0, "LinkedIn ad creative iteration",        True),
            (3, 3, 12, 2.5, "Discovery calls prep",                  True),
            (4, 4, 13, 4.0, "V2 wrap-up + retro",                   False),
        ]
        # Build a quick lookup by project idx -> [task ids in insertion order]
        tasks_by_project: dict = {}
        for t in task_docs:
            tasks_by_project.setdefault(t["project_id"], []).append(t["id"])
        entry_docs = []
        for day_off, pi, tidx, hrs, notes, billable in time_specs:
            pid = proj_docs[pi]["id"]
            tid = None
            plist = tasks_by_project.get(pid, [])
            # tidx is the global task_specs row → convert to that specific project's task
            # Simpler: pick the (tidx modulo len) task inside that project.
            if plist:
                tid = plist[tidx % len(plist)]
            entry_docs.append({
                "id": str(uuid.uuid4()),
                "workspace_owner": workspace_owner,
                "user_email": author_email,
                "project_id": pid,
                "task_id": tid,
                "date": (monday + timedelta(days=day_off)).isoformat(),
                "hours": hrs,
                "notes": notes,
                "billable": billable,
                "source": "manual",
                "created_at": now_iso, "updated_at": now_iso,
                "is_demo": True,
            })
        await db.time_entries.insert_many(entry_docs)

        logger.info(
            "Seeded %d projects, %d tasks, %d milestones, 1 sprint, %d time entries for jury workspace",
            len(proj_docs), len(task_docs), len(ms_docs), len(entry_docs),
        )


async def seed_jury_demo():
    """XPRIZE / investor demo account, pre-populated with realistic sample data.

    Always force-resets the user's auth state on each boot so judges land in
    the dashboard with one click — no email verification, no 2FA prompt, no
    onboarding wizard. The flag `is_demo=True` exempts the account from any
    real billing or destructive operations.

    SEC-002 fix (2026-07-21): password must come from env
    (`JURY_DEMO_PASSWORD`). If unset, the demo is not seeded — safer to
    have no jury account than an account whose password sits in the
    source tree. In non-prod environments where a stable demo login is
    critical, set the env var and boot again.
    """
    email = "jury@zynthoro.ai"
    password = os.environ.get("JURY_DEMO_PASSWORD")
    if not password or len(password) < 12:
        logger.warning(
            "JURY_DEMO_PASSWORD env var is missing or too short — skipping "
            "jury demo seed. Existing demo user (if any) is left untouched."
        )
        return
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

    # ----- Session C1 demo seed: real finance_invoices + sales_leads -----
    # These populate the actual production modules the jury will interact
    # with (unlike `demo_invoices` above which only feeds the legacy
    # `/api/demo/invoices` read-only route).
    await _seed_finance_and_sales_demo(workspace_owner, now_iso)

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
    # SEC-004: rate limit + audit trail for admin backdoors; auto-purge 7d
    await db.admin_call_attempts.create_index([("client_ip", 1), ("attempted_at", -1)])
    await db.admin_call_attempts.create_index("attempted_at", expireAfterSeconds=60 * 60 * 24 * 7)
    # ai_uploads is session-temporary — TTL index auto-purges after 24h
    await db.ai_uploads.create_index("file_id", unique=True)
    await db.ai_uploads.create_index("user_id")
    await db.ai_uploads.create_index("created_at", expireAfterSeconds=60 * 60 * 24)
    await seed_founder()
    await seed_jury_demo()
    # Validate Stripe tier catalog against live Stripe account.
    await _validate_stripe_catalog_on_startup()
    # Background scheduler: weekly digest to info@zynthoro.ai — fires
    # once per week on Monday at 07:00 UTC (configurable via
    # DIGEST_WEEKDAY / DIGEST_HOUR_UTC env vars). Skips the email if
    # there's no activity in the 7-day window.
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

# Session B modules (2026-07-21) — HR, Accounting, Communication, Compliance
import hr_module  # noqa: E402
import accounting_module  # noqa: E402
import accounting_csv_module  # noqa: E402
import communication_module  # noqa: E402
import compliance_module  # noqa: E402
import finance_module  # noqa: E402
import sales_module  # noqa: E402
import projects_module  # noqa: E402
import planning_module  # noqa: E402
import time_tracking_module  # noqa: E402
import blog_module  # noqa: E402
import meta_oauth_module  # noqa: E402
import ai_studio_module  # noqa: E402
app.include_router(hr_module.build_router(db, get_current_user_full))
app.include_router(accounting_module.build_router(db, get_current_user_full))
app.include_router(accounting_csv_module.build_router(db, get_current_user_full))
app.include_router(communication_module.build_router(db, get_current_user_full))
app.include_router(compliance_module.build_router(db, get_current_user_full))
app.include_router(finance_module.build_router(db, get_current_user_full))
app.include_router(sales_module.build_router(db, get_current_user_full))
app.include_router(projects_module.build_router(db, get_current_user_full))
app.include_router(planning_module.build_router(db, get_current_user_full))
app.include_router(time_tracking_module.build_router(db, get_current_user_full))
app.include_router(blog_module.build_router(db))
app.include_router(meta_oauth_module.build_router(db, get_current_user_full))
app.include_router(ai_studio_module.build_router(db, get_current_user_full))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    # NOTE: `*` is the required setting on Emergent's deployment platform
    # so the app works across preview + production hostnames (the deploy
    # URL is not known until publish time). Emergent's ingress echoes back
    # the request Origin when origin=* is used with credentials=True, so
    # this is safe on this platform. If you self-host, tighten this to a
    # comma-separated allow-list of your production origins.
    allow_origins=[
        o.strip() for o in (os.environ.get('CORS_ORIGINS') or '*').split(',') if o.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
