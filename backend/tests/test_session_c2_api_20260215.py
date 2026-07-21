"""Session C2 — Projects, Planning, Time Tracking API tests (HTTP)."""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
FOUNDER_EMAIL = "regie@myrootzz.com"
FOUNDER_PASSWORD = "Zynthoro2026!"
JURY_EMAIL = "jury@zynthoro.ai"
JURY_PASSWORD = "ZynthoroDemo2026!"


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    assert j.get("stage") == "ok", f"unexpected stage: {j}"
    s.headers.update({"Authorization": f"Bearer {j['access_token']}"})
    return s


@pytest.fixture(scope="module")
def founder():
    return _login(FOUNDER_EMAIL, FOUNDER_PASSWORD)


@pytest.fixture(scope="module")
def jury():
    return _login(JURY_EMAIL, JURY_PASSWORD)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
class TestProjects:
    def test_list_projects_with_totals(self, founder):
        r = founder.get(f"{BASE_URL}/api/projects", timeout=15)
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        assert "projects" in j and "totals" in j
        totals = j["totals"]
        for k in ("total", "on_track", "at_risk", "completed"):
            assert k in totals

    def test_project_lifecycle(self, founder):
        # Create
        name = f"TEST_C2_{uuid.uuid4().hex[:6]}"
        payload = {"name": name, "status": "on_track", "domain": "QA",
                   "start_date": "2026-02-01", "end_date": "2026-03-01",
                   "colour": "#4f46e5"}
        r = founder.post(f"{BASE_URL}/api/projects", json=payload, timeout=15)
        assert r.status_code in (200, 201), r.text[:300]
        proj = r.json()
        pid = proj["id"]
        try:
            # Get detail
            d = founder.get(f"{BASE_URL}/api/projects/{pid}", timeout=15).json()
            assert d["project"]["name"] == name
            assert d["tasks"] == [] and d["milestones"] == []

            # Add task
            t1 = founder.post(f"{BASE_URL}/api/projects/tasks", json={
                "project_id": pid, "title": "Task A", "status": "todo",
            }, timeout=15)
            assert t1.status_code in (200, 201), t1.text[:300]
            task = t1.json()
            tid = task["id"]

            # Mark done → progress should be 100
            r2 = founder.put(f"{BASE_URL}/api/projects/tasks/{tid}/status",
                             json={"status": "done"}, timeout=15)
            assert r2.status_code == 200
            d2 = founder.get(f"{BASE_URL}/api/projects/{pid}", timeout=15).json()
            assert d2["project"]["progress"] == 100
            # completed_at populated
            done_task = [t for t in d2["tasks"] if t["id"] == tid][0]
            assert done_task.get("completed_at")

            # Milestone
            m = founder.post(f"{BASE_URL}/api/projects/milestones", json={
                "project_id": pid, "title": "MS1",
            }, timeout=15)
            assert m.status_code in (200, 201)
            mid = m.json()["id"]
            tog = founder.put(f"{BASE_URL}/api/projects/milestones/{mid}/toggle",
                              timeout=15)
            assert tog.status_code == 200
            assert tog.json()["completed"] is True

            # Update (PUT requires full ProjectIn — name required)
            up = founder.put(f"{BASE_URL}/api/projects/{pid}",
                             json={"name": name, "status": "completed"}, timeout=15)
            assert up.status_code == 200, up.text[:200]
        finally:
            # Delete → cascade
            r_del = founder.delete(f"{BASE_URL}/api/projects/{pid}", timeout=15)
            assert r_del.status_code in (200, 204)
            check = founder.get(f"{BASE_URL}/api/projects/{pid}", timeout=15)
            assert check.status_code == 404

    def test_list_has_task_counts(self, founder):
        r = founder.get(f"{BASE_URL}/api/projects", timeout=15).json()
        for p in r["projects"]:
            assert "task_counts" in p


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------
class TestPlanning:
    def test_sprint_flow(self, founder):
        # Create project + task
        p = founder.post(f"{BASE_URL}/api/projects", json={
            "name": f"TEST_C2_SPR_{uuid.uuid4().hex[:5]}", "status": "on_track",
        }, timeout=15).json()
        pid = p["id"]
        t = founder.post(f"{BASE_URL}/api/projects/tasks", json={
            "project_id": pid, "title": "Sprint task", "status": "todo",
        }, timeout=15).json()
        tid = t["id"]

        # Sprint
        s = founder.post(f"{BASE_URL}/api/planning/sprints", json={
            "name": f"TEST_C2 Sprint {uuid.uuid4().hex[:4]}",
            "start_date": "2026-02-09", "end_date": "2026-02-23",
            "status": "active", "goal": "Test goal", "capacity_hours": 40,
        }, timeout=15)
        assert s.status_code in (200, 201), s.text[:300]
        sid = s.json()["id"]
        try:
            # available-tasks includes our task
            avail = founder.get(f"{BASE_URL}/api/planning/available-tasks", timeout=15).json()
            tasks_list = avail.get("tasks", avail if isinstance(avail, list) else [])
            ids = [x["id"] for x in tasks_list]
            assert tid in ids, f"task {tid} not in available tasks; got {ids[:5]}"
            # project_name enrichment
            picked = [x for x in tasks_list if x["id"] == tid][0]
            assert "project_name" in picked

            # Link task
            link = founder.post(f"{BASE_URL}/api/planning/sprints/{sid}/tasks",
                                json={"task_id": tid}, timeout=15)
            assert link.status_code in (200, 201), link.text[:300]

            # Sprint detail enriched
            det = founder.get(f"{BASE_URL}/api/planning/sprints/{sid}", timeout=15).json()
            assert det["sprint"]["id"] == sid
            assert any(x["id"] == tid for x in det["tasks"])
            row = [x for x in det["tasks"] if x["id"] == tid][0]
            assert "project_name" in row and "project_color" in row

            # List summary
            lst = founder.get(f"{BASE_URL}/api/planning/sprints", timeout=15).json()
            found = [x for x in lst.get("sprints", lst) if x["id"] == sid]
            assert found and "summary" in found[0]
            summ = found[0]["summary"]
            assert summ["task_count"] == 1

            # After marking task done, summary.done increments
            founder.put(f"{BASE_URL}/api/projects/tasks/{tid}/status",
                        json={"status": "done"}, timeout=15)
            lst2 = founder.get(f"{BASE_URL}/api/planning/sprints", timeout=15).json()
            f2 = [x for x in lst2.get("sprints", lst2) if x["id"] == sid][0]
            assert f2["summary"]["done"] == 1
            assert f2["summary"]["progress"] == 100

            # Unlink
            un = founder.delete(f"{BASE_URL}/api/planning/sprints/{sid}/tasks/{tid}", timeout=15)
            assert un.status_code in (200, 204)
            det2 = founder.get(f"{BASE_URL}/api/planning/sprints/{sid}", timeout=15).json()
            assert not any(x["id"] == tid for x in det2["tasks"])
        finally:
            # Delete sprint (detaches remaining tasks)
            founder.delete(f"{BASE_URL}/api/planning/sprints/{sid}", timeout=15)
            founder.delete(f"{BASE_URL}/api/projects/{pid}", timeout=15)


# ---------------------------------------------------------------------------
# Time tracking
# ---------------------------------------------------------------------------
class TestTimeTracking:
    def test_timer_start_stop(self, founder):
        # ensure no timer running
        founder.post(f"{BASE_URL}/api/time-tracking/timer/stop", json={}, timeout=15)

        r = founder.post(f"{BASE_URL}/api/time-tracking/timer/start", json={
            "notes": "TEST_C2 timer", "billable": True,
        }, timeout=15)
        assert r.status_code in (200, 201), r.text[:300]

        # GET timer returns running
        g = founder.get(f"{BASE_URL}/api/time-tracking/timer", timeout=15).json()
        assert g and g.get("timer") and "elapsed_seconds" in g["timer"]

        # Starting again auto-commits
        r2 = founder.post(f"{BASE_URL}/api/time-tracking/timer/start", json={
            "notes": "TEST_C2 timer 2",
        }, timeout=15).json()
        assert "auto_committed" in r2

        # Stop
        st = founder.post(f"{BASE_URL}/api/time-tracking/timer/stop", json={}, timeout=15)
        assert st.status_code == 200, st.text[:200]
        j = st.json()
        entry = j.get("entry", j)
        assert entry.get("source") == "timer"

        # GET timer returns null-ish
        n = founder.get(f"{BASE_URL}/api/time-tracking/timer", timeout=15).json()
        assert n.get("timer") in (None, {})

    def test_manual_entry_and_totals(self, founder):
        r = founder.post(f"{BASE_URL}/api/time-tracking/entries", json={
            "date": "2026-02-10", "hours": 2.5, "billable": True,
            "notes": "TEST_C2 manual",
        }, timeout=15)
        assert r.status_code in (200, 201), r.text[:300]
        entry = r.json()
        assert entry["source"] == "manual"
        eid = entry["id"]

        lst = founder.get(f"{BASE_URL}/api/time-tracking/entries", timeout=15).json()
        assert "entries" in lst and "totals" in lst
        for k in ("hours", "billable_hours", "count"):
            assert k in lst["totals"]

        # hours > 0 required
        bad = founder.post(f"{BASE_URL}/api/time-tracking/entries", json={
            "date": "2026-02-10", "hours": 0,
        }, timeout=15)
        assert bad.status_code >= 400

        # Cleanup best-effort
        founder.delete(f"{BASE_URL}/api/time-tracking/entries/{eid}", timeout=15)

    def test_timesheet_week_start_monday(self, founder):
        r = founder.get(f"{BASE_URL}/api/time-tracking/timesheet",
                        params={"week_of": "2026-02-15"}, timeout=15)
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        assert j.get("week_of") == "2026-02-09"
        assert "rows" in j and "days" in j
        assert "grand_total" in j

    def test_csv_export(self, founder):
        r = founder.get(f"{BASE_URL}/api/time-tracking/entries/export.csv", timeout=20)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        header = r.text.splitlines()[0]
        assert header == "date,user_email,project,task,hours,billable,notes,source", header


# ---------------------------------------------------------------------------
# Jury seeded workspace
# ---------------------------------------------------------------------------
class TestJurySeed:
    def test_jury_projects_seed(self, jury):
        r = jury.get(f"{BASE_URL}/api/projects", timeout=15).json()
        totals = r["totals"]
        assert totals["total"] >= 5, totals
        assert totals["on_track"] >= 3
        assert totals["at_risk"] >= 1
        assert totals["completed"] >= 1

    def test_jury_sprint_and_time(self, jury):
        sprints = jury.get(f"{BASE_URL}/api/planning/sprints", timeout=15).json()
        lst = sprints.get("sprints", sprints)
        assert any("Sprint 12" in (s.get("name") or "") for s in lst), \
            [s.get("name") for s in lst]

        entries = jury.get(f"{BASE_URL}/api/time-tracking/entries", timeout=15).json()
        assert entries["totals"]["hours"] >= 20, entries["totals"]
