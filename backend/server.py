from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
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


class TeamInviteIn(BaseModel):
    email: EmailStr
    role: str = Field(default="Employee")


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
    await db.presale_signups.insert_one(doc)
    return signup


@api_router.get("/presale/count")
async def get_presale_count():
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

    # No email service — log the verification link (Phase 2 user choice)
    logger.info("[email-mock from=hello@zynthoro.ai to=%s] Verification link: /verify-email?token=%s", email, verification_token)

    return {
        "message": "We've sent you a verification link. Please check your inbox.",
        "user_id": user_id,
        # Phase 2 only: return token so the UI can show a 'mock' link banner.
        "dev_verification_token": verification_token,
    }


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
    # No email service: log to console + return dev_code for the UI.
    logger.info("[email-mock from=support@zynthoro.ai to=%s] 2FA email code: %s", user["email"], code)
    return {"message": "Code sent. Check your inbox.", "dev_code": code}


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
        logger.info("[email-mock from=support@zynthoro.ai to=%s] Password reset link: /reset-password?token=%s", email, token)
        return {"message": "If the email exists, a reset link has been sent.", "dev_reset_token": token}
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
    # Always include the owner first
    owner = {
        "id": user["id"],
        "name": f'{user.get("first_name","")} {user.get("last_name","")}'.strip() or user["email"],
        "email": user["email"],
        "role": user.get("role", "Owner"),
        "status": "active",
        "twofa": user.get("twofa_enabled", False),
        "last_login": user.get("created_at"),
        "is_owner": True,
    }
    return {"members": [owner] + rows}


@api_router.post("/team/invite", status_code=201)
async def team_invite(payload: TeamInviteIn, user=Depends(get_current_user_full)):
    email = payload.email.lower().strip()
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
        "status": "invited",
        "twofa": False,
        "invite_token": invite_token,
        "last_login": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.team_members.insert_one(doc)
    logger.info("[email-mock from=hello@zynthoro.ai to=%s by=%s] Team invite token=%s", email, user["email"], invite_token)
    return {"id": doc["id"], "email": email, "role": payload.role, "dev_invite_token": invite_token}


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


@api_router.get("/ai/history")
async def ai_history(session_id: str, user=Depends(get_current_user_full)):
    rows = await db.ai_messages.find(
        {"session_id": session_id, "user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    return {"messages": rows}


# ========================================================================
#  Founder / Builder Mode (founder only)
# ========================================================================
@api_router.get("/founder/presale-signups")
async def founder_presale(user=Depends(get_founder_user)):
    rows = await db.presale_signups.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"signups": rows, "count": len(rows)}


@api_router.get("/founder/stats")
async def founder_stats(user=Depends(get_founder_user)):
    return {
        "presale_count": await db.presale_signups.count_documents({}),
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
    return {"enabled": False, "message": "Stripe checkout opens at launch on 30 June 2026."}


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
    await seed_founder()


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
