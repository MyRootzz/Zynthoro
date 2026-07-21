"""Projects module — projects, tasks, milestones.

Collections:
  - projects           { id, workspace_owner, name, description, status
                         ("planning"/"on_track"/"at_risk"/"completed"/"on_hold"),
                         domain, owner, start_date, end_date, progress,
                         color, created_at, updated_at }
  - project_tasks      { id, workspace_owner, project_id, title, description,
                         assignee, status ("todo"/"in_progress"/"done"),
                         priority ("low"/"medium"/"high"), due_date,
                         sprint_id?, created_at, updated_at, completed_at? }
  - project_milestones { id, workspace_owner, project_id, title, due_date,
                         completed, completed_at?, created_at, updated_at }
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

import activity_log
# Import finance helpers so we can create a proper draft invoice.
from finance_module import (
    _default_settings as _finance_default_settings,
    _totals as _finance_totals,
    _sym as _finance_sym,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


# ---- schemas --------------------------------------------------------------
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default="", max_length=5000)
    status: Optional[Literal["planning", "on_track", "at_risk", "completed", "on_hold"]] = "planning"
    domain: Optional[str] = Field(default="", max_length=100)
    owner: Optional[str] = Field(default="", max_length=200)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    progress: Optional[int] = Field(default=0, ge=0, le=100)
    color: Optional[str] = Field(default="#1A4FFF", max_length=20)


class TaskIn(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = Field(default="", max_length=5000)
    assignee: Optional[str] = Field(default="", max_length=200)
    status: Optional[Literal["todo", "in_progress", "done"]] = "todo"
    priority: Optional[Literal["low", "medium", "high"]] = "medium"
    due_date: Optional[str] = None


class TaskStatusIn(BaseModel):
    status: Literal["todo", "in_progress", "done"]


class MilestoneIn(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=300)
    due_date: Optional[str] = None
    completed: Optional[bool] = False


class BillHoursIn(BaseModel):
    lead_id: str
    hourly_rate: float = Field(gt=0, le=100000)
    currency: Optional[Literal["EUR", "USD", "GBP"]] = "EUR"
    due_in_days: Optional[int] = Field(default=14, ge=0, le=365)
    tax_rate: Optional[float] = Field(default=21.0, ge=0, le=100)


# ---- router ---------------------------------------------------------------
def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/projects", tags=["projects"])

    async def _recompute_progress(wo: str, project_id: str) -> None:
        """Recalculate a project's `progress` from its task completion."""
        tasks = await db.project_tasks.find(
            {"workspace_owner": wo, "project_id": project_id},
        ).to_list(1000)
        if not tasks:
            return
        done = sum(1 for t in tasks if t.get("status") == "done")
        progress = int(round(100 * done / len(tasks)))
        await db.projects.update_one(
            {"id": project_id, "workspace_owner": wo},
            {"$set": {"progress": progress, "updated_at": _now()}},
        )

    # ---- Projects ---------------------------------------------------------
    @router.get("")
    async def list_projects(user=Depends(get_user), status: Optional[str] = None):
        q = {"workspace_owner": _wo(user)}
        if status:
            q["status"] = status
        rows = await db.projects.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        # Attach task counts on-the-fly for the list view.
        counts: dict = {}
        pids = [r["id"] for r in rows]
        if pids:
            pipeline = [
                {"$match": {"workspace_owner": _wo(user), "project_id": {"$in": pids}}},
                {"$group": {"_id": {"p": "$project_id", "s": "$status"}, "n": {"$sum": 1}}},
            ]
            async for a in db.project_tasks.aggregate(pipeline):
                pid = a["_id"]["p"]
                counts.setdefault(pid, {"todo": 0, "in_progress": 0, "done": 0, "total": 0})
                counts[pid][a["_id"]["s"]] = a["n"]
                counts[pid]["total"] += a["n"]
        for r in rows:
            r["task_counts"] = counts.get(r["id"], {"todo": 0, "in_progress": 0, "done": 0, "total": 0})
        totals = {
            "total": len(rows),
            "on_track": sum(1 for r in rows if r.get("status") == "on_track"),
            "at_risk": sum(1 for r in rows if r.get("status") == "at_risk"),
            "completed": sum(1 for r in rows if r.get("status") == "completed"),
        }
        return {"projects": rows, "totals": totals}

    @router.post("", status_code=201)
    async def create_project(payload: ProjectIn, user=Depends(get_user)):
        wo = _wo(user)
        doc = payload.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "created_at": _now(),
            "updated_at": _now(),
        })
        await db.projects.insert_one(doc)
        doc.pop("_id", None)
        try:
            await activity_log.log_event(
                db, workspace_owner=wo, actor_email=user.get("email"),
                event_type="project_created", icon="folder_plus",
                title=f"New project: {doc['name']}",
                subtitle=doc.get("domain") or None,
                href="/dashboard/projects",
            )
        except Exception:
            pass
        return doc

    @router.get("/{pid}")
    async def get_project(pid: str, user=Depends(get_user)):
        wo = _wo(user)
        p = await db.projects.find_one({"id": pid, "workspace_owner": wo}, {"_id": 0})
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        tasks = await db.project_tasks.find(
            {"workspace_owner": wo, "project_id": pid}, {"_id": 0},
        ).sort("created_at", -1).to_list(500)
        milestones = await db.project_milestones.find(
            {"workspace_owner": wo, "project_id": pid}, {"_id": 0},
        ).sort("due_date", 1).to_list(200)
        return {"project": p, "tasks": tasks, "milestones": milestones}

    @router.put("/{pid}")
    async def update_project(pid: str, payload: ProjectIn, user=Depends(get_user)):
        wo = _wo(user)
        update = payload.model_dump()
        update["updated_at"] = _now()
        res = await db.projects.update_one(
            {"id": pid, "workspace_owner": wo}, {"$set": update},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        doc = await db.projects.find_one({"id": pid}, {"_id": 0})
        return doc

    @router.delete("/{pid}")
    async def delete_project(pid: str, user=Depends(get_user)):
        wo = _wo(user)
        res = await db.projects.delete_one({"id": pid, "workspace_owner": wo})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        # Cascade cleanup: tasks + milestones + time entries + sprint task refs.
        await db.project_tasks.delete_many({"workspace_owner": wo, "project_id": pid})
        await db.project_milestones.delete_many({"workspace_owner": wo, "project_id": pid})
        await db.time_entries.delete_many({"workspace_owner": wo, "project_id": pid})
        return {"ok": True, "id": pid}

    # ---- Tasks ------------------------------------------------------------
    @router.get("/{pid}/tasks")
    async def list_tasks(pid: str, user=Depends(get_user)):
        rows = await db.project_tasks.find(
            {"workspace_owner": _wo(user), "project_id": pid}, {"_id": 0},
        ).sort("created_at", -1).to_list(1000)
        return {"tasks": rows}

    @router.post("/tasks", status_code=201)
    async def create_task(payload: TaskIn, user=Depends(get_user)):
        wo = _wo(user)
        p = await db.projects.find_one({"id": payload.project_id, "workspace_owner": wo})
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        doc = payload.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "sprint_id": None,
            "completed_at": _now() if payload.status == "done" else None,
            "created_at": _now(),
            "updated_at": _now(),
        })
        await db.project_tasks.insert_one(doc)
        doc.pop("_id", None)
        await _recompute_progress(wo, payload.project_id)
        return doc

    @router.put("/tasks/{tid}")
    async def update_task(tid: str, payload: TaskIn, user=Depends(get_user)):
        wo = _wo(user)
        existing = await db.project_tasks.find_one({"id": tid, "workspace_owner": wo})
        if not existing:
            raise HTTPException(status_code=404, detail="Task not found")
        update = payload.model_dump()
        # Set completed_at when the task becomes done.
        if update.get("status") == "done" and existing.get("status") != "done":
            update["completed_at"] = _now()
        elif update.get("status") != "done":
            update["completed_at"] = None
        update["updated_at"] = _now()
        await db.project_tasks.update_one({"id": tid, "workspace_owner": wo}, {"$set": update})
        await _recompute_progress(wo, update["project_id"])
        doc = await db.project_tasks.find_one({"id": tid}, {"_id": 0})
        return doc

    @router.put("/tasks/{tid}/status")
    async def change_task_status(tid: str, payload: TaskStatusIn, user=Depends(get_user)):
        wo = _wo(user)
        existing = await db.project_tasks.find_one({"id": tid, "workspace_owner": wo})
        if not existing:
            raise HTTPException(status_code=404, detail="Task not found")
        completed_at = _now() if payload.status == "done" else None
        await db.project_tasks.update_one(
            {"id": tid, "workspace_owner": wo},
            {"$set": {"status": payload.status, "completed_at": completed_at, "updated_at": _now()}},
        )
        await _recompute_progress(wo, existing["project_id"])
        doc = await db.project_tasks.find_one({"id": tid}, {"_id": 0})
        return doc

    @router.delete("/tasks/{tid}")
    async def delete_task(tid: str, user=Depends(get_user)):
        wo = _wo(user)
        existing = await db.project_tasks.find_one({"id": tid, "workspace_owner": wo})
        if not existing:
            raise HTTPException(status_code=404, detail="Task not found")
        await db.project_tasks.delete_one({"id": tid, "workspace_owner": wo})
        await db.time_entries.delete_many({"workspace_owner": wo, "task_id": tid})
        await _recompute_progress(wo, existing["project_id"])
        return {"ok": True, "id": tid}

    # ---- Milestones -------------------------------------------------------
    @router.post("/milestones", status_code=201)
    async def create_milestone(payload: MilestoneIn, user=Depends(get_user)):
        wo = _wo(user)
        p = await db.projects.find_one({"id": payload.project_id, "workspace_owner": wo})
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        doc = payload.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "completed_at": _now() if payload.completed else None,
            "created_at": _now(),
            "updated_at": _now(),
        })
        await db.project_milestones.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/milestones/{mid}/toggle")
    async def toggle_milestone(mid: str, user=Depends(get_user)):
        wo = _wo(user)
        m = await db.project_milestones.find_one({"id": mid, "workspace_owner": wo})
        if not m:
            raise HTTPException(status_code=404, detail="Milestone not found")
        completed = not bool(m.get("completed"))
        await db.project_milestones.update_one(
            {"id": mid, "workspace_owner": wo},
            {"$set": {
                "completed": completed,
                "completed_at": _now() if completed else None,
                "updated_at": _now(),
            }},
        )
        doc = await db.project_milestones.find_one({"id": mid}, {"_id": 0})
        return doc

    @router.delete("/milestones/{mid}")
    async def delete_milestone(mid: str, user=Depends(get_user)):
        wo = _wo(user)
        res = await db.project_milestones.delete_one({"id": mid, "workspace_owner": wo})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Milestone not found")
        return {"ok": True, "id": mid}

    # ---- Bill unbilled billable time → draft invoice ---------------------
    @router.get("/{pid}/billable-summary")
    async def billable_summary(pid: str, user=Depends(get_user)):
        """Return billable unbilled time for a project, grouped by task,
        so the UI can preview line items before creating the invoice.
        """
        wo = _wo(user)
        p = await db.projects.find_one({"id": pid, "workspace_owner": wo})
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")

        entries = await db.time_entries.find(
            {"workspace_owner": wo, "project_id": pid,
             "billable": True,
             "$or": [{"invoiced": {"$exists": False}}, {"invoiced": False}]},
            {"_id": 0},
        ).to_list(5000)

        # Group by task_id.
        by_task: dict = {}
        tids = list({e.get("task_id") for e in entries if e.get("task_id")})
        titles: dict = {}
        if tids:
            async for t in db.project_tasks.find(
                {"workspace_owner": wo, "id": {"$in": tids}},
                {"_id": 0, "id": 1, "title": 1},
            ):
                titles[t["id"]] = t["title"]
        for e in entries:
            tid = e.get("task_id") or "_no_task_"
            key = tid
            if key not in by_task:
                by_task[key] = {
                    "task_id": e.get("task_id"),
                    "task_title": titles.get(tid, "General work"),
                    "hours": 0.0,
                    "entry_count": 0,
                }
            by_task[key]["hours"] += float(e.get("hours") or 0)
            by_task[key]["entry_count"] += 1
        for b in by_task.values():
            b["hours"] = round(b["hours"], 2)

        total_hours = round(sum(b["hours"] for b in by_task.values()), 2)
        return {
            "project": {"id": p["id"], "name": p["name"], "color": p.get("color", "#1A4FFF")},
            "unbilled_lines": sorted(by_task.values(), key=lambda x: -x["hours"]),
            "unbilled_hours": total_hours,
            "unbilled_entry_count": len(entries),
        }

    @router.post("/{pid}/invoice-billable-time", status_code=201)
    async def invoice_billable_time(pid: str, payload: BillHoursIn, user=Depends(get_user)):
        """Create a draft invoice from a project's unbilled billable hours.

        Concurrency-safe: atomically CLAIMS unbilled entries with a temporary
        `invoice_id=<claim_token>` before building the invoice. Two concurrent
        requests will each only see the entries they successfully claimed —
        the same hour can never end up on two draft invoices.
        """
        wo = _wo(user)
        p = await db.projects.find_one({"id": pid, "workspace_owner": wo})
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")

        lead = await db.sales_leads.find_one({"id": payload.lead_id, "workspace_owner": wo})
        if not lead:
            raise HTTPException(status_code=404, detail="Sales lead not found in your workspace")
        if lead.get("stage") != "won":
            raise HTTPException(
                status_code=400,
                detail="Only 'won' leads can be used as invoice clients. Move the lead to Won first.",
            )

        # --- ATOMIC CLAIM PASS ---
        # Each individual `update_many` document write is atomic in Mongo.
        # By filtering on `invoiced: false/missing` and setting `invoiced=True`
        # in one statement, only ONE concurrent request can win each doc.
        claim_token = f"claim-{uuid.uuid4()}"
        claim_res = await db.time_entries.update_many(
            {"workspace_owner": wo, "project_id": pid, "billable": True,
             "$or": [{"invoiced": {"$exists": False}}, {"invoiced": False}]},
            {"$set": {"invoiced": True, "invoice_id": claim_token, "updated_at": _now()}},
        )
        if claim_res.modified_count == 0:
            raise HTTPException(status_code=400, detail="No unbilled billable time entries for this project.")

        # Fetch ONLY the entries this request successfully claimed.
        entries = await db.time_entries.find(
            {"workspace_owner": wo, "invoice_id": claim_token},
        ).to_list(10000)
        if not entries:
            # Extremely unlikely (would need a purge between claim and read)
            # but be defensive.
            raise HTTPException(status_code=400, detail="Claimed entries disappeared before invoicing.")

        try:
            tids = list({e.get("task_id") for e in entries if e.get("task_id")})
            titles: dict = {}
            if tids:
                async for t in db.project_tasks.find(
                    {"workspace_owner": wo, "id": {"$in": tids}},
                    {"_id": 0, "id": 1, "title": 1},
                ):
                    titles[t["id"]] = t["title"]

            buckets: dict = {}
            for e in entries:
                tid = e.get("task_id") or "_no_task_"
                if tid not in buckets:
                    buckets[tid] = {"title": titles.get(tid, "General work"), "hours": 0.0}
                buckets[tid]["hours"] += float(e.get("hours") or 0)

            items: List[dict] = []
            for tid, b in buckets.items():
                if b["hours"] <= 0:
                    continue
                items.append({
                    "description": f"{b['title']} ({p['name']}) — {round(b['hours'], 2)}h",
                    "quantity": round(b["hours"], 2),
                    "unit_price": float(payload.hourly_rate),
                    "tax_rate": float(payload.tax_rate or 0),
                })
            if not items:
                raise HTTPException(status_code=400, detail="Nothing to invoice (zero total hours).")

            # Ensure finance_settings exists (idempotent) and grab an invoice number.
            settings = await db.finance_settings.find_one({"workspace_owner": wo}, {"_id": 0})
            if not settings:
                settings = _finance_default_settings(wo)
                settings["created_at"] = _now()
                await db.finance_settings.insert_one(dict(settings))

            # Atomic sequence bump — same logic as finance_module.
            res = await db.finance_settings.find_one_and_update(
                {"workspace_owner": wo}, {"$inc": {"next_invoice_seq": 1}},
                return_document=True,
            )
            seq = max(1, int((res or settings).get("next_invoice_seq", 1)) - 1)
            prefix = settings.get("invoice_prefix") or "INV-"
            from datetime import date as _date
            number = f"{prefix}{_date.today().year}-{seq:04d}"

            subtotal, tax_total, total = _finance_totals(items)

            today = datetime.now(timezone.utc).date().isoformat()
            due_date = None
            if payload.due_in_days is not None:
                from datetime import timedelta
                due_date = (datetime.now(timezone.utc).date() + timedelta(days=int(payload.due_in_days))).isoformat()

            invoice_id = str(uuid.uuid4())
            invoice = {
                "id": invoice_id,
                "workspace_owner": wo,
                "number": number,
                "client_name": lead["name"] + (f" · {lead['company']}" if lead.get("company") else ""),
                "client_email": lead.get("email"),
                "client_address": "",
                "issue_date": today,
                "due_date": due_date,
                "currency": payload.currency or settings.get("currency") or "EUR",
                "items": items,
                "subtotal": subtotal, "tax_total": tax_total, "total": total,
                "status": "draft",
                "payment_terms": settings.get("default_payment_terms", ""),
                "bank_details": settings.get("default_bank_details", ""),
                "notes": f"Billed from time tracking for project “{p['name']}”.",
                "sent_at": None, "paid_at": None,
                "created_at": _now(), "updated_at": _now(),
                "source_project_id": pid,
                "source_lead_id": lead["id"],
            }
            await db.finance_invoices.insert_one(invoice)

            # Commit: swap the claim token for the real invoice id.
            await db.time_entries.update_many(
                {"workspace_owner": wo, "invoice_id": claim_token},
                {"$set": {"invoice_id": invoice_id, "updated_at": _now()}},
            )
        except HTTPException:
            # On any downstream failure, RELEASE the claimed entries so they
            # can be billed by a retry — never leave them in limbo.
            await db.time_entries.update_many(
                {"workspace_owner": wo, "invoice_id": claim_token},
                {"$set": {"invoiced": False, "invoice_id": None, "updated_at": _now()}},
            )
            raise
        except Exception:
            await db.time_entries.update_many(
                {"workspace_owner": wo, "invoice_id": claim_token},
                {"$set": {"invoiced": False, "invoice_id": None, "updated_at": _now()}},
            )
            raise

        try:
            await activity_log.log_event(
                db, workspace_owner=wo, actor_email=user.get("email"),
                event_type="invoice_from_hours",
                icon="receipt",
                title=f"Invoice {number} drafted from {round(sum(e['hours'] for e in entries), 2)}h billable",
                subtitle=f"{p['name']} → {lead['name']} · {_finance_sym(invoice['currency'])}{total:,.2f}",
                href="/dashboard/finance",
            )
        except Exception:
            pass

        invoice.pop("_id", None)
        return {
            "invoice": invoice,
            "entries_marked": len(entries),
            "hours_billed": round(sum(float(e.get("hours") or 0) for e in entries), 2),
        }

    return router
