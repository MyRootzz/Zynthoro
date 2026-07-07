"""Canva Connect API integration — OAuth 2.0 (PKCE) + designs/export endpoints."""

import base64
import hashlib
import os
import secrets
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

CANVA_AUTH_URL = "https://www.canva.com/api/oauth/authorize"
CANVA_API = "https://api.canva.com/rest/v1"
CANVA_SCOPES = "design:content:read design:content:write design:meta:read profile:read"

ALLOWED_PRESETS = {"doc", "whiteboard", "presentation"}


def _client_creds():
    cid = os.environ.get("CANVA_CLIENT_ID")
    secret = os.environ.get("CANVA_CLIENT_SECRET")
    if not cid or not secret:
        raise HTTPException(status_code=503, detail="Canva integration is not configured")
    return cid, secret


def _basic_auth_header() -> str:
    cid, secret = _client_creds()
    return "Basic " + base64.b64encode(f"{cid}:{secret}".encode()).decode()


def _external_host(request: Request) -> str:
    return request.headers.get("x-forwarded-host") or request.headers.get("host", "")


def _redirect_uri(request: Request) -> str:
    return f"https://{_external_host(request)}/api/canva/callback"


class CreateDesignIn(BaseModel):
    title: Optional[str] = "Zynthoro design"
    preset: str = "presentation"


class ExportIn(BaseModel):
    format: str = "pdf"


def build_router(db: AsyncIOMotorDatabase, get_current_user_full):
    router = APIRouter(prefix="/api/canva", tags=["canva"])

    async def _get_valid_token(user_id: str) -> str:
        conn = await db.canva_connections.find_one({"user_id": user_id})
        if not conn:
            raise HTTPException(status_code=400, detail="Canva account not connected")
        if time.time() > conn["expires_at"] - 300:
            async with httpx.AsyncClient(timeout=20) as http:
                resp = await http.post(
                    f"{CANVA_API}/oauth/token",
                    headers={
                        "Authorization": _basic_auth_header(),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={"grant_type": "refresh_token", "refresh_token": conn["refresh_token"]},
                )
            data = resp.json()
            if "access_token" not in data:
                await db.canva_connections.delete_one({"user_id": user_id})
                raise HTTPException(status_code=400, detail="Canva session expired — please reconnect")
            await db.canva_connections.update_one(
                {"user_id": user_id},
                {"$set": {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", conn["refresh_token"]),
                    "expires_at": time.time() + data.get("expires_in", 14400),
                }},
            )
            return data["access_token"]
        return conn["access_token"]

    async def _canva_request(user_id: str, method: str, path: str, json_body=None, params=None):
        token = await _get_valid_token(user_id)
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.request(
                method, f"{CANVA_API}{path}",
                headers={"Authorization": f"Bearer {token}"},
                json=json_body, params=params,
            )
        if resp.status_code == 401:
            raise HTTPException(status_code=400, detail="Canva session expired — please reconnect")
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("message") or resp.json()
            except Exception:
                detail = resp.text[:300]
            raise HTTPException(status_code=502, detail=f"Canva API error: {detail}")
        return resp.json()

    @router.get("/status")
    async def canva_status(user=Depends(get_current_user_full)):
        configured = bool(os.environ.get("CANVA_CLIENT_ID") and os.environ.get("CANVA_CLIENT_SECRET"))
        conn = await db.canva_connections.find_one({"user_id": user["id"]}, {"_id": 0, "access_token": 0, "refresh_token": 0})
        return {
            "configured": configured,
            "connected": bool(conn),
            "display_name": (conn or {}).get("display_name"),
            "connected_at": (conn or {}).get("connected_at"),
        }

    @router.get("/connect")
    async def canva_connect(request: Request, user=Depends(get_current_user_full)):
        cid, _ = _client_creds()
        code_verifier = base64.urlsafe_b64encode(os.urandom(48)).decode().rstrip("=")
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")
        state = secrets.token_urlsafe(24)
        redirect_uri = _redirect_uri(request)
        await db.canva_oauth_states.delete_many({"created_at": {"$lt": time.time() - 900}})
        await db.canva_oauth_states.insert_one({
            "state": state,
            "user_id": user["id"],
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "created_at": time.time(),
        })
        from urllib.parse import urlencode
        params = {
            "client_id": cid,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": CANVA_SCOPES,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        return {"url": f"{CANVA_AUTH_URL}?{urlencode(params)}"}

    @router.get("/callback")
    async def canva_callback(request: Request, code: Optional[str] = None,
                             state: Optional[str] = None, error: Optional[str] = None):
        host = _external_host(request)
        fail_url = f"https://{host}/dashboard/marketing?canva=error"
        if error or not code or not state:
            return RedirectResponse(fail_url)
        st = await db.canva_oauth_states.find_one({"state": state})
        if not st or time.time() - st["created_at"] > 600:
            return RedirectResponse(fail_url)
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(
                f"{CANVA_API}/oauth/token",
                headers={
                    "Authorization": _basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": st["code_verifier"],
                    "redirect_uri": st["redirect_uri"],
                },
            )
        data = resp.json()
        if "access_token" not in data:
            return RedirectResponse(fail_url)
        display_name = None
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                prof = await http.get(
                    f"{CANVA_API}/users/me/profile",
                    headers={"Authorization": f"Bearer {data['access_token']}"},
                )
            if prof.status_code == 200:
                display_name = prof.json().get("profile", {}).get("display_name")
        except Exception:
            pass
        await db.canva_connections.update_one(
            {"user_id": st["user_id"]},
            {"$set": {
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "expires_at": time.time() + data.get("expires_in", 14400),
                "scope": data.get("scope"),
                "display_name": display_name,
                "connected_at": time.time(),
            }},
            upsert=True,
        )
        await db.canva_oauth_states.delete_one({"state": state})
        return RedirectResponse(f"https://{host}/dashboard/marketing?canva=connected")

    @router.post("/disconnect")
    async def canva_disconnect(user=Depends(get_current_user_full)):
        await db.canva_connections.delete_one({"user_id": user["id"]})
        return {"ok": True}

    @router.get("/designs")
    async def list_designs(continuation: Optional[str] = None, user=Depends(get_current_user_full)):
        params = {"continuation": continuation} if continuation else None
        return await _canva_request(user["id"], "GET", "/designs", params=params)

    @router.post("/designs")
    async def create_design(payload: CreateDesignIn, user=Depends(get_current_user_full)):
        preset = payload.preset if payload.preset in ALLOWED_PRESETS else "presentation"
        body = {
            "design_type": {"type": "preset", "name": preset},
            "title": (payload.title or "Zynthoro design")[:255],
        }
        return await _canva_request(user["id"], "POST", "/designs", json_body=body)

    @router.post("/designs/{design_id}/export")
    async def export_design(design_id: str, payload: ExportIn, user=Depends(get_current_user_full)):
        fmt = {"type": "pdf"} if payload.format != "png" else {"type": "png", "lossless": True}
        body = {"design_id": design_id, "format": fmt}
        return await _canva_request(user["id"], "POST", "/exports", json_body=body)

    @router.get("/exports/{job_id}")
    async def export_status(job_id: str, user=Depends(get_current_user_full)):
        return await _canva_request(user["id"], "GET", f"/exports/{job_id}")

    return router
