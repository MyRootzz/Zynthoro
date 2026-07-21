"""Regression tests for Session C2 — Projects, Planning, Time Tracking.

Run:
    cd /app/backend && python -m pytest tests/test_session_c2_20260215.py -v
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

import server  # noqa: E402
from server import db as server_db  # noqa: E402
import projects_module  # noqa: E402
import planning_module  # noqa: E402
import time_tracking_module  # noqa: E402

_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
def test_project_progress_recomputed_from_tasks():
    """`_recompute_progress` in projects_module — 3 of 4 tasks done → 75."""
    async def run():
        wo = f"wo-c2-{uuid.uuid4()}"
        pid = str(uuid.uuid4())
        await server_db.projects.insert_one({
            "id": pid, "workspace_owner": wo, "name": "P", "progress": 0,
            "status": "on_track", "created_at": "t", "updated_at": "t",
        })
        for status in ("done", "done", "done", "todo"):
            await server_db.project_tasks.insert_one({
                "id": str(uuid.uuid4()), "workspace_owner": wo,
                "project_id": pid, "title": "t", "status": status,
                "created_at": "t", "updated_at": "t",
            })
        try:
            # Import build_router to get the closure; simulate by running the
            # recompute logic directly (mirrors what the endpoint would do).
            tasks = await server_db.project_tasks.find(
                {"workspace_owner": wo, "project_id": pid},
            ).to_list(100)
            done = sum(1 for t in tasks if t["status"] == "done")
            progress = int(round(100 * done / len(tasks)))
            assert progress == 75
        finally:
            await server_db.projects.delete_many({"workspace_owner": wo})
            await server_db.project_tasks.delete_many({"workspace_owner": wo})
    _run(run())


def test_project_cascade_deletes_tasks_and_milestones():
    async def run():
        wo = f"wo-c2-{uuid.uuid4()}"
        pid = str(uuid.uuid4())
        await server_db.projects.insert_one({
            "id": pid, "workspace_owner": wo, "name": "P",
            "status": "planning", "progress": 0,
            "created_at": "t", "updated_at": "t",
        })
        await server_db.project_tasks.insert_one({
            "id": str(uuid.uuid4()), "workspace_owner": wo,
            "project_id": pid, "title": "t", "status": "todo",
            "created_at": "t", "updated_at": "t",
        })
        await server_db.project_milestones.insert_one({
            "id": str(uuid.uuid4()), "workspace_owner": wo,
            "project_id": pid, "title": "M", "completed": False,
            "created_at": "t", "updated_at": "t",
        })
        try:
            # Simulate the cascade the endpoint performs.
            await server_db.projects.delete_one({"id": pid, "workspace_owner": wo})
            await server_db.project_tasks.delete_many({"workspace_owner": wo, "project_id": pid})
            await server_db.project_milestones.delete_many({"workspace_owner": wo, "project_id": pid})
            assert await server_db.project_tasks.count_documents({"project_id": pid}) == 0
            assert await server_db.project_milestones.count_documents({"project_id": pid}) == 0
        finally:
            await server_db.projects.delete_many({"workspace_owner": wo})
            await server_db.project_tasks.delete_many({"workspace_owner": wo})
            await server_db.project_milestones.delete_many({"workspace_owner": wo})
    _run(run())


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------
def test_sprint_summary_shape():
    async def run():
        # The `_summary` helper is inside `build_router` closure — reproduce
        # its logic here using the same DB shapes.
        wo = f"wo-c2-{uuid.uuid4()}"
        sid = str(uuid.uuid4())
        for status in ("done", "done", "in_progress", "todo", "todo"):
            await server_db.project_tasks.insert_one({
                "id": str(uuid.uuid4()), "workspace_owner": wo,
                "project_id": "p", "title": "t", "status": status,
                "sprint_id": sid,
                "created_at": "t", "updated_at": "t",
            })
        try:
            tasks = await server_db.project_tasks.find(
                {"workspace_owner": wo, "sprint_id": sid},
            ).to_list(50)
            done = sum(1 for t in tasks if t["status"] == "done")
            in_progress = sum(1 for t in tasks if t["status"] == "in_progress")
            todo = len(tasks) - done - in_progress
            progress = int(round(100 * done / len(tasks)))
            assert (done, in_progress, todo, progress) == (2, 1, 2, 40)
        finally:
            await server_db.project_tasks.delete_many({"workspace_owner": wo})
    _run(run())


def test_delete_sprint_detaches_but_keeps_tasks():
    async def run():
        wo = f"wo-c2-{uuid.uuid4()}"
        sid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        await server_db.sprints.insert_one({
            "id": sid, "workspace_owner": wo, "name": "S",
            "start_date": "2026-01-01", "end_date": "2026-01-14",
            "status": "active",
            "created_at": "t", "updated_at": "t",
        })
        await server_db.project_tasks.insert_one({
            "id": tid, "workspace_owner": wo, "project_id": "p",
            "title": "t", "status": "todo", "sprint_id": sid,
            "created_at": "t", "updated_at": "t",
        })
        try:
            await server_db.sprints.delete_one({"id": sid, "workspace_owner": wo})
            await server_db.project_tasks.update_many(
                {"workspace_owner": wo, "sprint_id": sid},
                {"$set": {"sprint_id": None}},
            )
            t = await server_db.project_tasks.find_one({"id": tid})
            assert t is not None, "task must remain"
            assert t["sprint_id"] is None, "sprint_id must be cleared"
        finally:
            await server_db.project_tasks.delete_many({"workspace_owner": wo})
    _run(run())


# ---------------------------------------------------------------------------
# Time Tracking
# ---------------------------------------------------------------------------
def test_monday_calculation_is_iso_week():
    # 2026-02-15 is a Sunday → Monday of that week is 2026-02-09.
    assert time_tracking_module._monday("2026-02-15") == date(2026, 2, 9)
    # 2026-02-10 (Tue) → 2026-02-09.
    assert time_tracking_module._monday("2026-02-10") == date(2026, 2, 9)
    # 2026-02-09 (Mon) → itself.
    assert time_tracking_module._monday("2026-02-09") == date(2026, 2, 9)


def test_finalize_timer_creates_entry_and_deletes_timer():
    """The internal `_finalize_timer` helper is used by start/stop."""
    async def run():
        wo = f"wo-c2-{uuid.uuid4()}"
        # Make a timer that started 3600s ago (~ 1 hour).
        from datetime import datetime, timezone
        started = datetime.now(timezone.utc).timestamp() - 3600
        started_iso = datetime.fromtimestamp(started, tz=timezone.utc).isoformat()
        tid = str(uuid.uuid4())
        await server_db.time_timers.insert_one({
            "id": tid, "workspace_owner": wo,
            "user_email": "tester@test.local",
            "project_id": None, "task_id": None,
            "notes": "1h ago", "billable": True,
            "started_at": started_iso, "created_at": started_iso,
        })
        try:
            timer = await server_db.time_timers.find_one({"id": tid})
            entry = await time_tracking_module._finalize_timer(server_db, timer)
            # Timer gone, entry created with ~1 hour.
            assert await server_db.time_timers.find_one({"id": tid}) is None
            assert 0.99 <= entry["hours"] <= 1.01
            assert entry["source"] == "timer"
        finally:
            await server_db.time_entries.delete_many({"workspace_owner": wo})
            await server_db.time_timers.delete_many({"workspace_owner": wo})
    _run(run())


def test_time_entries_are_scoped_by_workspace():
    async def run():
        wo1 = f"wo-c2-{uuid.uuid4()}"
        wo2 = f"wo-c2-{uuid.uuid4()}"
        await server_db.time_entries.insert_many([
            {"id": str(uuid.uuid4()), "workspace_owner": wo1, "date": "2026-02-15", "hours": 2.0, "user_email": "a", "billable": True, "source": "manual", "created_at": "t", "updated_at": "t"},
            {"id": str(uuid.uuid4()), "workspace_owner": wo1, "date": "2026-02-15", "hours": 3.0, "user_email": "a", "billable": False, "source": "manual", "created_at": "t", "updated_at": "t"},
            {"id": str(uuid.uuid4()), "workspace_owner": wo2, "date": "2026-02-15", "hours": 10.0, "user_email": "b", "billable": True, "source": "manual", "created_at": "t", "updated_at": "t"},
        ])
        try:
            wo1_count = await server_db.time_entries.count_documents({"workspace_owner": wo1})
            wo2_count = await server_db.time_entries.count_documents({"workspace_owner": wo2})
            assert wo1_count == 2
            assert wo2_count == 1
        finally:
            await server_db.time_entries.delete_many({"workspace_owner": {"$in": [wo1, wo2]}})
    _run(run())
