from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
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
import business_verification  # noqa: E402
import checkout as checkout_mod  # noqa: E402
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
    await check_lockout(db, ident)

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        await record_failed_login(db, ident)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.get("email_verified", False) and not user.get("is_founder"):
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

    # Demo accounts (XPRIZE jury, etc.) bypass the 2FA setup gate — judges
    # should land in the dashboard with a single click. The is_demo flag is
    # set by the seed function and can never be granted via the API.
    if user.get("is_demo"):
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


@api_router.get("/auth/me")
async def auth_me(user=Depends(get_current_user_full)):
    return user


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
    team_count = await db.team_members.count_documents({"workspace_owner": user["id"]}) + 1
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
        "recent_activity": [],
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


@api_router.post("/ai/chat")
async def ai_chat(payload: AssistChatIn, user=Depends(get_current_user_full)):
    session_id = payload.session_id or f"{user['id']}:{payload.assistant}:{uuid.uuid4()}"
    try:
        result = await ai_assistants.chat_complete(
            db,
            payload.assistant,
            session_id,
            user["id"],
            payload.message,
            subscription_plan=user.get("subscription_plan"),
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

    session_id = payload.session_id or f"{user['id']}:{payload.assistant}:{uuid.uuid4()}"
    plan = user.get("subscription_plan")

    async def event_generator():
        try:
            async for frame in ai_assistants.chat_stream(
                db, payload.assistant, session_id, user["id"], payload.message,
                subscription_plan=plan,
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
        }
        await db.feature_flags.insert_one(dict(row))
    return row


class FeatureFlagsIn(BaseModel):
    ai_assistants_enabled: Optional[bool] = None
    presale_open: Optional[bool] = None
    beta_modules_enabled: Optional[bool] = None
    stripe_enabled: Optional[bool] = None


@api_router.patch("/founder/feature-flags")
async def founder_flags_update(payload: FeatureFlagsIn, user=Depends(get_founder_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if updates:
        await db.feature_flags.update_one(
            {"singleton": True}, {"$set": updates}, upsert=True
        )
    return await db.feature_flags.find_one({"singleton": True}, {"_id": 0})


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
#  Business verification + Starter checkout
# ========================================================================
MAX_PDF_BYTES = 8 * 1024 * 1024  # 8 MB


@api_router.post("/business-verification/upload")
async def business_verification_upload(
    file: UploadFile = File(...),
    user=Depends(get_current_user_full),
):
    """Upload a business registration PDF, run AI extraction, store result."""
    if (file.content_type or "").lower() not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    data = await file.read()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 8 MB).")
    if len(data) < 100:
        raise HTTPException(status_code=400, detail="File looks empty.")

    session_id = f"verify:{user['id']}:{uuid.uuid4()}"
    result = await business_verification.verify_pdf(data, session_id)

    extraction = result.get("extraction") or {}
    record = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user["email"],
        "plan": "Starter",
        "filename": file.filename,
        "file_size": len(data),
        "company_name": extraction.get("company_name"),
        "registration_number": extraction.get("registration_number"),
        "country": extraction.get("country"),
        "document_type": extraction.get("document_type"),
        "registration_date": result.get("registration_date"),
        "age_days": result.get("age_days"),
        "confidence": extraction.get("confidence"),
        "status": result["status"],
        "message": result["message"],
        "ai_session_id": session_id,
        "ai_provider": "anthropic",
        "ai_model": ai_assistants.CLAUDE_MODEL,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.business_verifications.insert_one(record)

    # Mirror to ai_logs for the XPRIZE audit trail
    await db.ai_logs.insert_one({
        "user_id": user["id"],
        "session_id": session_id,
        "assistant": "business_verification",
        "provider": "anthropic",
        "model": ai_assistants.CLAUDE_MODEL,
        "subscription_plan": user.get("subscription_plan"),
        "request_chars": len(data),
        "reply_chars": len((result.get("extraction") or {}).get("company_name") or ""),
        "latency_ms": 0,
        "status": "ok" if record["status"] != "failed" else "fallback",
        "error": None,
        "timestamp": record["created_at"],
    })

    return {
        "verification_id": record["id"],
        "status": record["status"],
        "message": record["message"],
        "eligible": record["status"] == "eligible",
        "company_name": record["company_name"],
        "registration_number": record["registration_number"],
        "country": record["country"],
        "registration_date": record["registration_date"],
    }


class StarterCheckoutIn(BaseModel):
    package_id: Literal["starter_founder", "starter_standard"]
    origin_url: str
    verification_id: Optional[str] = None


@api_router.post("/checkout/starter/session")
async def checkout_starter_session(
    payload: StarterCheckoutIn,
    request: Request,
    user=Depends(get_current_user_full),
):
    # Hard server-side guard: founder package only allowed with an 'eligible' verification.
    if payload.package_id == "starter_founder":
        if not payload.verification_id:
            raise HTTPException(status_code=400, detail="Verification required for founder pricing.")
        v = await db.business_verifications.find_one(
            {"id": payload.verification_id, "user_id": user["id"]},
            {"_id": 0},
        )
        if not v or v.get("status") != "eligible":
            raise HTTPException(status_code=400, detail="Verification not eligible for founder pricing.")

    host_url = str(request.base_url)
    try:
        session = await checkout_mod.create_subscription_checkout(
            package_id=payload.package_id,
            host_url=host_url,
            origin_url=payload.origin_url,
            user_id=user["id"],
            user_email=user["email"],
            verification_id=payload.verification_id,
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
        "verification_id": payload.verification_id,
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
        pkg = txn["package_id"]
        meta = txn.get("metadata") or {}
        months = int(meta.get("founder_window_months") or 0)
        founder_window = checkout_mod.founder_pricing_window(months)
        user_update = {
            "subscription_plan": "Starter",
            "subscription_status": "active",
            "subscription_started_at": datetime.now(timezone.utc).isoformat(),
            "billing_first_amount_eur": txn["amount"],
            **founder_window,
        }
        if txn.get("verification_id"):
            user_update["business_verification_id"] = txn["verification_id"]
        await db.users.update_one({"id": user["id"]}, {"$set": user_update})

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
        if event_type == "checkout.session.completed" and obj.get("mode") == "subscription":
            session_id = obj.get("id")
            meta = obj.get("metadata") or {}
            user_id = meta.get("user_id") or obj.get("client_reference_id")
            kind = meta.get("kind", "")
            now_iso = datetime.now(timezone.utc).isoformat()

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
            asyncio.create_task(email_service.send_stripe_alert(
                kind="payment_failed",
                event_type=event_type,
                user_email=cust_email or None,
                amount_eur=(obj.get("amount_due") or 0) / 100 if obj.get("amount_due") else None,
                stripe_subscription_id=obj.get("subscription"),
                extra={"Attempt": obj.get("attempt_count"), "Next attempt": obj.get("next_payment_attempt")},
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


@api_router.get("/admin/business-verifications")
async def admin_business_verifications(
    user=Depends(get_founder_user),
    limit: int = 200,
    status: Optional[str] = None,
):
    q = {}
    if status:
        q["status"] = status
    rows = await db.business_verifications.find(q, {"_id": 0}).sort("created_at", -1).limit(min(max(limit, 1), 1000)).to_list(length=None)
    return {
        "count": len(rows),
        "total": await db.business_verifications.count_documents(q),
        "verifications": rows,
    }


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
    await db.business_verifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.payment_transactions.create_index("session_id", unique=True)
    await seed_founder()
    await seed_jury_demo()


@app.on_event("shutdown")
async def shutdown():
    client.close()


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
