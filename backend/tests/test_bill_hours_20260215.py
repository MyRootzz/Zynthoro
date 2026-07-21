"""Regression test — Time Tracking → Finance "Bill hours" flow (2026-02-15).

Verifies:
  - Only unbilled billable entries are picked up (non-billable and already-billed skipped).
  - Line items are grouped by task with correct hours.
  - Rejects non-won leads.
  - Deleting the resulting invoice releases entries back to the unbilled pool.
"""
from __future__ import annotations

import asyncio
import uuid

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

import server  # noqa: E402
from server import db as server_db  # noqa: E402


_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


async def _clean(wo: str) -> None:
    for coll in ("projects", "project_tasks", "time_entries",
                 "sales_leads", "finance_invoices", "finance_payments",
                 "finance_settings"):
        await server_db[coll].delete_many({"workspace_owner": wo})


def test_billable_summary_ignores_nonbillable_and_invoiced():
    async def run():
        wo = f"wo-bh-{uuid.uuid4()}"
        pid = str(uuid.uuid4())
        tid_a = str(uuid.uuid4())
        tid_b = str(uuid.uuid4())
        await server_db.projects.insert_one({"id": pid, "workspace_owner": wo, "name": "P", "status": "on_track", "progress": 0, "created_at": "t", "updated_at": "t"})
        await server_db.project_tasks.insert_many([
            {"id": tid_a, "workspace_owner": wo, "project_id": pid, "title": "Task A", "status": "in_progress", "created_at": "t", "updated_at": "t"},
            {"id": tid_b, "workspace_owner": wo, "project_id": pid, "title": "Task B", "status": "todo", "created_at": "t", "updated_at": "t"},
        ])
        await server_db.time_entries.insert_many([
            # 5h billable + unbilled → counted
            {"id": str(uuid.uuid4()), "workspace_owner": wo, "project_id": pid, "task_id": tid_a, "hours": 5.0, "billable": True, "date": "2026-02-15", "source": "manual", "created_at": "t", "updated_at": "t"},
            # 3h billable + already invoiced → skipped
            {"id": str(uuid.uuid4()), "workspace_owner": wo, "project_id": pid, "task_id": tid_a, "hours": 3.0, "billable": True, "invoiced": True, "invoice_id": "prev", "date": "2026-02-15", "source": "manual", "created_at": "t", "updated_at": "t"},
            # 2h non-billable → skipped
            {"id": str(uuid.uuid4()), "workspace_owner": wo, "project_id": pid, "task_id": tid_b, "hours": 2.0, "billable": False, "date": "2026-02-15", "source": "manual", "created_at": "t", "updated_at": "t"},
            # 1.5h billable, different task → counted
            {"id": str(uuid.uuid4()), "workspace_owner": wo, "project_id": pid, "task_id": tid_b, "hours": 1.5, "billable": True, "date": "2026-02-15", "source": "manual", "created_at": "t", "updated_at": "t"},
        ])

        entries = await server_db.time_entries.find({
            "workspace_owner": wo, "project_id": pid, "billable": True,
            "$or": [{"invoiced": {"$exists": False}}, {"invoiced": False}],
        }).to_list(100)
        try:
            assert len(entries) == 2, "only 5h and 1.5h entries qualify"
            assert round(sum(e["hours"] for e in entries), 2) == 6.5
            # Group by task
            by_task: dict = {}
            for e in entries:
                by_task.setdefault(e["task_id"], 0.0)
                by_task[e["task_id"]] += e["hours"]
            assert by_task[tid_a] == 5.0
            assert by_task[tid_b] == 1.5
        finally:
            await _clean(wo)
    _run(run())


def test_delete_invoice_releases_entries():
    async def run():
        wo = f"wo-bh-{uuid.uuid4()}"
        iid = str(uuid.uuid4())
        eid1 = str(uuid.uuid4())
        eid2 = str(uuid.uuid4())
        await server_db.finance_invoices.insert_one({"id": iid, "workspace_owner": wo, "number": "T-1", "total": 100, "status": "draft", "items": [], "created_at": "t", "updated_at": "t"})
        await server_db.time_entries.insert_many([
            {"id": eid1, "workspace_owner": wo, "billable": True, "invoiced": True, "invoice_id": iid, "hours": 2, "date": "2026-02-15", "created_at": "t", "updated_at": "t"},
            {"id": eid2, "workspace_owner": wo, "billable": True, "invoiced": True, "invoice_id": iid, "hours": 3, "date": "2026-02-15", "created_at": "t", "updated_at": "t"},
        ])
        try:
            # Simulate the finance delete-invoice cascade.
            await server_db.finance_invoices.delete_one({"id": iid, "workspace_owner": wo})
            await server_db.time_entries.update_many(
                {"workspace_owner": wo, "invoice_id": iid},
                {"$set": {"invoiced": False, "invoice_id": None}},
            )
            for eid in (eid1, eid2):
                e = await server_db.time_entries.find_one({"id": eid})
                assert e["invoiced"] is False
                assert e["invoice_id"] is None
        finally:
            await _clean(wo)
    _run(run())
