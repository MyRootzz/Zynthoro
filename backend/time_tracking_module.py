"""Time Tracking module — live timer + manual entries + timesheets + CSV.

Design:
  - Every user can have AT MOST ONE running timer at a time. When a new
    timer starts while another runs, the old one is auto-stopped and its
    elapsed time is committed as a time_entry.
  - Manual entries are added directly.
  - Weekly timesheet aggregates entries by (project_id, task_id?) x day.
  - CSV export streams a `text/csv` response.

Collections:
  - time_entries  { id, workspace_owner, user_email, project_id?, task_id?,
                    date (ISO YYYY-MM-DD), hours (float), notes, billable,
                    source ("timer"/"manual"), created_at, updated_at }
  - time_timers   { id, workspace_owner, user_email, project_id?, task_id?,
                    notes, billable, started_at (ISO), created_at }
                    (There is only ever 0 or 1 timer per (workspace, user).)
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone, date, timedelta
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


def _monday(iso_date: str) -> date:
    d = date.fromisoformat(iso_date[:10])
    return d - timedelta(days=d.weekday())


# ---- schemas --------------------------------------------------------------
class EntryIn(BaseModel):
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    date: str  # ISO date
    hours: float = Field(gt=0, le=24)
    notes: Optional[str] = Field(default="", max_length=1000)
    billable: Optional[bool] = True


class TimerStartIn(BaseModel):
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    notes: Optional[str] = Field(default="", max_length=1000)
    billable: Optional[bool] = True


class TimerStopIn(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=1000)


# ---- helpers --------------------------------------------------------------
async def _finalize_timer(db, timer: dict) -> dict:
    """Convert a running timer into a persisted time_entry and delete it.

    Returns the created entry doc.
    """
    started = datetime.fromisoformat(timer["started_at"].replace("Z", "+00:00"))
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    hours = max(0.0, round(elapsed / 3600.0, 4))
    entry = {
        "id": str(uuid.uuid4()),
        "workspace_owner": timer["workspace_owner"],
        "user_email": timer.get("user_email"),
        "project_id": timer.get("project_id"),
        "task_id": timer.get("task_id"),
        "date": started.date().isoformat(),
        "hours": hours,
        "notes": timer.get("notes") or "",
        "billable": bool(timer.get("billable", True)),
        "source": "timer",
        "created_at": _now(),
        "updated_at": _now(),
    }
    if hours > 0:
        await db.time_entries.insert_one(entry)
    await db.time_timers.delete_one({"id": timer["id"]})
    entry.pop("_id", None)
    return entry


# ---- router ---------------------------------------------------------------
def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/time-tracking", tags=["time-tracking"])

    async def _enrich(rows: list, wo: str) -> None:
        """Attach project_name + task_title to a list of time_entries."""
        pids = list({r.get("project_id") for r in rows if r.get("project_id")})
        tids = list({r.get("task_id") for r in rows if r.get("task_id")})
        pmap: dict = {}
        tmap: dict = {}
        if pids:
            async for p in db.projects.find(
                {"workspace_owner": wo, "id": {"$in": pids}}, {"_id": 0, "id": 1, "name": 1, "color": 1},
            ):
                pmap[p["id"]] = p
        if tids:
            async for t in db.project_tasks.find(
                {"workspace_owner": wo, "id": {"$in": tids}}, {"_id": 0, "id": 1, "title": 1},
            ):
                tmap[t["id"]] = t
        for r in rows:
            p = pmap.get(r.get("project_id"))
            t = tmap.get(r.get("task_id"))
            r["project_name"] = p.get("name") if p else None
            r["project_color"] = p.get("color") if p else "#1A4FFF"
            r["task_title"] = t.get("title") if t else None

    # ---- Timer ------------------------------------------------------------
    @router.get("/timer")
    async def get_timer(user=Depends(get_user)):
        wo = _wo(user)
        timer = await db.time_timers.find_one(
            {"workspace_owner": wo, "user_email": user.get("email")}, {"_id": 0},
        )
        if not timer:
            return {"timer": None}
        started = datetime.fromisoformat(timer["started_at"].replace("Z", "+00:00"))
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds())
        timer["elapsed_seconds"] = elapsed
        await _enrich([timer], wo)
        return {"timer": timer}

    @router.post("/timer/start", status_code=201)
    async def start_timer(payload: TimerStartIn, user=Depends(get_user)):
        wo = _wo(user)
        # Stop existing timer (if any) and roll it into an entry.
        prior = await db.time_timers.find_one(
            {"workspace_owner": wo, "user_email": user.get("email")},
        )
        finalized = None
        if prior:
            finalized = await _finalize_timer(db, prior)
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "user_email": user.get("email"),
            "project_id": payload.project_id,
            "task_id": payload.task_id,
            "notes": payload.notes or "",
            "billable": bool(payload.billable),
            "started_at": _now(),
            "created_at": _now(),
        }
        await db.time_timers.insert_one(doc)
        doc.pop("_id", None)
        return {"timer": doc, "auto_committed": finalized}

    @router.post("/timer/stop")
    async def stop_timer(payload: TimerStopIn, user=Depends(get_user)):
        wo = _wo(user)
        timer = await db.time_timers.find_one(
            {"workspace_owner": wo, "user_email": user.get("email")},
        )
        if not timer:
            raise HTTPException(status_code=404, detail="No timer is running.")
        if payload.notes is not None:
            timer["notes"] = payload.notes
        entry = await _finalize_timer(db, timer)
        return {"entry": entry}

    @router.delete("/timer")
    async def cancel_timer(user=Depends(get_user)):
        wo = _wo(user)
        res = await db.time_timers.delete_one(
            {"workspace_owner": wo, "user_email": user.get("email")},
        )
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="No timer is running.")
        return {"ok": True}

    # ---- Manual entries ---------------------------------------------------
    @router.get("/entries")
    async def list_entries(
        user=Depends(get_user),
        start: Optional[str] = Query(default=None, description="ISO date (inclusive)"),
        end: Optional[str] = Query(default=None, description="ISO date (inclusive)"),
        project_id: Optional[str] = None,
    ):
        wo = _wo(user)
        q = {"workspace_owner": wo}
        if project_id:
            q["project_id"] = project_id
        if start or end:
            q["date"] = {}
            if start:
                q["date"]["$gte"] = start
            if end:
                q["date"]["$lte"] = end
        rows = await db.time_entries.find(q, {"_id": 0}).sort("date", -1).to_list(1000)
        await _enrich(rows, wo)
        total = round(sum(float(r.get("hours") or 0) for r in rows), 2)
        billable = round(sum(float(r.get("hours") or 0) for r in rows if r.get("billable")), 2)
        return {
            "entries": rows,
            "totals": {"hours": total, "billable_hours": billable, "count": len(rows)},
        }

    @router.post("/entries", status_code=201)
    async def create_entry(payload: EntryIn, user=Depends(get_user)):
        wo = _wo(user)
        doc = payload.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "user_email": user.get("email"),
            "source": "manual",
            "created_at": _now(),
            "updated_at": _now(),
        })
        await db.time_entries.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/entries/{eid}")
    async def update_entry(eid: str, payload: EntryIn, user=Depends(get_user)):
        wo = _wo(user)
        update = payload.model_dump()
        update["updated_at"] = _now()
        res = await db.time_entries.update_one(
            {"id": eid, "workspace_owner": wo}, {"$set": update},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Entry not found")
        doc = await db.time_entries.find_one({"id": eid}, {"_id": 0})
        return doc

    @router.delete("/entries/{eid}")
    async def delete_entry(eid: str, user=Depends(get_user)):
        wo = _wo(user)
        res = await db.time_entries.delete_one({"id": eid, "workspace_owner": wo})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Entry not found")
        return {"ok": True, "id": eid}

    # ---- Weekly timesheet -------------------------------------------------
    @router.get("/timesheet")
    async def timesheet(
        user=Depends(get_user),
        week_of: Optional[str] = Query(default=None, description="Any ISO date within the target week"),
    ):
        wo = _wo(user)
        anchor = week_of or date.today().isoformat()
        monday = _monday(anchor)
        sunday = monday + timedelta(days=6)
        rows = await db.time_entries.find(
            {"workspace_owner": wo, "date": {"$gte": monday.isoformat(), "$lte": sunday.isoformat()}},
            {"_id": 0},
        ).to_list(2000)
        await _enrich(rows, wo)

        # Group by (project_id, task_id) -> {day_iso: hours}
        buckets: dict = {}
        for r in rows:
            key = (r.get("project_id") or "_none_", r.get("task_id") or "_none_")
            if key not in buckets:
                buckets[key] = {
                    "project_id": r.get("project_id"),
                    "task_id": r.get("task_id"),
                    "project_name": r.get("project_name") or "Unassigned",
                    "project_color": r.get("project_color") or "#94a3b8",
                    "task_title": r.get("task_title"),
                    "days": {(monday + timedelta(days=i)).isoformat(): 0.0 for i in range(7)},
                    "total": 0.0,
                }
            buckets[key]["days"][r["date"]] = buckets[key]["days"].get(r["date"], 0.0) + float(r.get("hours") or 0)
            buckets[key]["total"] += float(r.get("hours") or 0)

        # Round nicely.
        for b in buckets.values():
            for d in b["days"]:
                b["days"][d] = round(b["days"][d], 2)
            b["total"] = round(b["total"], 2)

        day_totals = {}
        for i in range(7):
            d = (monday + timedelta(days=i)).isoformat()
            day_totals[d] = round(sum(b["days"].get(d, 0.0) for b in buckets.values()), 2)

        return {
            "week_of": monday.isoformat(),
            "days": [(monday + timedelta(days=i)).isoformat() for i in range(7)],
            "rows": list(buckets.values()),
            "day_totals": day_totals,
            "grand_total": round(sum(day_totals.values()), 2),
        }

    # ---- CSV export -------------------------------------------------------
    @router.get("/entries/export.csv")
    async def export_csv(
        user=Depends(get_user),
        start: Optional[str] = None,
        end: Optional[str] = None,
    ):
        wo = _wo(user)
        q = {"workspace_owner": wo}
        if start or end:
            q["date"] = {}
            if start:
                q["date"]["$gte"] = start
            if end:
                q["date"]["$lte"] = end
        rows = await db.time_entries.find(q, {"_id": 0}).sort("date", -1).to_list(10000)
        await _enrich(rows, wo)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "date", "user_email", "project", "task",
            "hours", "billable", "notes", "source",
        ])
        for r in rows:
            writer.writerow([
                r.get("date"),
                r.get("user_email") or "",
                r.get("project_name") or "",
                r.get("task_title") or "",
                r.get("hours"),
                "yes" if r.get("billable") else "no",
                (r.get("notes") or "").replace("\n", " "),
                r.get("source") or "manual",
            ])
        csv_bytes = buf.getvalue().encode("utf-8")
        filename = f"timesheet_{start or 'all'}_{end or 'all'}.csv"
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router
