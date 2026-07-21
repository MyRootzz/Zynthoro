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

    return router
