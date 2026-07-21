"""HR module — employees, contracts, leave requests.

Simple CRUD per workspace. No plan-gating: HR is part of every module set
(the sidebar item's plan-lock is handled at UI level; the API accepts any
authenticated user and scopes by `workspace_owner`).

Collections:
  - hr_employees      { id, workspace_owner, first_name, last_name, email,
                        job_title, department, employment_type, start_date,
                        salary_eur, status, notes, created_at, updated_at }
  - hr_contracts      { id, workspace_owner, employee_id, contract_type,
                        start_date, end_date, hours_per_week, salary_eur,
                        notes, created_at, updated_at }
  - hr_leave_requests { id, workspace_owner, employee_id, kind, start_date,
                        end_date, days, reason, status ("pending"/"approved"/"rejected"),
                        decided_by, decided_at, created_at, updated_at }
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, date
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


# --- schemas ---------------------------------------------------------------
class EmployeeIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    job_title: Optional[str] = Field(default=None, max_length=120)
    department: Optional[str] = Field(default=None, max_length=120)
    employment_type: Optional[Literal["full_time", "part_time", "contractor", "intern"]] = "full_time"
    start_date: Optional[str] = None  # ISO date
    salary_eur: Optional[float] = Field(default=None, ge=0)
    status: Optional[Literal["active", "on_leave", "terminated"]] = "active"
    notes: Optional[str] = Field(default=None, max_length=2000)


class ContractIn(BaseModel):
    employee_id: str
    contract_type: Literal["permanent", "fixed_term", "freelance", "internship"] = "permanent"
    start_date: str
    end_date: Optional[str] = None
    hours_per_week: Optional[float] = Field(default=40, ge=0, le=168)
    salary_eur: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=2000)


class LeaveIn(BaseModel):
    employee_id: str
    kind: Literal["holiday", "sick", "parental", "unpaid", "other"] = "holiday"
    start_date: str
    end_date: str
    reason: Optional[str] = Field(default=None, max_length=1000)


class LeaveDecision(BaseModel):
    status: Literal["approved", "rejected"]


def _diff_days(start: str, end: str) -> int:
    try:
        s = date.fromisoformat(start[:10])
        e = date.fromisoformat(end[:10])
        return max(1, (e - s).days + 1)
    except Exception:
        return 1


def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/hr", tags=["hr"])

    # ---- Employees --------------------------------------------------------
    @router.get("/employees")
    async def list_employees(user=Depends(get_user)):
        rows = await db.hr_employees.find(
            {"workspace_owner": _wo(user)}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)
        return {"employees": rows}

    @router.post("/employees", status_code=201)
    async def create_employee(payload: EmployeeIn, user=Depends(get_user)):
        doc = payload.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "created_at": _now(),
            "updated_at": _now(),
        })
        await db.hr_employees.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/employees/{eid}")
    async def update_employee(eid: str, payload: EmployeeIn, user=Depends(get_user)):
        update = payload.model_dump()
        update["updated_at"] = _now()
        res = await db.hr_employees.update_one(
            {"id": eid, "workspace_owner": _wo(user)}, {"$set": update},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Employee not found")
        doc = await db.hr_employees.find_one({"id": eid}, {"_id": 0})
        return doc

    @router.delete("/employees/{eid}")
    async def delete_employee(eid: str, user=Depends(get_user)):
        res = await db.hr_employees.delete_one({"id": eid, "workspace_owner": _wo(user)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Employee not found")
        # Cascade cleanup: remove dependent contracts + leave rows
        await db.hr_contracts.delete_many({"employee_id": eid, "workspace_owner": _wo(user)})
        await db.hr_leave_requests.delete_many({"employee_id": eid, "workspace_owner": _wo(user)})
        return {"ok": True, "id": eid}

    # ---- Contracts --------------------------------------------------------
    @router.get("/contracts")
    async def list_contracts(user=Depends(get_user), employee_id: Optional[str] = None):
        q = {"workspace_owner": _wo(user)}
        if employee_id:
            q["employee_id"] = employee_id
        rows = await db.hr_contracts.find(q, {"_id": 0}).sort("start_date", -1).to_list(500)
        return {"contracts": rows}

    @router.post("/contracts", status_code=201)
    async def create_contract(payload: ContractIn, user=Depends(get_user)):
        # Verify employee belongs to the same workspace.
        emp = await db.hr_employees.find_one(
            {"id": payload.employee_id, "workspace_owner": _wo(user)}
        )
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found in your workspace")
        doc = payload.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "created_at": _now(),
            "updated_at": _now(),
        })
        await db.hr_contracts.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/contracts/{cid}")
    async def delete_contract(cid: str, user=Depends(get_user)):
        res = await db.hr_contracts.delete_one({"id": cid, "workspace_owner": _wo(user)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Contract not found")
        return {"ok": True, "id": cid}

    # ---- Leave requests ---------------------------------------------------
    @router.get("/leave-requests")
    async def list_leave(user=Depends(get_user), status: Optional[str] = None):
        q = {"workspace_owner": _wo(user)}
        if status:
            q["status"] = status
        rows = await db.hr_leave_requests.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"leave_requests": rows}

    @router.post("/leave-requests", status_code=201)
    async def create_leave(payload: LeaveIn, user=Depends(get_user)):
        emp = await db.hr_employees.find_one(
            {"id": payload.employee_id, "workspace_owner": _wo(user)}
        )
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found in your workspace")
        days = _diff_days(payload.start_date, payload.end_date)
        doc = payload.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "days": days,
            "status": "pending",
            "decided_by": None,
            "decided_at": None,
            "created_at": _now(),
            "updated_at": _now(),
        })
        await db.hr_leave_requests.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/leave-requests/{lid}/decide")
    async def decide_leave(lid: str, payload: LeaveDecision, user=Depends(get_user)):
        res = await db.hr_leave_requests.update_one(
            {"id": lid, "workspace_owner": _wo(user)},
            {"$set": {
                "status": payload.status,
                "decided_by": user.get("email"),
                "decided_at": _now(),
                "updated_at": _now(),
            }},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Leave request not found")
        doc = await db.hr_leave_requests.find_one({"id": lid}, {"_id": 0})
        return doc

    @router.delete("/leave-requests/{lid}")
    async def delete_leave(lid: str, user=Depends(get_user)):
        res = await db.hr_leave_requests.delete_one({"id": lid, "workspace_owner": _wo(user)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Leave request not found")
        return {"ok": True, "id": lid}

    return router
