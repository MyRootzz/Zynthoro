"""Regression tests for Session C1 — Finance & Sales modules.

Run:
    cd /app/backend && python -m pytest tests/test_session_c1_20260215.py -v
"""
from __future__ import annotations

import asyncio
import uuid

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

import server  # noqa: E402  (initialises db + routers)
from server import db as server_db  # noqa: E402
import finance_module  # noqa: E402
import sales_module  # noqa: E402

_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


def _user():
    return {"id": f"test-c1-{uuid.uuid4()}", "email": "c1@test.local"}


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------
def test_finance_totals_computation():
    subtotal, tax, total = finance_module._totals([
        {"quantity": 10, "unit_price": 150, "tax_rate": 21},
        {"quantity": 1, "unit_price": 500, "tax_rate": 21},
    ])
    assert subtotal == 2000.0
    assert tax == 420.0
    assert total == 2420.0


def test_finance_totals_no_tax():
    subtotal, tax, total = finance_module._totals([
        {"quantity": 3, "unit_price": 100, "tax_rate": 0},
    ])
    assert subtotal == 300.0 and tax == 0.0 and total == 300.0


def test_finance_pdf_renders_valid_pdf():
    inv = {
        "number": "INV-2026-0001",
        "client_name": "Acme BV",
        "client_email": "acme@example.com",
        "client_address": "Herengracht 1\n1015 BA Amsterdam",
        "issue_date": "2026-02-15",
        "due_date": "2026-03-01",
        "currency": "EUR",
        "items": [
            {"description": "Consulting hours", "quantity": 10, "unit_price": 150, "tax_rate": 21},
            {"description": "AI onboarding", "quantity": 1, "unit_price": 500, "tax_rate": 21},
        ],
        "subtotal": 2000.0, "tax_total": 420.0, "total": 2420.0,
        "status": "sent",
        "payment_terms": "Payment due within 14 days.",
        "bank_details": "IBAN NL01 BANK 1234 5678 90",
        "notes": "Thanks for your business.",
    }
    settings = {
        "company_name": "Zynthoro BV", "company_address": "Amsterdam, NL",
        "company_email": "info@zynthoro.ai", "company_vat": "NL0001",
        "default_payment_terms": "", "default_bank_details": "",
    }
    pdf = finance_module._render_invoice_pdf(inv, settings)
    assert isinstance(pdf, bytes) and len(pdf) > 500
    assert pdf.startswith(b"%PDF-"), "must be a valid PDF stream"


def test_currency_symbol():
    assert finance_module._sym("EUR") == "€"
    assert finance_module._sym("USD") == "$"
    assert finance_module._sym("GBP") == "£"
    assert finance_module._sym("XYZ") == "XYZ"


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------
def test_pipeline_stages_order():
    assert sales_module.PIPELINE_STAGES == ["new", "contacted", "proposal", "won", "lost"]


def test_sales_lead_stage_history_on_change():
    """Direct DB-level check: changing a lead's stage appends to history."""
    async def run():
        wo = f"wo-c1-{uuid.uuid4()}"
        lid = str(uuid.uuid4())
        await server_db.sales_leads.insert_one({
            "id": lid, "workspace_owner": wo,
            "name": "Test Lead", "stage": "new",
            "value": 1000, "currency": "EUR",
            "stage_history": [{"stage": "new", "at": "t0", "by": "x"}],
            "created_at": "t0", "updated_at": "t0",
        })
        try:
            # Move to contacted → proposal → won
            for s in ("contacted", "proposal", "won"):
                doc = await server_db.sales_leads.find_one({"id": lid})
                hist = list(doc.get("stage_history") or [])
                hist.append({"stage": s, "at": "t", "by": "x"})
                await server_db.sales_leads.update_one(
                    {"id": lid}, {"$set": {"stage": s, "stage_history": hist}},
                )
            final = await server_db.sales_leads.find_one({"id": lid})
            assert final["stage"] == "won"
            assert [h["stage"] for h in final["stage_history"]] == [
                "new", "contacted", "proposal", "won",
            ]
        finally:
            await server_db.sales_leads.delete_many({"workspace_owner": wo})
    _run(run())


def test_finance_invoice_creation_and_deletion():
    """Full DB round-trip: create invoice → list → delete."""
    async def run():
        wo = f"wo-c1-{uuid.uuid4()}"
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "number": "INV-TEST-1",
            "client_name": "X",
            "issue_date": "2026-02-15",
            "currency": "EUR",
            "items": [{"description": "x", "quantity": 1, "unit_price": 100, "tax_rate": 21}],
            "subtotal": 100, "tax_total": 21, "total": 121,
            "status": "draft",
            "created_at": "t", "updated_at": "t",
        }
        try:
            await server_db.finance_invoices.insert_one(doc)
            fetched = await server_db.finance_invoices.find_one({"id": doc["id"]})
            assert fetched["total"] == 121
            await server_db.finance_invoices.delete_one({"id": doc["id"]})
            assert await server_db.finance_invoices.find_one({"id": doc["id"]}) is None
        finally:
            await server_db.finance_invoices.delete_many({"workspace_owner": wo})
    _run(run())
