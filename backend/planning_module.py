"""Planning module — workspace-wide sprints; tasks from any project.

Sprints are workspace-wide (per user's C2 choice) — a sprint can host tasks
from any project. Task-sprint linking is done by writing `sprint_id` on the
existing `project_tasks` document, so a task remains a single source of
truth (no duplication) and shows up both in Projects and Planning views.

Collections:
  - sprints  { id, workspace_owner, name, goal, start_date, end_date,
               status ("planned"/"active"/"completed"),
               capacity_hours?, created_at, updated_at }
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


# ---- schemas --------------------------------------------------------------
class SprintIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    goal: Optional[str] = Field(default="", max_length=2000)
    start_date: str
    end_date: str
    status: Optional[Literal["planned", "active", "completed"]] = "planned"
    capacity_hours: Optional[float] = Field(default=None, ge=0)


class SprintTaskIn(BaseModel):
    task_id: str


# ---- router ---------------------------------------------------------------
def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/planning", tags=["planning"])

    async def _summary(wo: str, sprint_id: str) -> dict:
        tasks = await db.project_tasks.find(
            {"workspace_owner": wo, "sprint_id": sprint_id}, {"_id": 0},
        ).to_list(500)
        done = sum(1 for t in tasks if t.get("status") == "done")
        in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
        todo = len(tasks) - done - in_progress
        return {
            "task_count": len(tasks),
            "done": done,
            "in_progress": in_progress,
            "todo": todo,
            "progress": int(round(100 * done / len(tasks))) if tasks else 0,
        }

    # ---- Sprints ----------------------------------------------------------
    @router.get("/sprints")
    async def list_sprints(user=Depends(get_user)):
        wo = _wo(user)
        rows = await db.sprints.find({"workspace_owner": wo}, {"_id": 0}) \
            .sort("start_date", -1).to_list(200)
        for r in rows:
            r["summary"] = await _summary(wo, r["id"])
        return {"sprints": rows}

    @router.post("/sprints", status_code=201)
    async def create_sprint(payload: SprintIn, user=Depends(get_user)):
        wo = _wo(user)
        doc = payload.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "created_at": _now(),
            "updated_at": _now(),
        })
        await db.sprints.insert_one(doc)
        doc.pop("_id", None)
        doc["summary"] = await _summary(wo, doc["id"])
        return doc

    @router.get("/sprints/{sid}")
    async def get_sprint(sid: str, user=Depends(get_user)):
        wo = _wo(user)
        s = await db.sprints.find_one({"id": sid, "workspace_owner": wo}, {"_id": 0})
        if not s:
            raise HTTPException(status_code=404, detail="Sprint not found")
        tasks = await db.project_tasks.find(
            {"workspace_owner": wo, "sprint_id": sid}, {"_id": 0},
        ).sort("created_at", -1).to_list(500)
        # Enrich tasks with their project name for the sprint board.
        pids = list({t.get("project_id") for t in tasks if t.get("project_id")})
        pname: dict = {}
        if pids:
            async for p in db.projects.find(
                {"workspace_owner": wo, "id": {"$in": pids}}, {"_id": 0, "id": 1, "name": 1, "color": 1},
            ):
                pname[p["id"]] = {"name": p.get("name"), "color": p.get("color", "#1A4FFF")}
        for t in tasks:
            info = pname.get(t.get("project_id"), {})
            t["project_name"] = info.get("name")
            t["project_color"] = info.get("color", "#1A4FFF")
        s["summary"] = await _summary(wo, sid)
        return {"sprint": s, "tasks": tasks}

    @router.put("/sprints/{sid}")
    async def update_sprint(sid: str, payload: SprintIn, user=Depends(get_user)):
        wo = _wo(user)
        update = payload.model_dump()
        update["updated_at"] = _now()
        res = await db.sprints.update_one(
            {"id": sid, "workspace_owner": wo}, {"$set": update},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Sprint not found")
        doc = await db.sprints.find_one({"id": sid}, {"_id": 0})
        doc["summary"] = await _summary(wo, sid)
        return doc

    @router.delete("/sprints/{sid}")
    async def delete_sprint(sid: str, user=Depends(get_user)):
        wo = _wo(user)
        res = await db.sprints.delete_one({"id": sid, "workspace_owner": wo})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Sprint not found")
        # Detach tasks (keep them, just remove the sprint link).
        await db.project_tasks.update_many(
            {"workspace_owner": wo, "sprint_id": sid},
            {"$set": {"sprint_id": None, "updated_at": _now()}},
        )
        return {"ok": True, "id": sid}

    # ---- Sprint <-> Task linking -----------------------------------------
    @router.post("/sprints/{sid}/tasks", status_code=201)
    async def add_task_to_sprint(sid: str, payload: SprintTaskIn, user=Depends(get_user)):
        wo = _wo(user)
        s = await db.sprints.find_one({"id": sid, "workspace_owner": wo})
        if not s:
            raise HTTPException(status_code=404, detail="Sprint not found")
        t = await db.project_tasks.find_one({"id": payload.task_id, "workspace_owner": wo})
        if not t:
            raise HTTPException(status_code=404, detail="Task not found in your workspace")
        await db.project_tasks.update_one(
            {"id": payload.task_id, "workspace_owner": wo},
            {"$set": {"sprint_id": sid, "updated_at": _now()}},
        )
        return {"ok": True, "task_id": payload.task_id, "sprint_id": sid}

    @router.delete("/sprints/{sid}/tasks/{tid}")
    async def remove_task_from_sprint(sid: str, tid: str, user=Depends(get_user)):
        wo = _wo(user)
        res = await db.project_tasks.update_one(
            {"id": tid, "workspace_owner": wo, "sprint_id": sid},
            {"$set": {"sprint_id": None, "updated_at": _now()}},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not linked to this sprint")
        return {"ok": True, "task_id": tid}

    # ---- Available tasks (for the "Add task" picker) ---------------------
    @router.get("/available-tasks")
    async def available_tasks(user=Depends(get_user)):
        """All un-sprinted tasks in the workspace (candidates to add)."""
        wo = _wo(user)
        rows = await db.project_tasks.find(
            {"workspace_owner": wo, "$or": [{"sprint_id": None}, {"sprint_id": {"$exists": False}}]},
            {"_id": 0},
        ).sort("created_at", -1).to_list(1000)
        # Enrich with project name.
        pids = list({t.get("project_id") for t in rows if t.get("project_id")})
        pname: dict = {}
        if pids:
            async for p in db.projects.find(
                {"workspace_owner": wo, "id": {"$in": pids}}, {"_id": 0, "id": 1, "name": 1},
            ):
                pname[p["id"]] = p.get("name")
        for t in rows:
            t["project_name"] = pname.get(t.get("project_id"))
        return {"tasks": rows}

    return router
