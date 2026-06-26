"""Backend tests for Operations & Production module (Zynthoro).

Covers:
 - Recipes CRUD with auto-calculated cost fields
 - Production orders POST/GET (order_no format, cost_estimate from recipe),
   status PATCH and status filter
 - Work orders POST/GET (with quality_checks), filter by production_order_id,
   status PATCH
 - BOMs POST/GET/DELETE with multi-level lines, total_cost_eur, max_level
 - Quality inspections POST/GET with derived pass/fail/overall
 - Lots POST/GET, /lots/{lot_no}/trace, /lots/{lot_no}/recall
 - Costs summary endpoint
 - Plan gating returns 402 for under-tier users; demo/is_unlimited bypass it
 - Jury seed populates recipes(3) / production_orders(3) / QC(2) / lots(3)
"""
import os
import re
import uuid
import requests
import pytest

try:
    from dotenv import load_dotenv
    load_dotenv('/app/backend/.env')
    load_dotenv('/app/frontend/.env')
except Exception:
    pass

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

JURY_EMAIL = "jury@zynthoro.ai"
JURY_PASSWORD = "ZynthoroDemo2026!"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def jury_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": JURY_EMAIL, "password": JURY_PASSWORD},
               timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("stage") == "ok", body
    return s


@pytest.fixture(scope="module")
def starter_session():
    """Fresh signup-only session — no 2FA completed, so /api/auth/me will likely
    401. We use the pre-token / direct login path: signup, verify email via
    dev_verification_token. But to test plan gating we need a logged-in cookie.
    Strategy: sign up, verify, then since first login requires 2FA setup, we
    skip and instead promote nothing — for gating we just call the endpoints
    *without* a session cookie and expect 401, or with a starter-plan cookie.
    Easier: use signup that lands authenticated? Many apps issue cookie post-
    signup. We'll attempt and skip if not possible.
    """
    em = f"TEST_starterop_{uuid.uuid4().hex[:8]}@example.com"
    pw = "StarterPass2026!"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "first_name": "Test", "last_name": "Starter",
        "email": em, "password": pw, "company": "TestCo"
    }, timeout=20)
    if r.status_code not in (200, 201):
        pytest.skip(f"Signup failed: {r.status_code} {r.text}")
    tok = r.json().get("dev_verification_token")
    if tok:
        s.get(f"{BASE_URL}/api/auth/verify-email?token={tok}", timeout=15)
    # Login — likely returns 2fa_setup_required, no cookie set
    lr = s.post(f"{BASE_URL}/api/auth/login",
                json={"email": em, "password": pw}, timeout=15)
    if lr.status_code != 200:
        pytest.skip(f"Login failed for starter: {lr.text}")
    body = lr.json()
    if body.get("stage") != "ok":
        # No authenticated cookie; skip gating tests
        pytest.skip(f"Starter requires 2FA setup ({body.get('stage')}); cannot test plan gating with auth cookie")
    return s


# ---------- Recipes ----------
class TestRecipes:
    def test_seed_has_three_recipes(self, jury_session):
        r = jury_session.get(f"{BASE_URL}/api/operations/recipes", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "recipes" in data and "count" in data
        # Seed has at least 3
        assert data["count"] >= 3
        names = [x["name"] for x in data["recipes"]]
        # Verify seed entries present
        assert any("Sourdough" in n for n in names)

    def test_create_recipe_auto_cost(self, jury_session):
        payload = {
            "name": f"TEST_recipe_{uuid.uuid4().hex[:6]}",
            "yield_qty": 10, "yield_unit": "bars",
            "ingredients": [
                {"name": "Flour", "quantity": 1000, "unit": "g", "cost_per_unit_eur": 0.002},
                {"name": "Sugar", "quantity": 500, "unit": "g", "cost_per_unit_eur": 0.003},
            ],
            "labour_cost_eur": 5.0,
            "overhead_eur": 2.0,
        }
        r = jury_session.post(f"{BASE_URL}/api/operations/recipes", json=payload, timeout=15)
        assert r.status_code == 201, r.text
        body = r.json()
        # material = 1000*0.002 + 500*0.003 = 2.0 + 1.5 = 3.5
        assert body["material_cost_eur"] == 3.5
        # total = 3.5 + 5 + 2 = 10.5
        assert body["cost_total_eur"] == 10.5
        # per unit = 10.5 / 10 = 1.05
        assert body["cost_per_unit_eur"] == 1.05
        assert body["version"] == 1
        assert "id" in body

        # Cleanup
        jury_session.delete(f"{BASE_URL}/api/operations/recipes/{body['id']}", timeout=15)

    def test_patch_bumps_version(self, jury_session):
        # Create
        p = {"name": f"TEST_ver_{uuid.uuid4().hex[:6]}", "yield_qty": 1,
             "ingredients": [], "labour_cost_eur": 1.0, "overhead_eur": 0.0}
        r = jury_session.post(f"{BASE_URL}/api/operations/recipes", json=p, timeout=15)
        assert r.status_code == 201
        rid = r.json()["id"]
        # Patch
        p["labour_cost_eur"] = 2.0
        rp = jury_session.patch(f"{BASE_URL}/api/operations/recipes/{rid}", json=p, timeout=15)
        assert rp.status_code == 200, rp.text
        assert rp.json()["version"] == 2
        # Cleanup
        jury_session.delete(f"{BASE_URL}/api/operations/recipes/{rid}", timeout=15)

    def test_delete_recipe(self, jury_session):
        p = {"name": f"TEST_del_{uuid.uuid4().hex[:6]}", "yield_qty": 1,
             "ingredients": [], "labour_cost_eur": 0.0, "overhead_eur": 0.0}
        r = jury_session.post(f"{BASE_URL}/api/operations/recipes", json=p, timeout=15)
        rid = r.json()["id"]
        d = jury_session.delete(f"{BASE_URL}/api/operations/recipes/{rid}", timeout=15)
        assert d.status_code == 200
        # Re-delete should 404
        d2 = jury_session.delete(f"{BASE_URL}/api/operations/recipes/{rid}", timeout=15)
        assert d2.status_code == 404


# ---------- Production orders ----------
class TestProductionOrders:
    def test_seed_has_three(self, jury_session):
        r = jury_session.get(f"{BASE_URL}/api/operations/production-orders", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 3

    def test_status_filter(self, jury_session):
        r = jury_session.get(f"{BASE_URL}/api/operations/production-orders?status=planned", timeout=15)
        assert r.status_code == 200
        for o in r.json()["orders"]:
            assert o["status"] == "planned"

    def test_create_with_recipe_link(self, jury_session):
        # Create a recipe first
        rec_payload = {
            "name": f"TEST_rec_link_{uuid.uuid4().hex[:6]}",
            "yield_qty": 1, "ingredients": [], "labour_cost_eur": 0.0, "overhead_eur": 0.0,
        }
        # Override: use cost_per_unit calc by adding ingredient cost
        rec_payload["ingredients"] = [{"name": "X", "quantity": 1, "unit": "g", "cost_per_unit_eur": 5.0}]
        # cost_total = 5 + 0 + 0 = 5, per unit (yield=1) = 5
        rr = jury_session.post(f"{BASE_URL}/api/operations/recipes", json=rec_payload, timeout=15)
        assert rr.status_code == 201
        recipe = rr.json()
        assert recipe["cost_per_unit_eur"] == 5.0

        # Create PO linked
        po_payload = {
            "name": f"TEST_po_{uuid.uuid4().hex[:6]}",
            "recipe_id": recipe["id"],
            "quantity": 10, "unit": "units",
        }
        pr = jury_session.post(f"{BASE_URL}/api/operations/production-orders", json=po_payload, timeout=15)
        assert pr.status_code == 201, pr.text
        po = pr.json()
        # order_no format PO-YYYYMMDD-XXXXX (5-char alphanumeric)
        assert re.match(r"^PO-\d{8}-[A-Z0-9]{5}$", po["order_no"]), po["order_no"]
        assert po["status"] == "planned"
        # cost_estimate_eur = 5.0 * 10 = 50.0
        assert po["cost_estimate_eur"] == 50.0

        # Patch status
        sp = jury_session.patch(
            f"{BASE_URL}/api/operations/production-orders/{po['id']}/status",
            json={"status": "in_progress"}, timeout=15)
        assert sp.status_code == 200

        # Cleanup recipe (PO has no DELETE — but it's TEST-prefixed)
        jury_session.delete(f"{BASE_URL}/api/operations/recipes/{recipe['id']}", timeout=15)


# ---------- Work orders ----------
class TestWorkOrders:
    def test_create_and_filter(self, jury_session):
        wo_payload = {
            "production_order_id": "demo-po-id",
            "name": f"TEST_wo_{uuid.uuid4().hex[:6]}",
            "assignee_email": "ops@example.com",
            "steps": [
                {"title": "Mix", "instruction": "mix well",
                 "quality_checks": ["color", "smell"]},
                {"title": "Bake", "instruction": "180C",
                 "quality_checks": ["internal temp"]},
            ],
        }
        r = jury_session.post(f"{BASE_URL}/api/operations/work-orders", json=wo_payload, timeout=15)
        assert r.status_code == 201, r.text
        wo = r.json()
        assert wo["status"] == "planned"
        assert len(wo["steps"]) == 2
        assert wo["steps"][0]["quality_checks"] == ["color", "smell"]

        # Filter
        f = jury_session.get(
            f"{BASE_URL}/api/operations/work-orders?production_order_id=demo-po-id",
            timeout=15)
        assert f.status_code == 200
        ids = [x["id"] for x in f.json()["work_orders"]]
        assert wo["id"] in ids

        # Status update
        sp = jury_session.patch(f"{BASE_URL}/api/operations/work-orders/{wo['id']}/status",
                                 json={"status": "in_progress"}, timeout=15)
        assert sp.status_code == 200


# ---------- BOMs ----------
class TestBOMs:
    def test_create_with_multilevel(self, jury_session):
        payload = {
            "name": f"TEST_bom_{uuid.uuid4().hex[:6]}",
            "finished_sku": "FIN-001",
            "lines": [
                {"sku": "A", "name": "A", "quantity": 2, "unit": "u", "level": 1, "cost_eur": 1.5},
                {"sku": "B", "name": "B", "quantity": 4, "unit": "u", "level": 2, "cost_eur": 0.75},
                {"sku": "C", "name": "C", "quantity": 1, "unit": "u", "level": 3, "cost_eur": 10.0},
            ],
        }
        r = jury_session.post(f"{BASE_URL}/api/operations/boms", json=payload, timeout=15)
        assert r.status_code == 201, r.text
        bom = r.json()
        # total = 2*1.5 + 4*0.75 + 1*10 = 3+3+10 = 16
        assert bom["total_cost_eur"] == 16.0
        assert bom["max_level"] == 3

        # List
        lr = jury_session.get(f"{BASE_URL}/api/operations/boms", timeout=15)
        assert lr.status_code == 200
        assert any(b["id"] == bom["id"] for b in lr.json()["boms"])

        # Delete
        dr = jury_session.delete(f"{BASE_URL}/api/operations/boms/{bom['id']}", timeout=15)
        assert dr.status_code == 200


# ---------- Quality inspections ----------
class TestQuality:
    def test_seed_has_two(self, jury_session):
        r = jury_session.get(f"{BASE_URL}/api/operations/quality-inspections", timeout=15)
        assert r.status_code == 200
        assert r.json()["count"] >= 2

    def test_create_derived_overall(self, jury_session):
        # All pass → overall=pass
        payload = {
            "production_order_id": "demo",
            "checklist": ["a", "b"],
            "results": ["pass", "pass"],
        }
        r = jury_session.post(f"{BASE_URL}/api/operations/quality-inspections", json=payload, timeout=15)
        assert r.status_code == 201
        body = r.json()
        assert body["pass_count"] == 2
        assert body["fail_count"] == 0
        assert body["overall"] == "pass"

        # One fail → overall=fail
        payload["results"] = ["pass", "fail"]
        r2 = jury_session.post(f"{BASE_URL}/api/operations/quality-inspections", json=payload, timeout=15)
        assert r2.status_code == 201
        b2 = r2.json()
        assert b2["pass_count"] == 1
        assert b2["fail_count"] == 1
        assert b2["overall"] == "fail"


# ---------- Lots / traceability ----------
class TestLots:
    def test_seed_has_three(self, jury_session):
        r = jury_session.get(f"{BASE_URL}/api/operations/lots", timeout=15)
        assert r.status_code == 200
        assert r.json()["count"] >= 3

    def test_create_lot_and_trace(self, jury_session):
        # First create an upstream lot
        up = {"production_order_id": "demo", "expiry_date": "2026-12-31",
              "raw_material_lots": []}
        ur = jury_session.post(f"{BASE_URL}/api/operations/lots", json=up, timeout=15)
        assert ur.status_code == 201
        upstream_lot_no = ur.json()["lot_no"]
        assert re.match(r"^LOT-\d{6}-[A-Z0-9]{6}$", upstream_lot_no), upstream_lot_no

        # Create downstream lot referencing upstream
        down = {"production_order_id": "demo", "expiry_date": "2026-12-31",
                "raw_material_lots": [upstream_lot_no]}
        dr = jury_session.post(f"{BASE_URL}/api/operations/lots", json=down, timeout=15)
        assert dr.status_code == 201
        down_lot_no = dr.json()["lot_no"]

        # Trace
        tr = jury_session.get(f"{BASE_URL}/api/operations/lots/{down_lot_no}/trace", timeout=15)
        assert tr.status_code == 200, tr.text
        tb = tr.json()
        assert tb["lot"]["lot_no"] == down_lot_no
        assert len(tb["upstream_lots"]) == 1
        assert tb["upstream_lots"][0]["lot_no"] == upstream_lot_no

    def test_recall_lot(self, jury_session):
        # Create lot
        c = jury_session.post(f"{BASE_URL}/api/operations/lots",
                              json={"production_order_id": "demo",
                                    "raw_material_lots": []}, timeout=15)
        lot_no = c.json()["lot_no"]
        # Recall
        rr = jury_session.post(f"{BASE_URL}/api/operations/lots/{lot_no}/recall", timeout=15)
        assert rr.status_code == 200
        assert rr.json()["status"] == "recalled"
        # Verify via list
        lr = jury_session.get(f"{BASE_URL}/api/operations/lots", timeout=15)
        match = next((x for x in lr.json()["lots"] if x["lot_no"] == lot_no), None)
        assert match is not None
        assert match["status"] == "recalled"


# ---------- Cost summary ----------
class TestCostSummary:
    def test_summary_fields(self, jury_session):
        r = jury_session.get(f"{BASE_URL}/api/operations/costs/summary", timeout=15)
        assert r.status_code == 200, r.text
        s = r.json()
        required = {"recipe_count", "production_order_count", "average_unit_cost_eur",
                    "estimated_production_cost_eur", "actual_production_cost_eur",
                    "variance_eur"}
        assert required.issubset(s.keys())
        assert s["recipe_count"] >= 3
        assert s["production_order_count"] >= 3
        assert s["average_unit_cost_eur"] > 0
        assert s["estimated_production_cost_eur"] > 0


# ---------- Plan gating ----------
class TestPlanGating:
    def test_unauth_returns_401(self):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/operations/recipes", timeout=15)
        assert r.status_code in (401, 403)

    def test_demo_bypasses_all_tiers(self, jury_session):
        # Demo user accesses BOM (agency) and Lots (enterprise) without 402
        r_bom = jury_session.get(f"{BASE_URL}/api/operations/boms", timeout=15)
        assert r_bom.status_code == 200, r_bom.text
        r_lots = jury_session.get(f"{BASE_URL}/api/operations/lots", timeout=15)
        assert r_lots.status_code == 200
        r_qc = jury_session.get(f"{BASE_URL}/api/operations/quality-inspections", timeout=15)
        assert r_qc.status_code == 200

    def test_starter_gets_402_for_higher_tiers(self, starter_session):
        # BOM is agency-tier → 402 for starter
        r_bom = starter_session.get(f"{BASE_URL}/api/operations/boms", timeout=15)
        assert r_bom.status_code == 402, f"Expected 402, got {r_bom.status_code}: {r_bom.text}"
        # Lots is enterprise-tier → 402
        r_lots = starter_session.get(f"{BASE_URL}/api/operations/lots", timeout=15)
        assert r_lots.status_code == 402
