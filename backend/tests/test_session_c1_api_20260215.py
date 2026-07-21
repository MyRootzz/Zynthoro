"""Session C1 — Finance & Sales API integration tests (over HTTP)."""
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


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    assert j.get("stage") == "ok", f"unexpected stage: {j}"
    tok = j["access_token"]
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def founder():
    return _login(FOUNDER_EMAIL, FOUNDER_PASSWORD)


@pytest.fixture(scope="module")
def other_user():
    """Second workspace user to test isolation."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"c1iso_{uuid.uuid4().hex[:8]}@test.local"
    password = "TestPass1234!!"
    r = s.post(
        f"{BASE_URL}/api/auth/signup",
        json={
            "first_name": "Iso", "last_name": "User",
            "email": email, "password": password, "company": "Iso Co",
        }, timeout=30,
    )
    if r.status_code not in (200, 201):
        pytest.skip(f"signup failed: {r.status_code} {r.text[:200]}")
    j = r.json()
    tok = j.get("dev_verification_token") or j.get("verification_token")
    if tok:
        s.get(f"{BASE_URL}/api/auth/verify-email?token={tok}", timeout=15)
    # Try login — this user has 2FA setup_required, so we cannot easily get an access token.
    lr = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    if lr.status_code == 200 and lr.json().get("stage") == "ok":
        s.headers.update({"Authorization": f"Bearer {lr.json()['access_token']}"})
        return s
    pytest.skip("second user requires 2FA setup — isolation test done via DB check separately")


# -------------------------------------------------------------------------
# Finance
# -------------------------------------------------------------------------
class TestFinanceSettings:
    def test_get_settings(self, founder):
        r = founder.get(f"{BASE_URL}/api/finance/settings", timeout=15)
        assert r.status_code == 200
        s = r.json()["settings"]
        assert "invoice_prefix" in s
        assert "default_payment_terms" in s
        assert "default_bank_details" in s

    def test_update_settings(self, founder):
        payload = {
            "company_name": "Zynthoro Test BV",
            "company_address": "Amsterdam, NL",
            "company_vat": "NL0001B01",
            "invoice_prefix": "INV-",
            "default_payment_terms": "Payment due within 14 days.",
            "default_bank_details": "IBAN NL01 BANK 1234 5678 90",
            "currency": "EUR",
        }
        r = founder.put(f"{BASE_URL}/api/finance/settings", json=payload, timeout=15)
        assert r.status_code == 200
        s = r.json()["settings"]
        assert s["company_name"] == "Zynthoro Test BV"
        assert s["default_bank_details"].startswith("IBAN NL01")
        # Verify persistence
        r2 = founder.get(f"{BASE_URL}/api/finance/settings", timeout=15)
        assert r2.json()["settings"]["default_payment_terms"] == "Payment due within 14 days."


@pytest.fixture(scope="module")
def created_invoice(founder):
    today = date.today().isoformat()
    due = (date.today() + timedelta(days=14)).isoformat()
    payload = {
        "client_name": "TEST_Acme BV",
        "client_email": "delivered@resend.dev",
        "client_address": "Herengracht 1\n1015 BA Amsterdam",
        "issue_date": today,
        "due_date": due,
        "currency": "EUR",
        "items": [
            {"description": "Consulting", "quantity": 10, "unit_price": 150, "tax_rate": 21},
            {"description": "AI onboarding", "quantity": 1, "unit_price": 500, "tax_rate": 21},
        ],
        "payment_terms": "Payment due within 14 days.",
        "bank_details": "IBAN NL01 BANK 1234 5678 90",
        "notes": "Thanks for your business.",
    }
    r = founder.post(f"{BASE_URL}/api/finance/invoices", json=payload, timeout=20)
    assert r.status_code == 201, r.text[:300]
    inv = r.json()
    yield inv
    # cleanup
    founder.delete(f"{BASE_URL}/api/finance/invoices/{inv['id']}", timeout=15)


class TestFinanceInvoices:
    def test_create_totals(self, created_invoice):
        assert created_invoice["subtotal"] == 2000.0
        assert created_invoice["tax_total"] == 420.0
        assert created_invoice["total"] == 2420.0
        assert created_invoice["status"] == "draft"
        num = created_invoice["number"]
        assert num.startswith("INV-") and f"-{date.today().year}-" in num, f"bad num format: {num}"
        assert len(num.split("-")[-1]) == 4

    def test_list_invoices_totals(self, founder, created_invoice):
        r = founder.get(f"{BASE_URL}/api/finance/invoices", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "invoices" in j and "totals" in j
        for k in ("total_eur", "paid_eur", "outstanding_eur", "draft_count", "paid_count"):
            assert k in j["totals"], f"missing totals key {k}"
        ids = [i["id"] for i in j["invoices"]]
        assert created_invoice["id"] in ids

    def test_get_invoice_with_payments(self, founder, created_invoice):
        r = founder.get(f"{BASE_URL}/api/finance/invoices/{created_invoice['id']}", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j["invoice"]["id"] == created_invoice["id"]
        assert isinstance(j["payments"], list)

    def test_update_draft_recomputes(self, founder, created_invoice):
        payload = {
            "client_name": "TEST_Acme BV",
            "client_email": "delivered@resend.dev",
            "issue_date": created_invoice["issue_date"],
            "due_date": created_invoice["due_date"],
            "currency": "EUR",
            "items": [
                {"description": "Only one", "quantity": 2, "unit_price": 100, "tax_rate": 21},
            ],
        }
        r = founder.put(f"{BASE_URL}/api/finance/invoices/{created_invoice['id']}", json=payload, timeout=15)
        assert r.status_code == 200, r.text[:200]
        inv = r.json()
        assert inv["subtotal"] == 200.0
        assert inv["tax_total"] == 42.0
        assert inv["total"] == 242.0
        # restore items to full 2420 for downstream tests
        restore = {
            "client_name": "TEST_Acme BV",
            "client_email": "delivered@resend.dev",
            "issue_date": created_invoice["issue_date"],
            "due_date": created_invoice["due_date"],
            "currency": "EUR",
            "items": [
                {"description": "Consulting", "quantity": 10, "unit_price": 150, "tax_rate": 21},
                {"description": "AI onboarding", "quantity": 1, "unit_price": 500, "tax_rate": 21},
            ],
        }
        r2 = founder.put(f"{BASE_URL}/api/finance/invoices/{created_invoice['id']}", json=restore, timeout=15)
        assert r2.status_code == 200 and r2.json()["total"] == 2420.0

    def test_pdf_generation(self, founder, created_invoice):
        r = founder.get(f"{BASE_URL}/api/finance/invoices/{created_invoice['id']}/pdf", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("Content-Type", "").startswith("application/pdf")
        content = r.content
        assert content.startswith(b"%PDF-"), "must be valid PDF"
        assert len(content) > 1000

    def test_send_email(self, founder, created_invoice):
        r = founder.post(f"{BASE_URL}/api/finance/invoices/{created_invoice['id']}/send-email", timeout=60)
        # If RESEND is configured we get email_sent True + email_id. Otherwise skip.
        if r.status_code != 200:
            pytest.skip(f"send-email returned {r.status_code}: {r.text[:200]}")
        j = r.json()
        # Some impls return {invoice, email_sent, email_id} — accept both
        assert j.get("email_sent") or j.get("email_id"), f"unexpected send-email payload: {j}"
        # Verify status now 'sent'
        got = founder.get(f"{BASE_URL}/api/finance/invoices/{created_invoice['id']}", timeout=15).json()
        assert got["invoice"]["status"] in ("sent", "overdue", "paid")
        assert got["invoice"].get("sent_at")

    def test_partial_and_full_payment(self, founder, created_invoice):
        iid = created_invoice["id"]
        # Partial payment
        r1 = founder.post(
            f"{BASE_URL}/api/finance/invoices/{iid}/payments",
            json={"amount": 1000.0, "method": "bank", "date": date.today().isoformat(), "notes": "partial"},
            timeout=15,
        )
        assert r1.status_code in (200, 201), r1.text[:200]
        inv1 = founder.get(f"{BASE_URL}/api/finance/invoices/{iid}", timeout=15).json()["invoice"]
        assert inv1["status"] != "paid", "should not be paid after partial"

        # Second payment covering the rest
        r2 = founder.post(
            f"{BASE_URL}/api/finance/invoices/{iid}/payments",
            json={"amount": 1420.0, "method": "bank", "date": date.today().isoformat()},
            timeout=15,
        )
        assert r2.status_code in (200, 201), r2.text[:200]
        inv2 = founder.get(f"{BASE_URL}/api/finance/invoices/{iid}", timeout=15).json()["invoice"]
        assert inv2["status"] == "paid"
        assert inv2.get("paid_at")

    def test_edit_paid_returns_400(self, founder, created_invoice):
        iid = created_invoice["id"]
        # ensure it's paid from previous test
        payload = {
            "client_name": "Should Fail",
            "client_email": "fail@x.com",
            "issue_date": created_invoice["issue_date"],
            "due_date": created_invoice["due_date"],
            "currency": "EUR",
            "items": [{"description": "x", "quantity": 1, "unit_price": 1, "tax_rate": 0}],
        }
        r = founder.put(f"{BASE_URL}/api/finance/invoices/{iid}", json=payload, timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"

    def test_delete_payment_reverts_status(self, founder, created_invoice):
        iid = created_invoice["id"]
        got = founder.get(f"{BASE_URL}/api/finance/invoices/{iid}", timeout=15).json()
        payments = got["payments"]
        if not payments:
            pytest.skip("no payments")
        pid = payments[0]["id"]
        r = founder.delete(f"{BASE_URL}/api/finance/payments/{pid}", timeout=15)
        assert r.status_code in (200, 204)
        inv = founder.get(f"{BASE_URL}/api/finance/invoices/{iid}", timeout=15).json()["invoice"]
        assert inv["status"] != "paid", "removing a payment should revert status"


class TestFinanceMarkPaidStandalone:
    """Separate invoice to test mark-paid endpoint."""

    def test_mark_paid(self, founder):
        today = date.today().isoformat()
        payload = {
            "client_name": "TEST_MarkPaid",
            "client_email": "mp@example.com",
            "issue_date": today,
            "currency": "EUR",
            "items": [{"description": "x", "quantity": 1, "unit_price": 100, "tax_rate": 0}],
        }
        r = founder.post(f"{BASE_URL}/api/finance/invoices", json=payload, timeout=15)
        assert r.status_code == 201
        iid = r.json()["id"]
        try:
            mp = founder.post(f"{BASE_URL}/api/finance/invoices/{iid}/mark-paid", timeout=15)
            assert mp.status_code in (200, 201), mp.text[:200]
            inv = founder.get(f"{BASE_URL}/api/finance/invoices/{iid}", timeout=15).json()
            assert inv["invoice"]["status"] == "paid"
            assert inv["invoice"].get("paid_at")
            assert len(inv["payments"]) >= 1
        finally:
            founder.delete(f"{BASE_URL}/api/finance/invoices/{iid}", timeout=15)


class TestFinanceDeleteCascadesPayments:
    def test_delete_cascades(self, founder):
        payload = {
            "client_name": "TEST_Cascade",
            "issue_date": date.today().isoformat(),
            "currency": "EUR",
            "items": [{"description": "x", "quantity": 1, "unit_price": 50, "tax_rate": 0}],
        }
        r = founder.post(f"{BASE_URL}/api/finance/invoices", json=payload, timeout=15)
        iid = r.json()["id"]
        founder.post(
            f"{BASE_URL}/api/finance/invoices/{iid}/payments",
            json={"amount": 50, "method": "cash", "date": date.today().isoformat()}, timeout=15,
        )
        d = founder.delete(f"{BASE_URL}/api/finance/invoices/{iid}", timeout=15)
        assert d.status_code == 200
        # get should 404
        g = founder.get(f"{BASE_URL}/api/finance/invoices/{iid}", timeout=15)
        assert g.status_code == 404


# -------------------------------------------------------------------------
# Sales
# -------------------------------------------------------------------------
@pytest.fixture(scope="module")
def created_lead(founder):
    payload = {
        "name": "TEST_John Smith",
        "company": "Acme",
        "email": "js@acme.com",
        "phone": "+31 20 1234567",
        "source": "referral",
        "stage": "new",
        "value": 15000,
        "currency": "EUR",
        "expected_close": (date.today() + timedelta(days=30)).isoformat(),
    }
    r = founder.post(f"{BASE_URL}/api/sales/leads", json=payload, timeout=15)
    assert r.status_code == 201, r.text[:200]
    lead = r.json()
    yield lead
    founder.delete(f"{BASE_URL}/api/sales/leads/{lead['id']}", timeout=15)


class TestSales:
    def test_create_lead_has_history(self, created_lead):
        assert created_lead["stage"] == "new"
        hist = created_lead.get("stage_history") or []
        assert len(hist) == 1
        assert hist[0]["stage"] == "new"

    def test_list_leads(self, founder, created_lead):
        r = founder.get(f"{BASE_URL}/api/sales/leads", timeout=15)
        assert r.status_code == 200
        ids = [l["id"] for l in r.json().get("leads", [])]
        assert created_lead["id"] in ids

    def test_pipeline(self, founder, created_lead):
        r = founder.get(f"{BASE_URL}/api/sales/pipeline", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "columns" in j and "totals" in j
        stages = [c["stage"] for c in j["columns"]]
        assert stages == ["new", "contacted", "proposal", "won", "lost"]
        for c in j["columns"]:
            assert "count" in c and "total_value" in c
        for k in ("total_leads", "open_value", "won_value", "lost_count"):
            assert k in j["totals"]

    def test_stage_change_appends_history(self, founder, created_lead):
        lid = created_lead["id"]
        r = founder.put(f"{BASE_URL}/api/sales/leads/{lid}/stage", json={"stage": "proposal"}, timeout=15)
        assert r.status_code == 200, r.text[:200]
        lead = r.json()
        assert lead["stage"] == "proposal"
        hist = lead.get("stage_history") or []
        assert len(hist) >= 2, f"stage_history should have grown: {hist}"
        assert hist[-1]["stage"] == "proposal"

        # Repeat same stage — should not append (or no-op)
        r2 = founder.put(f"{BASE_URL}/api/sales/leads/{lid}/stage", json={"stage": "proposal"}, timeout=15)
        assert r2.status_code == 200
        lead2 = r2.json()
        assert len(lead2.get("stage_history") or []) == len(hist), "duplicate stage should not append"

    def test_full_put_stage_also_appends(self, founder, created_lead):
        lid = created_lead["id"]
        before = founder.get(f"{BASE_URL}/api/sales/leads/{lid}", timeout=15).json()
        before_hist_len = len(before.get("stage_history") or before.get("lead", {}).get("stage_history") or [])
        payload = {
            "name": "TEST_John Smith",
            "company": "Acme",
            "email": "js@acme.com",
            "stage": "won",
            "value": 15000,
            "currency": "EUR",
        }
        r = founder.put(f"{BASE_URL}/api/sales/leads/{lid}", json=payload, timeout=15)
        assert r.status_code == 200, r.text[:200]
        lead = r.json()
        assert lead["stage"] == "won"
        assert len(lead.get("stage_history") or []) > before_hist_len

    def test_pipeline_aggregation_after_moves(self, founder, created_lead):
        r = founder.get(f"{BASE_URL}/api/sales/pipeline", timeout=15)
        cols = {c["stage"]: c for c in r.json()["columns"]}
        assert cols["won"]["count"] >= 1
        assert cols["won"]["total_value"] >= 15000


class TestSalesDelete:
    def test_delete_lead(self, founder):
        payload = {"name": "TEST_Del", "stage": "new", "value": 100, "currency": "EUR"}
        r = founder.post(f"{BASE_URL}/api/sales/leads", json=payload, timeout=15)
        lid = r.json()["id"]
        d = founder.delete(f"{BASE_URL}/api/sales/leads/{lid}", timeout=15)
        assert d.status_code in (200, 204)
        g = founder.get(f"{BASE_URL}/api/sales/leads/{lid}", timeout=15)
        assert g.status_code == 404


# -------------------------------------------------------------------------
# Workspace isolation via unauthenticated + wrong-user access
# -------------------------------------------------------------------------
class TestIsolation:
    def test_unauth_cannot_list(self):
        r = requests.get(f"{BASE_URL}/api/finance/invoices", timeout=15)
        assert r.status_code in (401, 403), f"expected auth-required, got {r.status_code}"

    def test_unauth_cannot_list_leads(self):
        r = requests.get(f"{BASE_URL}/api/sales/leads", timeout=15)
        assert r.status_code in (401, 403)


# -------------------------------------------------------------------------
# Regression: HR module still working
# -------------------------------------------------------------------------
class TestHRRegression:
    def test_hr_employees(self, founder):
        r = founder.get(f"{BASE_URL}/api/hr/employees", timeout=15)
        # accept 200 or 404 if route not present; but should be 200 per prev iteration
        assert r.status_code == 200, f"HR regression broken: {r.status_code} {r.text[:200]}"
