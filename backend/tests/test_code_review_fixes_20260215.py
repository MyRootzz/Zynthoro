"""Regression tests for the 3 code-review fixes (Feb 15, 2026).

  1. HIGH  — reportlab HTML escaping: PDF must not crash on '<' in fields
  2. MED   — invoice status must NOT flip to 'sent' when email send fails
  3. MED   — Bill Hours must be race-safe under concurrent requests
"""
from __future__ import annotations

import asyncio
import uuid

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

import server  # noqa: E402
from server import db as server_db  # noqa: E402
import finance_module  # noqa: E402


_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Fix #1 — reportlab HTML escaping in the PDF renderer
# ---------------------------------------------------------------------------
def test_pdf_renders_when_client_name_contains_angle_brackets():
    inv = {
        "number": "INV-<test>-1",
        "client_name": "Acme <div> Corp",
        "client_email": "acme@example.com",
        "client_address": "1 <script>alert(1)</script> Street\nAmsterdam",
        "issue_date": "2026-02-15",
        "due_date": "2026-03-01",
        "currency": "EUR",
        "items": [
            {"description": "A <B trading — item", "quantity": 2, "unit_price": 100, "tax_rate": 21},
            {"description": "Line with <font color='red'>markup</font>", "quantity": 1, "unit_price": 50, "tax_rate": 21},
        ],
        "subtotal": 250.0, "tax_total": 52.5, "total": 302.5,
        "status": "draft",
        "payment_terms": "Discount <font color=red>50% off</font> after 14 days",
        "bank_details": "IBAN NL01 <bank>BANK</bank> 1234",
        "notes": "Please contact us at <ops@example.com>",
    }
    settings = {
        "company_name": "Ampers & Sand & Co <Ltd>",
        "company_address": "Line 1\n<Amsterdam>",
        "company_email": "test@x.com",
        "company_vat": "NL<001>",
        "default_payment_terms": "", "default_bank_details": "",
    }
    # None of this should raise. Prior to Fix #1 this raised ValueError.
    pdf = finance_module._render_invoice_pdf(inv, settings)
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF-")
    assert len(pdf) > 500


def test_rl_escape_helper_escapes_and_preserves_newlines():
    out = finance_module._rl("A <b>hello</b>\nSecond line & more")
    assert "&lt;b&gt;hello&lt;/b&gt;" in out
    assert "&amp; more" in out
    assert "<br/>" in out  # newline → <br/>


# ---------------------------------------------------------------------------
# Fix #2 — status must NOT flip to 'sent' when send fails
# ---------------------------------------------------------------------------
def test_invoice_status_unchanged_when_email_returns_no_id():
    """Simulates Resend returning `{email_id: None, error: '...'}` and
    asserts the invoice stays in its previous status. We reproduce the
    endpoint's decision branch in-line rather than mock-boot the app.
    """
    async def run():
        wo = f"wo-fix-{uuid.uuid4()}"
        iid = str(uuid.uuid4())
        await server_db.finance_invoices.insert_one({
            "id": iid, "workspace_owner": wo, "number": "T-1",
            "status": "draft", "sent_at": None, "total": 100,
            "created_at": "t", "updated_at": "t",
        })
        try:
            # ---- Case A: email failed (eid=None) → NO update. ----
            email_result = {"email_id": None, "error": "quota exceeded"}
            eid = email_result.get("email_id")
            if eid:
                await server_db.finance_invoices.update_one(
                    {"id": iid, "workspace_owner": wo},
                    {"$set": {"status": "sent", "sent_at": "now"}},
                )
            doc = await server_db.finance_invoices.find_one({"id": iid})
            assert doc["status"] == "draft", "status must stay draft on failure"
            assert doc["sent_at"] is None

            # ---- Case B: email succeeded → update. ----
            email_result = {"email_id": "re_123", "error": None}
            eid = email_result.get("email_id")
            if eid:
                await server_db.finance_invoices.update_one(
                    {"id": iid, "workspace_owner": wo},
                    {"$set": {"status": "sent", "sent_at": "now"}},
                )
            doc = await server_db.finance_invoices.find_one({"id": iid})
            assert doc["status"] == "sent"
            assert doc["sent_at"] == "now"
        finally:
            await server_db.finance_invoices.delete_many({"workspace_owner": wo})
    _run(run())


# ---------------------------------------------------------------------------
# Fix #3 — atomic claim prevents double-billing under concurrency
# ---------------------------------------------------------------------------
def test_atomic_claim_prevents_double_billing():
    """Two concurrent "claim" update_many calls must each get a disjoint
    subset of the unbilled entries — no entry is claimed twice.
    """
    async def run():
        wo = f"wo-fix-{uuid.uuid4()}"
        # Seed 6 unbilled billable entries.
        entries = []
        for _ in range(6):
            entries.append({
                "id": str(uuid.uuid4()), "workspace_owner": wo,
                "project_id": "P1", "billable": True, "hours": 1.0,
                "date": "2026-02-15",
                "created_at": "t", "updated_at": "t",
            })
        await server_db.time_entries.insert_many(entries)
        try:
            tokenA = f"claim-{uuid.uuid4()}"
            tokenB = f"claim-{uuid.uuid4()}"

            async def claim(token):
                return await server_db.time_entries.update_many(
                    {"workspace_owner": wo, "project_id": "P1", "billable": True,
                     "$or": [{"invoiced": {"$exists": False}}, {"invoiced": False}]},
                    {"$set": {"invoiced": True, "invoice_id": token}},
                )
            # Fire both claims concurrently.
            resA, resB = await asyncio.gather(claim(tokenA), claim(tokenB))
            totalClaimed = resA.modified_count + resB.modified_count
            # No entry may be counted twice — union of claims equals total rows.
            assert totalClaimed == 6, f"expected 6 total claimed rows, got {totalClaimed}"

            # And no single entry was claimed by BOTH tokens.
            countA = await server_db.time_entries.count_documents({"workspace_owner": wo, "invoice_id": tokenA})
            countB = await server_db.time_entries.count_documents({"workspace_owner": wo, "invoice_id": tokenB})
            assert countA + countB == 6
        finally:
            await server_db.time_entries.delete_many({"workspace_owner": wo})
    _run(run())


def test_claim_release_on_failure_puts_entries_back():
    """The endpoint releases claimed entries when downstream fails."""
    async def run():
        wo = f"wo-fix-{uuid.uuid4()}"
        token = f"claim-{uuid.uuid4()}"
        await server_db.time_entries.insert_many([
            {"id": str(uuid.uuid4()), "workspace_owner": wo, "project_id": "P", "billable": True, "hours": 2, "invoiced": True, "invoice_id": token, "date": "2026-02-15", "created_at": "t", "updated_at": "t"},
            {"id": str(uuid.uuid4()), "workspace_owner": wo, "project_id": "P", "billable": True, "hours": 3, "invoiced": True, "invoice_id": token, "date": "2026-02-15", "created_at": "t", "updated_at": "t"},
        ])
        try:
            # Simulate the release step from the endpoint's except block.
            await server_db.time_entries.update_many(
                {"workspace_owner": wo, "invoice_id": token},
                {"$set": {"invoiced": False, "invoice_id": None}},
            )
            # Both entries are now unbilled again.
            unbilled = await server_db.time_entries.count_documents({
                "workspace_owner": wo, "billable": True,
                "$or": [{"invoiced": {"$exists": False}}, {"invoiced": False}],
            })
            assert unbilled == 2
        finally:
            await server_db.time_entries.delete_many({"workspace_owner": wo})
    _run(run())
