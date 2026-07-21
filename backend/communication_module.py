"""Communication module — internal channels + messages + shared inbox.

Simple polling-based messaging (no websockets — kept intentionally lean
for jury demo). Every user in the workspace can create channels; messages
are scoped to a channel; a shared "inbox" pseudo-channel `__inbox__` is
auto-created per workspace for founder announcements.

Collections:
  - comm_channels { id, workspace_owner, name, description?, kind
                   ("channel"/"inbox"), created_by, created_at, message_count }
  - comm_messages { id, workspace_owner, channel_id, author_email,
                    author_name, body, created_at }
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field


class ChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=400)


class MessageIn(BaseModel):
    channel_id: str
    body: str = Field(min_length=1, max_length=4000)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/comm", tags=["communication"])

    async def _ensure_inbox(wo: str, user: dict):
        exists = await db.comm_channels.find_one(
            {"workspace_owner": wo, "kind": "inbox"}
        )
        if exists:
            return exists
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "name": "Inbox",
            "description": "Shared inbox — direct messages & announcements",
            "kind": "inbox",
            "created_by": user.get("email"),
            "created_at": _now(),
            "message_count": 0,
        }
        await db.comm_channels.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/channels")
    async def list_channels(user=Depends(get_user)):
        wo = _wo(user)
        await _ensure_inbox(wo, user)
        rows = await db.comm_channels.find(
            {"workspace_owner": wo}, {"_id": 0}
        ).sort([("kind", 1), ("created_at", 1)]).to_list(200)
        return {"channels": rows}

    @router.post("/channels", status_code=201)
    async def create_channel(payload: ChannelIn, user=Depends(get_user)):
        # Normalise name: strip leading # if user typed one.
        name = payload.name.strip().lstrip("#").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Channel name is required")
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "name": name,
            "description": payload.description,
            "kind": "channel",
            "created_by": user.get("email"),
            "created_at": _now(),
            "message_count": 0,
        }
        await db.comm_channels.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/channels/{cid}")
    async def delete_channel(cid: str, user=Depends(get_user)):
        # Inbox is protected.
        ch = await db.comm_channels.find_one({"id": cid, "workspace_owner": _wo(user)})
        if not ch:
            raise HTTPException(status_code=404, detail="Channel not found")
        if ch.get("kind") == "inbox":
            raise HTTPException(status_code=400, detail="The Inbox channel cannot be deleted.")
        await db.comm_channels.delete_one({"id": cid, "workspace_owner": _wo(user)})
        await db.comm_messages.delete_many({"channel_id": cid, "workspace_owner": _wo(user)})
        return {"ok": True, "id": cid}

    @router.get("/messages")
    async def list_messages(
        user=Depends(get_user),
        channel_id: str = Query(...),
        limit: int = Query(default=100, le=500),
    ):
        wo = _wo(user)
        # Ownership check
        ch = await db.comm_channels.find_one({"id": channel_id, "workspace_owner": wo})
        if not ch:
            raise HTTPException(status_code=404, detail="Channel not found")
        rows = await db.comm_messages.find(
            {"channel_id": channel_id, "workspace_owner": wo}, {"_id": 0}
        ).sort("created_at", 1).to_list(limit)
        return {"messages": rows, "channel": {**ch, "_id": None}}

    @router.post("/messages", status_code=201)
    async def create_message(payload: MessageIn, user=Depends(get_user)):
        wo = _wo(user)
        ch = await db.comm_channels.find_one({"id": payload.channel_id, "workspace_owner": wo})
        if not ch:
            raise HTTPException(status_code=404, detail="Channel not found")
        author_name = (
            (user.get("first_name") or "").strip() + " " + (user.get("last_name") or "").strip()
        ).strip() or user.get("email")
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "channel_id": payload.channel_id,
            "author_email": user.get("email"),
            "author_name": author_name,
            "body": payload.body,
            "created_at": _now(),
        }
        await db.comm_messages.insert_one(doc)
        await db.comm_channels.update_one(
            {"id": payload.channel_id},
            {"$inc": {"message_count": 1}, "$set": {"last_message_at": doc["created_at"]}},
        )
        doc.pop("_id", None)
        return doc

    @router.delete("/messages/{mid}")
    async def delete_message(mid: str, user=Depends(get_user)):
        res = await db.comm_messages.delete_one({"id": mid, "workspace_owner": _wo(user)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"ok": True, "id": mid}

    return router
