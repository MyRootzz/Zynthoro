"""Sales module — leads + pipeline (kanban stages).

CRUD per workspace, scoped by `workspace_owner`.

Collections:
  - sales_leads  { id, workspace_owner, name, company, email, phone, source,
                   stage ("new"/"contacted"/"proposal"/"won"/"lost"),
                   value, currency, expected_close, notes,
                   stage_history: [{ stage, at, by }],
                   created_at, updated_at }
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, Field

import activity_log


PIPELINE_STAGES: List[str] = ["new", "contacted", "proposal", "won", "lost"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


# ---- schemas --------------------------------------------------------------
class LeadIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company: Optional[str] = Field(default="", max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default="", max_length=60)
    source: Optional[str] = Field(default="", max_length=100)
    stage: Optional[Literal["new", "contacted", "proposal", "won", "lost"]] = "new"
    value: Optional[float] = Field(default=0, ge=0)
    currency: Optional[Literal["EUR", "USD", "GBP"]] = "EUR"
    expected_close: Optional[str] = None  # ISO date
    notes: Optional[str] = Field(default="", max_length=5000)


class StageIn(BaseModel):
    stage: Literal["new", "contacted", "proposal", "won", "lost"]


# ---- router ---------------------------------------------------------------
def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/sales", tags=["sales"])

    @router.get("/leads")
    async def list_leads(user=Depends(get_user), stage: Optional[str] = None):
        q: dict = {"workspace_owner": _wo(user)}
        if stage:
            q["stage"] = stage
        rows = await db.sales_leads.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
        return {"leads": rows}

    @router.get("/pipeline")
    async def pipeline(user=Depends(get_user)):
        rows = await db.sales_leads.find(
            {"workspace_owner": _wo(user)}, {"_id": 0},
        ).sort("updated_at", -1).to_list(1000)
        by_stage: dict = {s: {"stage": s, "leads": [], "count": 0, "total_value": 0.0} for s in PIPELINE_STAGES}
        for r in rows:
            s = r.get("stage") or "new"
            if s not in by_stage:
                s = "new"
            by_stage[s]["leads"].append(r)
            by_stage[s]["count"] += 1
            by_stage[s]["total_value"] += float(r.get("value") or 0)
        columns = [by_stage[s] for s in PIPELINE_STAGES]
        won_value = by_stage["won"]["total_value"]
        open_value = sum(by_stage[s]["total_value"] for s in ("new", "contacted", "proposal"))
        return {
            "columns": columns,
            "totals": {
                "total_leads": len(rows),
                "open_value": round(open_value, 2),
                "won_value": round(won_value, 2),
                "lost_count": by_stage["lost"]["count"],
            },
        }

    @router.post("/leads", status_code=201)
    async def create_lead(payload: LeadIn, user=Depends(get_user)):
        wo = _wo(user)
        stage = payload.stage or "new"
        doc = payload.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "stage": stage,
            "value": float(payload.value or 0),
            "stage_history": [{"stage": stage, "at": _now(), "by": user.get("email")}],
            "created_at": _now(),
            "updated_at": _now(),
        })
        await db.sales_leads.insert_one(doc)
        doc.pop("_id", None)
        try:
            await activity_log.log_event(
                db, workspace_owner=wo, actor_email=user.get("email"),
                event_type="lead_created", icon="user_plus",
                title=f"New lead: {doc['name']}",
                subtitle=f"{doc.get('company') or 'No company'} · {stage}",
                href="/dashboard/sales",
            )
        except Exception:
            pass
        return doc

    @router.get("/leads/{lid}")
    async def get_lead(lid: str, user=Depends(get_user)):
        doc = await db.sales_leads.find_one(
            {"id": lid, "workspace_owner": _wo(user)}, {"_id": 0},
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Lead not found")
        return doc

    @router.put("/leads/{lid}")
    async def update_lead(lid: str, payload: LeadIn, user=Depends(get_user)):
        wo = _wo(user)
        existing = await db.sales_leads.find_one({"id": lid, "workspace_owner": wo})
        if not existing:
            raise HTTPException(status_code=404, detail="Lead not found")
        update = payload.model_dump()
        update["value"] = float(payload.value or 0)
        update["updated_at"] = _now()

        # If stage changed, append to history.
        new_stage = update.get("stage") or existing.get("stage") or "new"
        old_stage = existing.get("stage") or "new"
        if new_stage != old_stage:
            hist = list(existing.get("stage_history") or [])
            hist.append({"stage": new_stage, "at": _now(), "by": user.get("email")})
            update["stage_history"] = hist

        await db.sales_leads.update_one(
            {"id": lid, "workspace_owner": wo}, {"$set": update},
        )
        doc = await db.sales_leads.find_one({"id": lid}, {"_id": 0})
        return doc

    @router.put("/leads/{lid}/stage")
    async def change_stage(lid: str, payload: StageIn, user=Depends(get_user)):
        wo = _wo(user)
        existing = await db.sales_leads.find_one({"id": lid, "workspace_owner": wo})
        if not existing:
            raise HTTPException(status_code=404, detail="Lead not found")
        if existing.get("stage") == payload.stage:
            doc = existing.copy()
            doc.pop("_id", None)
            return doc
        hist = list(existing.get("stage_history") or [])
        hist.append({"stage": payload.stage, "at": _now(), "by": user.get("email")})
        await db.sales_leads.update_one(
            {"id": lid, "workspace_owner": wo},
            {"$set": {
                "stage": payload.stage,
                "stage_history": hist,
                "updated_at": _now(),
            }},
        )
        try:
            await activity_log.log_event(
                db, workspace_owner=wo, actor_email=user.get("email"),
                event_type="lead_stage_changed", icon="sparkles",
                title=f"{existing['name']} moved to {payload.stage.title()}",
                subtitle=existing.get("company") or "",
                href="/dashboard/sales",
            )
        except Exception:
            pass
        doc = await db.sales_leads.find_one({"id": lid}, {"_id": 0})
        return doc

    @router.delete("/leads/{lid}")
    async def delete_lead(lid: str, user=Depends(get_user)):
        res = await db.sales_leads.delete_one({"id": lid, "workspace_owner": _wo(user)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Lead not found")
        return {"ok": True, "id": lid}

    return router
