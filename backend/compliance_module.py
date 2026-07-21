"""Compliance module — GDPR checklist, audit log viewer, policy library.

- GDPR checklist: a curated list of tasks per workspace. Each workspace
  auto-seeds the same checklist on first read; users can check/uncheck
  and add notes per item.
- Audit log viewer: unified read-only feed pulling from `activity_events`,
  `security_incidents`, and `payment_transactions` (blocked entries).
- Policy library: workspace-scoped documents (title + body + version +
  updated_at). Auto-seeds a starter set of policy templates.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field


# ---- Seed data ------------------------------------------------------------
GDPR_ITEMS = [
    ("data-inventory",       "Data inventory & mapping",
     "List every category of personal data you process, its purpose, legal basis, and retention."),
    ("privacy-notice",       "Public privacy notice published",
     "A clear, up-to-date privacy notice is accessible from your public site."),
    ("consent-records",      "Consent records for marketing",
     "You capture and store timestamp + IP + text-shown for every marketing opt-in."),
    ("dpa-vendors",          "DPAs signed with every processor",
     "Data Processing Agreements in place with Stripe, Resend, Anthropic, Google, Emergent, hosting, etc."),
    ("dsar-process",         "Data Subject Access Request (DSAR) process",
     "You have a documented process to answer access / erasure / portability requests within 30 days."),
    ("breach-runbook",       "Data breach notification runbook",
     "72-hour supervisory-authority notification path is documented and tested."),
    ("retention-policy",     "Retention & deletion policy",
     "Every collection has a retention rule; deletion happens automatically or on schedule."),
    ("access-controls",      "Least-privilege access controls",
     "Employees only have access to systems needed for their role; access is reviewed quarterly."),
    ("encryption",           "Encryption at rest & in transit",
     "All personal data is encrypted at rest (Mongo Atlas / disk) and in transit (TLS 1.2+)."),
    ("staff-training",       "Staff privacy training",
     "All staff completed GDPR / security awareness training in the last 12 months."),
    ("dpo",                  "DPO / privacy contact designated",
     "A privacy contact is named on the website and knows their responsibilities."),
    ("logs-retention",       "Audit log retention",
     "Security-relevant events (logins, admin actions, data exports) are logged for ≥12 months."),
]

POLICY_TEMPLATES = [
    ("Data Protection & Privacy Policy",
     "Defines how personal data is collected, processed, stored, and shared. "
     "Anchors GDPR compliance; must be reviewed annually."),
    ("Information Security Policy",
     "Access control, encryption, incident response, and acceptable-use rules for all employees."),
    ("Data Retention & Deletion Policy",
     "Defines retention periods for each data category and the deletion cadence."),
    ("Data Breach Response Plan",
     "Roles, escalation, and 72-hour notification workflow when a breach is suspected."),
    ("Third-Party Data Processor Register",
     "Living list of every processor with DPA status, purpose, transfer mechanism, and DPO contact."),
    ("Acceptable Use Policy",
     "Rules for staff using company IT, AI assistants, and customer data."),
]


class ChecklistToggleIn(BaseModel):
    checked: bool
    notes: Optional[str] = Field(default=None, max_length=1000)


class PolicyIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=50_000)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/compliance", tags=["compliance"])

    async def _seed_checklist(wo: str):
        existing = await db.compliance_checklist.count_documents({"workspace_owner": wo})
        if existing:
            return
        docs = [
            {
                "id": str(uuid.uuid4()),
                "workspace_owner": wo,
                "key": key,
                "title": title,
                "description": desc,
                "checked": False,
                "notes": None,
                "updated_at": _now(),
                "created_at": _now(),
            }
            for key, title, desc in GDPR_ITEMS
        ]
        if docs:
            await db.compliance_checklist.insert_many(docs)

    async def _seed_policies(wo: str):
        existing = await db.compliance_policies.count_documents({"workspace_owner": wo})
        if existing:
            return
        docs = [
            {
                "id": str(uuid.uuid4()),
                "workspace_owner": wo,
                "title": title,
                "body": body,
                "version": 1,
                "is_template": True,
                "created_at": _now(),
                "updated_at": _now(),
            }
            for title, body in POLICY_TEMPLATES
        ]
        if docs:
            await db.compliance_policies.insert_many(docs)

    # ---- GDPR Checklist ---------------------------------------------------
    @router.get("/checklist")
    async def get_checklist(user=Depends(get_user)):
        wo = _wo(user)
        await _seed_checklist(wo)
        rows = await db.compliance_checklist.find(
            {"workspace_owner": wo}, {"_id": 0}
        ).sort("created_at", 1).to_list(200)
        total = len(rows)
        done = sum(1 for r in rows if r.get("checked"))
        return {
            "items": rows,
            "total": total,
            "done": done,
            "progress_pct": round((done / total) * 100) if total else 0,
        }

    @router.put("/checklist/{item_id}")
    async def toggle_checklist(item_id: str, payload: ChecklistToggleIn, user=Depends(get_user)):
        res = await db.compliance_checklist.update_one(
            {"id": item_id, "workspace_owner": _wo(user)},
            {"$set": {
                "checked": payload.checked,
                "notes": payload.notes,
                "updated_at": _now(),
                "updated_by": user.get("email"),
            }},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Checklist item not found")
        item = await db.compliance_checklist.find_one({"id": item_id}, {"_id": 0})
        return item

    # ---- Audit log viewer -------------------------------------------------
    @router.get("/audit-log")
    async def audit_log(
        user=Depends(get_user),
        limit: int = Query(default=100, le=500),
        source: Optional[Literal["activity", "security", "payments", "all"]] = "all",
    ):
        wo = _wo(user)
        items: list[dict] = []

        if source in ("activity", "all"):
            rows = await db.activity_events.find(
                {"workspace_owner": wo}, {"_id": 0}
            ).sort("created_at", -1).to_list(limit)
            for r in rows:
                items.append({
                    "source": "activity",
                    "at": r.get("created_at") or r.get("timestamp"),
                    "type": r.get("event_type") or r.get("type"),
                    "title": r.get("title") or r.get("message"),
                    "subtitle": r.get("subtitle"),
                    "actor": r.get("actor_email"),
                    "metadata": r.get("metadata"),
                })

        if source in ("security", "all"):
            # Security incidents are workspace-agnostic (system-wide).
            # Only expose them to the founder + workspace-owner themselves.
            is_admin = bool(user.get("is_founder") or user.get("is_unlimited"))
            q = {} if is_admin else {"user_id": user.get("id")}
            rows = await db.security_incidents.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
            for r in rows:
                items.append({
                    "source": "security",
                    "at": r.get("created_at"),
                    "type": r.get("type"),
                    "title": f"Security incident: {r.get('type')}",
                    "subtitle": (
                        f"amount paid €{(r.get('amount_paid_cents') or 0)/100:.2f} vs expected "
                        f"€{(r.get('expected_cents') or 0)/100:.2f}"
                    ),
                    "actor": r.get("user_email"),
                    "metadata": {
                        "session_id": r.get("session_id"),
                        "tier_key": r.get("tier_key"),
                    },
                })

        if source in ("payments", "all"):
            # Show provisioning-blocked payment attempts (coupon abuse etc.)
            q_pay = {
                "provisioning_blocked": True,
            }
            if not (user.get("is_founder") or user.get("is_unlimited")):
                q_pay["user_id"] = user.get("id")
            rows = await db.payment_transactions.find(
                q_pay, {"_id": 0}
            ).sort("provisioning_blocked_at", -1).to_list(limit)
            for r in rows:
                items.append({
                    "source": "payments",
                    "at": r.get("provisioning_blocked_at") or r.get("updated_at"),
                    "type": "payment_blocked",
                    "title": f"Blocked payment: {r.get('provisioning_blocked_reason','unknown')}",
                    "subtitle": r.get("session_id"),
                    "actor": None,
                    "metadata": {"user_id": r.get("user_id")},
                })

        # Sort combined feed by timestamp desc; None goes last.
        items.sort(key=lambda x: (x.get("at") or ""), reverse=True)
        return {"items": items[:limit], "total": len(items)}

    # ---- Policy library ---------------------------------------------------
    @router.get("/policies")
    async def list_policies(user=Depends(get_user)):
        wo = _wo(user)
        await _seed_policies(wo)
        rows = await db.compliance_policies.find(
            {"workspace_owner": wo}, {"_id": 0}
        ).sort("title", 1).to_list(200)
        return {"policies": rows}

    @router.post("/policies", status_code=201)
    async def create_policy(payload: PolicyIn, user=Depends(get_user)):
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "title": payload.title,
            "body": payload.body,
            "version": 1,
            "is_template": False,
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.compliance_policies.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/policies/{pid}")
    async def update_policy(pid: str, payload: PolicyIn, user=Depends(get_user)):
        prev = await db.compliance_policies.find_one(
            {"id": pid, "workspace_owner": _wo(user)}
        )
        if not prev:
            raise HTTPException(status_code=404, detail="Policy not found")
        new_version = int(prev.get("version", 1)) + 1
        await db.compliance_policies.update_one(
            {"id": pid},
            {"$set": {
                "title": payload.title,
                "body": payload.body,
                "version": new_version,
                "is_template": False,
                "updated_at": _now(),
                "updated_by": user.get("email"),
            }},
        )
        doc = await db.compliance_policies.find_one({"id": pid}, {"_id": 0})
        return doc

    @router.delete("/policies/{pid}")
    async def delete_policy(pid: str, user=Depends(get_user)):
        res = await db.compliance_policies.delete_one(
            {"id": pid, "workspace_owner": _wo(user)}
        )
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Policy not found")
        return {"ok": True, "id": pid}

    return router
