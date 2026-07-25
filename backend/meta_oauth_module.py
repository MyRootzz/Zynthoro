"""Meta (Facebook + Instagram) OAuth — post-only, multi-tenant.

Flow:
  1. GET  /api/oauth/meta/start        — returns the authorize URL (front-
     end redirects the user's browser to it).
  2. GET  /api/oauth/meta/callback     — Meta redirects the user's browser
     here with `code`. We exchange it for a long-lived user token, list
     Pages, harvest each Page's access token + IG business account, and
     store them encrypted per workspace.
  3. GET  /api/oauth/meta/status       — returns whether the current user
     is connected and the list of Pages / IG accounts they own.
  4. POST /api/oauth/meta/disconnect   — nukes their stored tokens.
  5. POST /api/oauth/meta/publish      — post a message (+ optional image)
     to a chosen Page and/or its linked IG Business account.

MOCK MODE — activated when META_APP_ID / META_APP_SECRET are missing.
In that mode:
  - /start returns a preview-only "mock connect" URL that immediately
    hits /callback with a stub code.
  - /callback fabricates a demo Page + IG account and stores them so
    the UI can be exercised end-to-end without real Meta credentials.
  - /publish returns a synthetic success (no external API call).
The env `META_MOCK_MODE=1` can also force mock mode explicitly.

Docs consulted: Facebook Graph v25.0. Two-step IG publish flow used
for Instagram (media container → media_publish).
"""
from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

GRAPH_VERSION = "v25.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
FB_AUTH_URL = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"

SCOPES = [
    "pages_show_list",
    "pages_manage_posts",
    "pages_read_engagement",
    "instagram_basic",
    "instagram_content_publish",
    "business_management",
]


# ---- Env / mode ------------------------------------------------------------
def _mock_mode() -> bool:
    if os.environ.get("META_MOCK_MODE") == "1":
        return True
    return not (os.environ.get("META_APP_ID") and os.environ.get("META_APP_SECRET"))


def _cipher() -> Optional[Fernet]:
    key = os.environ.get("META_ENCRYPTION_KEY")
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        logger.error("META_ENCRYPTION_KEY invalid: %s", e)
        return None


def _encrypt(token: str) -> str:
    c = _cipher()
    if not c:
        # Store plaintext under a marker; in mock mode this is fine.
        return "PLAIN::" + token
    return c.encrypt(token.encode()).decode()


def _decrypt(encrypted: str) -> str:
    if encrypted.startswith("PLAIN::"):
        return encrypted[len("PLAIN::"):]
    c = _cipher()
    if not c:
        raise RuntimeError("META_ENCRYPTION_KEY not configured")
    try:
        return c.decrypt(encrypted.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError("Meta token decrypt failed — key rotated?") from e


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


# ---- Pydantic --------------------------------------------------------------
class PublishIn(BaseModel):
    page_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=5000)
    image_url: Optional[str] = None
    target_fb: bool = True
    target_ig: bool = False


class ScheduleIn(BaseModel):
    page_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=5000)
    image_url: Optional[str] = None
    target_fb: bool = True
    target_ig: bool = False
    # ISO-8601 datetime in the future (UTC or with timezone).
    scheduled_at: str = Field(min_length=10, max_length=64)


# ---- Router ----------------------------------------------------------------
def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/oauth/meta", tags=["meta-oauth"])

    async def _load_connections(wo: str) -> List[Dict[str, Any]]:
        rows = await db.meta_connections.find(
            {"workspace_owner": wo}, {"_id": 0, "encrypted_token": 0}
        ).to_list(50)
        return rows

    # -- START ---------------------------------------------------------------
    @router.get("/start")
    async def start(user=Depends(get_user)):
        state = secrets.token_urlsafe(24)
        await db.meta_oauth_states.insert_one({
            "state": state,
            "workspace_owner": _wo(user),
            "created_at": _now(),
        })

        if _mock_mode():
            # Mock: immediately usable "connect" URL that hits our callback.
            redirect = os.environ.get("META_REDIRECT_URI") or "https://zynthoro.ai/dashboard/marketing/meta-callback"
            return {
                "mode": "mock",
                "authorize_url": f"{redirect}?code=mock_code&state={state}",
                "note": "Meta App credentials are not configured — running in demo mode. Set META_APP_ID/META_APP_SECRET in Secrets to enable the real OAuth flow.",
            }

        params = {
            "client_id": os.environ["META_APP_ID"],
            "redirect_uri": os.environ["META_REDIRECT_URI"],
            "state": state,
            "response_type": "code",
            "scope": ",".join(SCOPES),
        }
        return {"mode": "live", "authorize_url": f"{FB_AUTH_URL}?{urlencode(params)}"}

    # -- CALLBACK ------------------------------------------------------------
    @router.get("/callback")
    async def callback(code: str, state: str, user=Depends(get_user)):
        # Validate state against the stored one for this workspace.
        state_doc = await db.meta_oauth_states.find_one_and_delete(
            {"state": state, "workspace_owner": _wo(user)}
        )
        if not state_doc:
            raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

        if _mock_mode():
            return await _mock_finish_connect(db, user)

        app_id = os.environ["META_APP_ID"]
        app_secret = os.environ["META_APP_SECRET"]
        redirect_uri = os.environ["META_REDIRECT_URI"]

        async with httpx.AsyncClient(timeout=25.0) as client:
            # 1) code → short token
            r = await client.get(
                f"{GRAPH_URL}/oauth/access_token",
                params={
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            if r.status_code != 200:
                logger.error("Meta code exchange failed: %s", r.text)
                raise HTTPException(status_code=400, detail="Meta code exchange failed.")
            short_token = r.json().get("access_token")
            if not short_token:
                raise HTTPException(status_code=400, detail="No access_token from Meta.")

            # 2) short → long-lived user token
            r = await client.get(
                f"{GRAPH_URL}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "fb_exchange_token": short_token,
                },
            )
            long_token = r.json().get("access_token") if r.status_code == 200 else short_token

            # 3) list Pages + Page access tokens
            r = await client.get(f"{GRAPH_URL}/me/accounts", params={"access_token": long_token})
            pages = r.json().get("data", [])

            # 4) for each Page, fetch its IG business account (if any)
            wo = _wo(user)
            saved = []
            for pg in pages:
                page_id = pg["id"]
                page_token = pg["access_token"]
                ig = None
                try:
                    ig_r = await client.get(
                        f"{GRAPH_URL}/{page_id}",
                        params={"fields": "instagram_business_account{id,username,name}", "access_token": page_token},
                    )
                    ig = (ig_r.json().get("instagram_business_account") or {}) if ig_r.status_code == 200 else None
                except Exception:
                    ig = None

                doc = {
                    "id": str(uuid.uuid4()),
                    "workspace_owner": wo,
                    "page_id": page_id,
                    "page_name": pg.get("name"),
                    "encrypted_token": _encrypt(page_token),
                    "ig_account_id": (ig or {}).get("id"),
                    "ig_username": (ig or {}).get("username"),
                    "connected_at": _now(),
                    "requires_reauth": False,
                    "source": "live",
                }
                await db.meta_connections.update_one(
                    {"workspace_owner": wo, "page_id": page_id},
                    {"$set": doc},
                    upsert=True,
                )
                saved.append({"page_id": page_id, "page_name": doc["page_name"], "ig_account_id": doc["ig_account_id"]})

        return {"ok": True, "mode": "live", "connected_pages": len(saved), "pages": saved}

    # -- STATUS --------------------------------------------------------------
    @router.get("/status")
    async def status(user=Depends(get_user)):
        conns = await _load_connections(_wo(user))
        return {
            "mode": "mock" if _mock_mode() else "live",
            "connected": len(conns) > 0,
            "pages": conns,
        }

    # -- DISCONNECT ----------------------------------------------------------
    @router.post("/disconnect")
    async def disconnect(user=Depends(get_user)):
        r = await db.meta_connections.delete_many({"workspace_owner": _wo(user)})
        return {"ok": True, "removed": r.deleted_count}

    # -- PUBLISH -------------------------------------------------------------
    @router.post("/publish")
    async def publish(payload: PublishIn, user=Depends(get_user)):
        try:
            return await publish_now(db, _wo(user), payload.model_dump())
        except _MetaPublishError as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)

    # -- SCHEDULE ------------------------------------------------------------
    @router.post("/schedule")
    async def schedule_post(payload: ScheduleIn, user=Depends(get_user)):
        wo = _wo(user)
        conn = await db.meta_connections.find_one({"workspace_owner": wo, "page_id": payload.page_id})
        if not conn:
            raise HTTPException(status_code=404, detail="Page not connected.")

        try:
            scheduled_dt = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="scheduled_at must be an ISO-8601 datetime.")
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
        if scheduled_dt <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="scheduled_at must be in the future.")

        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "page_id": payload.page_id,
            "message": payload.message,
            "image_url": payload.image_url,
            "target_fb": payload.target_fb,
            "target_ig": payload.target_ig,
            "scheduled_at": scheduled_dt.isoformat(),
            "status": "pending",
            "attempts": 0,
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.scheduled_posts.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/scheduled")
    async def list_scheduled(user=Depends(get_user), status: Optional[str] = None):
        q = {"workspace_owner": _wo(user)}
        if status:
            q["status"] = status
        rows = await (
            db.scheduled_posts
            .find(q, {"_id": 0})
            .sort("scheduled_at", 1)
            .to_list(200)
        )
        return {"posts": rows, "count": len(rows)}

    @router.post("/scheduled/{sid}/cancel")
    async def cancel_scheduled(sid: str, user=Depends(get_user)):
        r = await db.scheduled_posts.update_one(
            {"id": sid, "workspace_owner": _wo(user), "status": "pending"},
            {"$set": {"status": "cancelled", "updated_at": _now()}},
        )
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Scheduled post not found or already processed.")
        return {"ok": True, "id": sid, "status": "cancelled"}

    return router


# ---- Exception + publish helper (reused by scheduler) ---------------------
class _MetaPublishError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def publish_now(db: AsyncIOMotorDatabase, wo: str, payload: dict) -> Dict[str, Any]:
    """Do a Meta publish right now on behalf of a workspace.

    Shared by:
      - the /publish endpoint (interactive publish)
      - the scheduler tick (deferred publish)

    Raises _MetaPublishError on business errors (missing connection,
    Meta API rejection, missing IG account, etc).
    """
    page_id = payload["page_id"]
    message = payload["message"]
    image_url = payload.get("image_url")
    target_fb = bool(payload.get("target_fb", True))
    target_ig = bool(payload.get("target_ig", False))

    conn = await db.meta_connections.find_one({"workspace_owner": wo, "page_id": page_id})
    if not conn:
        raise _MetaPublishError("Page not connected.", 404)

    if _mock_mode() or conn.get("source") == "mock":
        fb_id = f"mock_fb_{uuid.uuid4().hex[:10]}" if target_fb else None
        ig_id = f"mock_ig_{uuid.uuid4().hex[:10]}" if (target_ig and conn.get("ig_account_id")) else None
        await db.meta_publishes.insert_one({
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "page_id": page_id,
            "message": message,
            "image_url": image_url,
            "fb_post_id": fb_id,
            "ig_post_id": ig_id,
            "mode": "mock",
            "created_at": _now(),
        })
        return {"ok": True, "mode": "mock", "fb_post_id": fb_id, "ig_post_id": ig_id}

    page_token = _decrypt(conn["encrypted_token"])
    results = {"fb_post_id": None, "ig_post_id": None}

    async with httpx.AsyncClient(timeout=30.0) as client:
        if target_fb:
            if image_url:
                r = await client.post(
                    f"{GRAPH_URL}/{page_id}/photos",
                    data={"url": image_url, "caption": message, "access_token": page_token},
                )
            else:
                r = await client.post(
                    f"{GRAPH_URL}/{page_id}/feed",
                    data={"message": message, "access_token": page_token},
                )
            data = r.json()
            if "error" in data:
                await _mark_reauth_if_needed(db, wo, page_id, data["error"])
                raise _MetaPublishError(f"Facebook publish failed: {data['error'].get('message')}", 400)
            results["fb_post_id"] = data.get("id") or data.get("post_id")

        if target_ig:
            if not conn.get("ig_account_id"):
                raise _MetaPublishError("This Page has no linked Instagram Business account.", 400)
            if not image_url:
                raise _MetaPublishError("Instagram requires an image_url.", 400)
            ig_id = conn["ig_account_id"]
            cont = await client.post(
                f"{GRAPH_URL}/{ig_id}/media",
                data={"image_url": image_url, "caption": message, "access_token": page_token},
            )
            cont_data = cont.json()
            if "error" in cont_data:
                raise _MetaPublishError(f"Instagram container error: {cont_data['error'].get('message')}", 400)
            pub = await client.post(
                f"{GRAPH_URL}/{ig_id}/media_publish",
                data={"creation_id": cont_data["id"], "access_token": page_token},
            )
            pub_data = pub.json()
            if "error" in pub_data:
                raise _MetaPublishError(f"Instagram publish error: {pub_data['error'].get('message')}", 400)
            results["ig_post_id"] = pub_data.get("id")

    await db.meta_publishes.insert_one({
        "id": str(uuid.uuid4()),
        "workspace_owner": wo,
        "page_id": page_id,
        "message": message,
        "image_url": image_url,
        "fb_post_id": results["fb_post_id"],
        "ig_post_id": results["ig_post_id"],
        "mode": "live",
        "created_at": _now(),
    })
    return {"ok": True, "mode": "live", **results}


# ---- Scheduler tick --------------------------------------------------------
async def process_due_scheduled_posts(db: AsyncIOMotorDatabase) -> Dict[str, int]:
    """Find pending scheduled posts whose scheduled_at is now (or in the
    past) and publish them. Idempotent via a status transition guard —
    two ticks firing at once will not double-publish.

    Returns a summary of what happened."""
    now_iso = _now()
    processed = 0
    published = 0
    failed = 0

    # Grab up to 50 due posts per tick.
    due_cursor = db.scheduled_posts.find(
        {"status": "pending", "scheduled_at": {"$lte": now_iso}},
        {"_id": 0},
    ).limit(50)

    async for post in due_cursor:
        # Atomic claim: transition pending → publishing. If another worker
        # already claimed it, `matched_count` will be 0 and we skip.
        claim = await db.scheduled_posts.update_one(
            {"id": post["id"], "status": "pending"},
            {"$set": {"status": "publishing", "updated_at": _now()},
             "$inc": {"attempts": 1}},
        )
        if claim.matched_count == 0:
            continue
        processed += 1

        try:
            result = await publish_now(db, post["workspace_owner"], post)
            await db.scheduled_posts.update_one(
                {"id": post["id"]},
                {"$set": {
                    "status": "published",
                    "result": result,
                    "published_at": _now(),
                    "updated_at": _now(),
                }},
            )
            published += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("Scheduled post %s failed: %s", post["id"], e)
            await db.scheduled_posts.update_one(
                {"id": post["id"]},
                {"$set": {
                    "status": "failed",
                    "error": str(e)[:400],
                    "updated_at": _now(),
                }},
            )
            failed += 1

    if processed:
        logger.info("Scheduler tick %s: processed=%d published=%d failed=%d",
                    now_iso, processed, published, failed)
    return {"processed": processed, "published": published, "failed": failed}


def start_scheduler(db: AsyncIOMotorDatabase, interval_seconds: int = 60) -> Any:
    """Start an APScheduler AsyncIOScheduler that ticks
    `process_due_scheduled_posts` every N seconds.

    Idempotent: safe to call once at app startup.
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:  # pragma: no cover
        logger.error("apscheduler not installed — scheduled posts will not fire.")
        return None

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        process_due_scheduled_posts,
        "interval",
        seconds=interval_seconds,
        args=[db],
        id="meta_scheduler_tick",
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Meta scheduler started (tick every %ds).", interval_seconds)
    return scheduler


async def _mock_finish_connect(db: AsyncIOMotorDatabase, user: dict) -> Dict[str, Any]:
    wo = _wo(user)
    page_id = f"mock_page_{uuid.uuid4().hex[:8]}"
    doc = {
        "id": str(uuid.uuid4()),
        "workspace_owner": wo,
        "page_id": page_id,
        "page_name": f"{user.get('company') or 'Demo'} — Facebook Page",
        "encrypted_token": _encrypt("mock_page_token"),
        "ig_account_id": f"mock_ig_{uuid.uuid4().hex[:8]}",
        "ig_username": (user.get("company") or "demo").lower().replace(" ", "") + "_ig",
        "connected_at": _now(),
        "requires_reauth": False,
        "source": "mock",
    }
    await db.meta_connections.update_one(
        {"workspace_owner": wo, "page_id": page_id},
        {"$set": doc},
        upsert=True,
    )
    return {
        "ok": True,
        "mode": "mock",
        "connected_pages": 1,
        "pages": [{"page_id": page_id, "page_name": doc["page_name"], "ig_account_id": doc["ig_account_id"]}],
    }


async def _mark_reauth_if_needed(db: AsyncIOMotorDatabase, wo: str, page_id: str, error: dict) -> None:
    """If Meta returned error code 190 (invalid token), mark the connection
    as needing re-auth so the UI can prompt the user."""
    code = error.get("code") if isinstance(error, dict) else None
    if code == 190:
        await db.meta_connections.update_one(
            {"workspace_owner": wo, "page_id": page_id},
            {"$set": {"requires_reauth": True, "updated_at": _now()}},
        )
