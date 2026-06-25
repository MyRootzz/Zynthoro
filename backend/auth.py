"""Authentication helpers: password hashing, JWT, current user dependency, brute-force protection."""
import os
import secrets
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import HTTPException, Request, Depends

JWT_ALGORITHM = "HS256"
ACCESS_TTL_MIN = 60 * 24  # 24h access for SPA simplicity
REFRESH_TTL_DAYS = 30
LOCKOUT_ATTEMPTS = 5
LOCKOUT_WINDOW_MIN = 15


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _secret() -> str:
    s = os.environ.get("JWT_SECRET")
    if not s:
        raise RuntimeError("JWT_SECRET not set")
    return s


def create_access_token(user_id: str, email: str, twofa_passed: bool) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "twofa": twofa_passed,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TTL_MIN),
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_pretwofa_token(user_id: str, email: str) -> str:
    """Short-lived token issued after password check but before 2FA verification."""
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        "type": "pre_2fa",
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return request.cookies.get("access_token")


async def get_current_user_full(request: Request):
    from server import db  # local import to avoid cycle
    token = _bearer(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    if not payload.get("twofa"):
        raise HTTPException(status_code=401, detail="2FA required")
    user = await db.users.find_one(
        {"id": payload["sub"]},
        {"_id": 0, "password_hash": 0, "totp_secret": 0, "company_logo_data": 0},
    )
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user["has_company_logo"] = bool(user.pop("company_logo_size", None)) or False
    # Re-check by looking up flag without pulling the data
    if not user.get("has_company_logo"):
        exists = await db.users.find_one({"id": payload["sub"], "company_logo_mime": {"$exists": True}}, {"_id": 1})
        user["has_company_logo"] = bool(exists)
    return user


async def get_optional_user(request: Request):
    try:
        return await get_current_user_full(request)
    except HTTPException:
        return None


async def get_founder_user(user=Depends(get_current_user_full)):
    if not user.get("is_founder"):
        raise HTTPException(status_code=403, detail="Founder only")
    return user


# ===== Brute-force =====
async def check_lockout(db, identifier: str):
    rec = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if not rec:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOCKOUT_WINDOW_MIN)
    last = rec.get("last_at")
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    if rec.get("count", 0) >= LOCKOUT_ATTEMPTS and last and last >= cutoff:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")


async def record_failed_login(db, identifier: str):
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$inc": {"count": 1}, "$set": {"last_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


async def clear_failed_logins(db, identifier: str):
    await db.login_attempts.delete_one({"identifier": identifier})


def gen_token_url_safe(n: int = 32) -> str:
    return secrets.token_urlsafe(n)


def gen_numeric_code(digits: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(digits))
