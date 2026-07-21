"""Accounting module — journal entries, trial balance, P&L.

Simple double-entry bookkeeping:
  - Chart of accounts is auto-seeded per workspace on first use with a
    standard SME set (Dutch RGS-inspired but simplified).
  - Journal entries are groups of >=2 lines; sum of debits must equal
    sum of credits (validated on POST).
  - Trial balance = totals per account.
  - P&L = revenue accounts − expense accounts over a date range.

Collections:
  - acc_accounts         { id, workspace_owner, code, name, type
                           ("asset"/"liability"/"equity"/"revenue"/"expense"),
                           parent_id?, is_system, created_at }
  - acc_journal_entries  { id, workspace_owner, entry_no, date, description,
                           lines: [{ account_id, account_code, description?,
                                     debit, credit }],
                           total_debit, total_credit, created_at, created_by }
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, field_validator


# Standard chart — auto-seeded on first use per workspace.
DEFAULT_COA = [
    # Assets (1xxx)
    ("1000", "Cash & bank",              "asset"),
    ("1200", "Accounts receivable",      "asset"),
    ("1300", "Inventory",                "asset"),
    ("1500", "Prepaid expenses",         "asset"),
    ("1800", "Fixed assets",             "asset"),
    # Liabilities (2xxx)
    ("2000", "Accounts payable",         "liability"),
    ("2100", "VAT payable",              "liability"),
    ("2200", "Wages payable",            "liability"),
    ("2500", "Long-term loans",          "liability"),
    # Equity (3xxx)
    ("3000", "Owner's equity",           "equity"),
    ("3100", "Retained earnings",        "equity"),
    # Revenue (4xxx)
    ("4000", "Product sales",            "revenue"),
    ("4100", "Service revenue",          "revenue"),
    ("4900", "Other income",             "revenue"),
    # Expenses (5xxx – 7xxx)
    ("5000", "Cost of goods sold",       "expense"),
    ("5100", "Software & subscriptions", "expense"),
    ("5200", "Rent & utilities",         "expense"),
    ("5300", "Marketing & advertising",  "expense"),
    ("5400", "Wages & benefits",         "expense"),
    ("5500", "Professional services",    "expense"),
    ("5600", "Travel & meals",           "expense"),
    ("5700", "Depreciation",             "expense"),
    ("5900", "Bank fees & interest",     "expense"),
]


class JournalLineIn(BaseModel):
    account_id: Optional[str] = None
    account_code: Optional[str] = None  # convenience: resolve to id server-side
    description: Optional[str] = Field(default=None, max_length=500)
    debit: float = Field(default=0, ge=0)
    credit: float = Field(default=0, ge=0)

    @field_validator("credit")
    @classmethod
    def _one_side_only(cls, v, info):
        d = info.data.get("debit") or 0
        # A line must be exactly one of debit or credit > 0.
        if (d > 0 and v > 0) or (d == 0 and v == 0):
            raise ValueError("each line must have either debit or credit > 0, not both")
        return v


class JournalEntryIn(BaseModel):
    date: str  # ISO date
    description: Optional[str] = Field(default=None, max_length=500)
    lines: List[JournalLineIn] = Field(min_length=2)

    @field_validator("lines")
    @classmethod
    def _balances(cls, lines: List[JournalLineIn]):
        d = round(sum(l.debit for l in lines), 2)
        c = round(sum(l.credit for l in lines), 2)
        if d != c:
            raise ValueError(f"entry does not balance: debit={d} vs credit={c}")
        if d == 0:
            raise ValueError("entry total must be > 0")
        return lines


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/accounting", tags=["accounting"])

    async def _seed_coa_if_empty(wo: str):
        exists = await db.acc_accounts.find_one({"workspace_owner": wo})
        if exists:
            return
        docs = [
            {
                "id": str(uuid.uuid4()),
                "workspace_owner": wo,
                "code": code,
                "name": name,
                "type": kind,
                "is_system": True,
                "created_at": _now(),
            }
            for code, name, kind in DEFAULT_COA
        ]
        if docs:
            await db.acc_accounts.insert_many(docs)

    # ---- Chart of accounts -----------------------------------------------
    @router.get("/accounts")
    async def list_accounts(user=Depends(get_user)):
        wo = _wo(user)
        await _seed_coa_if_empty(wo)
        rows = await db.acc_accounts.find(
            {"workspace_owner": wo}, {"_id": 0}
        ).sort("code", 1).to_list(500)
        return {"accounts": rows}

    # ---- Journal entries -------------------------------------------------
    @router.get("/journal-entries")
    async def list_journal(
        user=Depends(get_user),
        date_from: Optional[str] = Query(default=None),
        date_to: Optional[str] = Query(default=None),
        limit: int = Query(default=100, le=500),
    ):
        wo = _wo(user)
        q = {"workspace_owner": wo}
        if date_from or date_to:
            drange: dict = {}
            if date_from:
                drange["$gte"] = date_from
            if date_to:
                drange["$lte"] = date_to
            q["date"] = drange
        rows = await db.acc_journal_entries.find(q, {"_id": 0}).sort([("date", -1), ("entry_no", -1)]).to_list(limit)
        return {"entries": rows}

    @router.post("/journal-entries", status_code=201)
    async def create_journal(payload: JournalEntryIn, user=Depends(get_user)):
        wo = _wo(user)
        await _seed_coa_if_empty(wo)
        # Resolve account_code → account_id if provided.
        accounts = await db.acc_accounts.find(
            {"workspace_owner": wo}, {"_id": 0}
        ).to_list(500)
        by_code = {a["code"]: a for a in accounts}
        by_id = {a["id"]: a for a in accounts}
        resolved_lines: list[dict] = []
        for line in payload.lines:
            acct = None
            if line.account_id and line.account_id in by_id:
                acct = by_id[line.account_id]
            elif line.account_code and line.account_code in by_code:
                acct = by_code[line.account_code]
            if not acct:
                raise HTTPException(
                    status_code=400,
                    detail=f"Account not found: id={line.account_id} code={line.account_code}",
                )
            resolved_lines.append({
                "account_id": acct["id"],
                "account_code": acct["code"],
                "account_name": acct["name"],
                "account_type": acct["type"],
                "description": line.description,
                "debit": round(float(line.debit), 2),
                "credit": round(float(line.credit), 2),
            })
        entry_no = (await db.acc_journal_entries.count_documents({"workspace_owner": wo})) + 1
        d_total = round(sum(l["debit"] for l in resolved_lines), 2)
        c_total = round(sum(l["credit"] for l in resolved_lines), 2)
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "entry_no": entry_no,
            "date": payload.date,
            "description": payload.description,
            "lines": resolved_lines,
            "total_debit": d_total,
            "total_credit": c_total,
            "created_at": _now(),
            "created_by": user.get("email"),
        }
        await db.acc_journal_entries.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/journal-entries/{eid}")
    async def delete_journal(eid: str, user=Depends(get_user)):
        res = await db.acc_journal_entries.delete_one({"id": eid, "workspace_owner": _wo(user)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Entry not found")
        return {"ok": True, "id": eid}

    # ---- Reports ---------------------------------------------------------
    @router.get("/trial-balance")
    async def trial_balance(user=Depends(get_user), as_of: Optional[str] = None):
        wo = _wo(user)
        await _seed_coa_if_empty(wo)
        q = {"workspace_owner": wo}
        if as_of:
            q["date"] = {"$lte": as_of}
        entries = await db.acc_journal_entries.find(q, {"_id": 0}).to_list(5000)

        totals: dict = {}
        for e in entries:
            for l in e.get("lines", []):
                aid = l["account_id"]
                t = totals.setdefault(aid, {
                    "account_id": aid,
                    "account_code": l["account_code"],
                    "account_name": l["account_name"],
                    "account_type": l["account_type"],
                    "debit": 0.0, "credit": 0.0,
                })
                t["debit"] += l["debit"]
                t["credit"] += l["credit"]

        # Include zero-balance accounts too so users see the full CoA.
        accounts = await db.acc_accounts.find({"workspace_owner": wo}, {"_id": 0}).to_list(500)
        rows = []
        for a in accounts:
            t = totals.get(a["id"], {
                "account_id": a["id"], "account_code": a["code"],
                "account_name": a["name"], "account_type": a["type"],
                "debit": 0.0, "credit": 0.0,
            })
            # Compute net side based on account type convention.
            net = round(t["debit"] - t["credit"], 2)
            rows.append({**t, "debit": round(t["debit"], 2),
                         "credit": round(t["credit"], 2), "balance": net})
        rows.sort(key=lambda r: r["account_code"])
        total_debit = round(sum(r["debit"] for r in rows), 2)
        total_credit = round(sum(r["credit"] for r in rows), 2)
        return {
            "as_of": as_of,
            "rows": rows,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "balanced": total_debit == total_credit,
        }

    @router.get("/pnl")
    async def profit_and_loss(
        user=Depends(get_user),
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ):
        wo = _wo(user)
        await _seed_coa_if_empty(wo)
        q: dict = {"workspace_owner": wo}
        drange: dict = {}
        if date_from:
            drange["$gte"] = date_from
        if date_to:
            drange["$lte"] = date_to
        if drange:
            q["date"] = drange
        entries = await db.acc_journal_entries.find(q, {"_id": 0}).to_list(5000)

        by_acct: dict = {}
        for e in entries:
            for l in e.get("lines", []):
                if l["account_type"] not in ("revenue", "expense"):
                    continue
                aid = l["account_id"]
                cur = by_acct.setdefault(aid, {
                    "account_id": aid, "account_code": l["account_code"],
                    "account_name": l["account_name"], "account_type": l["account_type"],
                    "amount": 0.0,
                })
                # Revenue accounts increase on credit side (net = credit - debit).
                # Expense accounts increase on debit side.
                if l["account_type"] == "revenue":
                    cur["amount"] += l["credit"] - l["debit"]
                else:
                    cur["amount"] += l["debit"] - l["credit"]

        revenue = [
            {**a, "amount": round(a["amount"], 2)}
            for a in by_acct.values() if a["account_type"] == "revenue"
        ]
        expenses = [
            {**a, "amount": round(a["amount"], 2)}
            for a in by_acct.values() if a["account_type"] == "expense"
        ]
        revenue.sort(key=lambda a: a["account_code"])
        expenses.sort(key=lambda a: a["account_code"])
        total_revenue = round(sum(a["amount"] for a in revenue), 2)
        total_expenses = round(sum(a["amount"] for a in expenses), 2)
        net_income = round(total_revenue - total_expenses, 2)
        return {
            "date_from": date_from, "date_to": date_to,
            "revenue": revenue, "expenses": expenses,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "net_income": net_income,
        }

    return router
