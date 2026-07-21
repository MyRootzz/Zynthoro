"""Finance & Invoicing module — invoices, payments, PDF export, email.

CRUD per workspace, all scoped by `workspace_owner`.

Collections:
  - finance_settings   { workspace_owner, company_name, company_address,
                         company_email, company_vat, logo_url,
                         default_payment_terms, default_bank_details,
                         invoice_prefix, next_invoice_seq, currency }
  - finance_invoices   { id, workspace_owner, number, client_name,
                         client_email, client_address, issue_date, due_date,
                         currency, items: [...], subtotal, tax_total, total,
                         status ("draft"/"sent"/"paid"/"overdue"),
                         payment_terms, bank_details, notes,
                         sent_at, paid_at, created_at, updated_at }
  - finance_payments   { id, workspace_owner, invoice_id, amount, method,
                         date, notes, created_at }
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone, date
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, Field

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

import activity_log
import email_service


# ---- helpers --------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


def _default_settings(wo: str) -> dict:
    return {
        "workspace_owner": wo,
        "company_name": "",
        "company_address": "",
        "company_email": "",
        "company_vat": "",
        "logo_url": "",
        "default_payment_terms": "Payment due within 14 days of invoice date.",
        "default_bank_details": "",
        "invoice_prefix": "INV-",
        "next_invoice_seq": 1,
        "currency": "EUR",
    }


CURRENCY_SYMBOL = {"EUR": "€", "USD": "$", "GBP": "£"}


def _sym(currency: str) -> str:
    return CURRENCY_SYMBOL.get((currency or "EUR").upper(), (currency or "EUR"))


def _totals(items: list[dict]) -> tuple[float, float, float]:
    subtotal = 0.0
    tax_total = 0.0
    for it in items:
        qty = float(it.get("quantity") or 0)
        price = float(it.get("unit_price") or 0)
        tax_rate = float(it.get("tax_rate") or 0)
        line = qty * price
        subtotal += line
        tax_total += line * (tax_rate / 100.0)
    return round(subtotal, 2), round(tax_total, 2), round(subtotal + tax_total, 2)


# ---- schemas --------------------------------------------------------------
class SettingsIn(BaseModel):
    company_name: Optional[str] = Field(default="", max_length=200)
    company_address: Optional[str] = Field(default="", max_length=1000)
    company_email: Optional[str] = Field(default="", max_length=200)
    company_vat: Optional[str] = Field(default="", max_length=60)
    logo_url: Optional[str] = Field(default="", max_length=500)
    default_payment_terms: Optional[str] = Field(default="", max_length=2000)
    default_bank_details: Optional[str] = Field(default="", max_length=2000)
    invoice_prefix: Optional[str] = Field(default="INV-", max_length=20)
    currency: Optional[Literal["EUR", "USD", "GBP"]] = "EUR"


class InvoiceItem(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: float = Field(ge=0)
    unit_price: float = Field(ge=0)
    tax_rate: Optional[float] = Field(default=0, ge=0, le=100)


class InvoiceIn(BaseModel):
    client_name: str = Field(min_length=1, max_length=200)
    client_email: Optional[EmailStr] = None
    client_address: Optional[str] = Field(default="", max_length=1000)
    issue_date: str  # ISO date
    due_date: Optional[str] = None
    currency: Optional[Literal["EUR", "USD", "GBP"]] = "EUR"
    items: List[InvoiceItem] = Field(min_length=1)
    payment_terms: Optional[str] = Field(default="", max_length=2000)
    bank_details: Optional[str] = Field(default="", max_length=2000)
    notes: Optional[str] = Field(default="", max_length=2000)


class PaymentIn(BaseModel):
    amount: float = Field(gt=0)
    method: Optional[str] = Field(default="bank_transfer", max_length=60)
    date: Optional[str] = None
    notes: Optional[str] = Field(default="", max_length=1000)


# ---- PDF generator --------------------------------------------------------
def _render_invoice_pdf(inv: dict, settings: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Invoice {inv['number']}",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#666"))
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=22, leading=26, textColor=colors.HexColor("#0A1628"))
    h_label = ParagraphStyle("hl", parent=styles["Normal"], fontSize=8.5, leading=11,
                             textColor=colors.HexColor("#888"), fontName="Helvetica-Bold")

    story: list = []
    sym = _sym(inv.get("currency", "EUR"))

    # Header row: company (left) — INVOICE title + number (right)
    company_html = (
        f"<b>{settings.get('company_name') or 'Your Company'}</b><br/>"
        f"{(settings.get('company_address') or '').replace(chr(10), '<br/>')}"
    )
    if settings.get("company_email"):
        company_html += f"<br/>{settings['company_email']}"
    if settings.get("company_vat"):
        company_html += f"<br/>VAT: {settings['company_vat']}"

    right = (
        f"<para align='right'>"
        f"<font size='22' color='#0A1628'><b>INVOICE</b></font><br/>"
        f"<font size='11' color='#1A4FFF'><b>{inv['number']}</b></font>"
        f"</para>"
    )
    header = Table(
        [[Paragraph(company_html, body), Paragraph(right, body)]],
        colWidths=[95 * mm, 75 * mm],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header)
    story.append(Spacer(1, 8 * mm))

    # Bill-to + meta
    bill_to = (
        f"<b>Bill To</b><br/>"
        f"{inv['client_name']}<br/>"
        f"{(inv.get('client_address') or '').replace(chr(10), '<br/>')}"
    )
    if inv.get("client_email"):
        bill_to += f"<br/>{inv['client_email']}"

    meta = (
        f"<para align='right'>"
        f"<b>Issue date:</b> {inv.get('issue_date') or ''}<br/>"
        f"<b>Due date:</b> {inv.get('due_date') or '—'}<br/>"
        f"<b>Status:</b> <font color='#1A4FFF'>{(inv.get('status') or 'draft').upper()}</font>"
        f"</para>"
    )
    meta_tbl = Table(
        [[Paragraph(bill_to, body), Paragraph(meta, body)]],
        colWidths=[95 * mm, 75 * mm],
    )
    meta_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(meta_tbl)
    story.append(Spacer(1, 8 * mm))

    # Line items table
    rows = [["Description", "Qty", "Unit price", "Tax %", "Line total"]]
    for it in inv.get("items", []):
        qty = float(it.get("quantity") or 0)
        price = float(it.get("unit_price") or 0)
        tax = float(it.get("tax_rate") or 0)
        line_total = qty * price * (1 + tax / 100.0)
        rows.append([
            Paragraph(it.get("description", ""), body),
            f"{qty:g}",
            f"{sym}{price:,.2f}",
            f"{tax:g}%",
            f"{sym}{line_total:,.2f}",
        ])
    tbl = Table(rows, colWidths=[80 * mm, 16 * mm, 25 * mm, 15 * mm, 30 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F4F6FB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0A1628")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#ccc")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#eee")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 5 * mm))

    # Totals block
    subtotal = inv.get("subtotal", 0.0)
    tax_total = inv.get("tax_total", 0.0)
    total = inv.get("total", 0.0)
    totals = Table(
        [
            ["Subtotal", f"{sym}{subtotal:,.2f}"],
            ["Tax", f"{sym}{tax_total:,.2f}"],
            ["Total due", f"{sym}{total:,.2f}"],
        ],
        colWidths=[130 * mm, 40 * mm],
    )
    totals.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#0A1628")),
        ("LINEABOVE", (0, 2), (-1, 2), 0.5, colors.HexColor("#0A1628")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(totals)
    story.append(Spacer(1, 10 * mm))

    # Payment terms
    pay_terms = (inv.get("payment_terms") or settings.get("default_payment_terms") or "").strip()
    bank = (inv.get("bank_details") or settings.get("default_bank_details") or "").strip()
    if pay_terms:
        story.append(Paragraph("PAYMENT TERMS", h_label))
        story.append(Paragraph(pay_terms.replace("\n", "<br/>"), body))
        story.append(Spacer(1, 4 * mm))
    if bank:
        story.append(Paragraph("BANK DETAILS", h_label))
        story.append(Paragraph(bank.replace("\n", "<br/>"), body))
        story.append(Spacer(1, 4 * mm))
    if inv.get("notes"):
        story.append(Paragraph("NOTES", h_label))
        story.append(Paragraph(str(inv["notes"]).replace("\n", "<br/>"), body))
        story.append(Spacer(1, 4 * mm))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "Thank you for your business. Generated by Zynthoro.",
        small,
    ))

    doc.build(story)
    return buf.getvalue()


# ---- router ---------------------------------------------------------------
def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/finance", tags=["finance"])

    async def _get_settings(wo: str) -> dict:
        s = await db.finance_settings.find_one({"workspace_owner": wo}, {"_id": 0})
        if s:
            return s
        doc = _default_settings(wo)
        doc["created_at"] = _now()
        await db.finance_settings.insert_one(doc)
        doc.pop("_id", None)
        return doc

    async def _next_invoice_number(wo: str, settings: dict) -> str:
        # Atomic increment of the sequence counter.
        res = await db.finance_settings.find_one_and_update(
            {"workspace_owner": wo},
            {"$inc": {"next_invoice_seq": 1}},
            return_document=True,
        )
        seq = (res or {}).get("next_invoice_seq") or settings.get("next_invoice_seq", 1)
        # `find_one_and_update` returns the *incremented* doc, so the number
        # we assign is seq - 1.
        num = max(1, int(seq) - 1)
        prefix = settings.get("invoice_prefix") or "INV-"
        year = date.today().year
        return f"{prefix}{year}-{num:04d}"

    # ---- Settings ---------------------------------------------------------
    @router.get("/settings")
    async def get_settings(user=Depends(get_user)):
        s = await _get_settings(_wo(user))
        return {"settings": s}

    @router.put("/settings")
    async def update_settings(payload: SettingsIn, user=Depends(get_user)):
        wo = _wo(user)
        await _get_settings(wo)  # ensure exists
        update = {k: v for k, v in payload.model_dump().items() if v is not None}
        update["updated_at"] = _now()
        await db.finance_settings.update_one(
            {"workspace_owner": wo}, {"$set": update},
        )
        s = await db.finance_settings.find_one({"workspace_owner": wo}, {"_id": 0})
        return {"settings": s}

    # ---- Invoices ---------------------------------------------------------
    @router.get("/invoices")
    async def list_invoices(user=Depends(get_user), status: Optional[str] = None):
        q: dict = {"workspace_owner": _wo(user)}
        if status:
            q["status"] = status
        rows = await db.finance_invoices.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        # Auto-mark overdue: mutate the returned row AND persist so the
        # status doesn't "flip back" on the single-invoice GET.
        today = date.today().isoformat()
        for r in rows:
            if r.get("status") == "sent" and r.get("due_date") and r["due_date"] < today:
                r["status"] = "overdue"
                await db.finance_invoices.update_one(
                    {"id": r["id"], "workspace_owner": _wo(user)},
                    {"$set": {"status": "overdue", "updated_at": _now()}},
                )
        return {
            "invoices": rows,
            "totals": {
                "total_eur": round(sum(r.get("total", 0) for r in rows), 2),
                "paid_eur": round(sum(r.get("total", 0) for r in rows if r.get("status") == "paid"), 2),
                "outstanding_eur": round(sum(r.get("total", 0) for r in rows if r.get("status") in ("sent", "overdue")), 2),
                "draft_count": sum(1 for r in rows if r.get("status") == "draft"),
                "sent_count": sum(1 for r in rows if r.get("status") == "sent"),
                "paid_count": sum(1 for r in rows if r.get("status") == "paid"),
                "overdue_count": sum(1 for r in rows if r.get("status") == "overdue"),
            },
        }

    @router.post("/invoices", status_code=201)
    async def create_invoice(payload: InvoiceIn, user=Depends(get_user)):
        wo = _wo(user)
        settings = await _get_settings(wo)
        items = [i.model_dump() for i in payload.items]
        subtotal, tax_total, total = _totals(items)
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "number": await _next_invoice_number(wo, settings),
            "client_name": payload.client_name,
            "client_email": payload.client_email,
            "client_address": payload.client_address or "",
            "issue_date": payload.issue_date,
            "due_date": payload.due_date,
            "currency": payload.currency or settings.get("currency") or "EUR",
            "items": items,
            "subtotal": subtotal,
            "tax_total": tax_total,
            "total": total,
            "status": "draft",
            "payment_terms": payload.payment_terms or settings.get("default_payment_terms", ""),
            "bank_details": payload.bank_details or settings.get("default_bank_details", ""),
            "notes": payload.notes or "",
            "sent_at": None,
            "paid_at": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.finance_invoices.insert_one(doc)
        doc.pop("_id", None)
        try:
            await activity_log.log_event(
                db, workspace_owner=wo, actor_email=user.get("email"),
                event_type="invoice_created", icon="receipt",
                title=f"Invoice {doc['number']} created",
                subtitle=f"{doc['client_name']} · {_sym(doc['currency'])}{total:,.2f}",
                href="/dashboard/finance",
            )
        except Exception:
            pass
        return doc

    @router.get("/invoices/{iid}")
    async def get_invoice(iid: str, user=Depends(get_user)):
        doc = await db.finance_invoices.find_one(
            {"id": iid, "workspace_owner": _wo(user)}, {"_id": 0},
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Invoice not found")
        payments = await db.finance_payments.find(
            {"invoice_id": iid, "workspace_owner": _wo(user)}, {"_id": 0},
        ).sort("date", -1).to_list(200)
        return {"invoice": doc, "payments": payments}

    @router.put("/invoices/{iid}")
    async def update_invoice(iid: str, payload: InvoiceIn, user=Depends(get_user)):
        wo = _wo(user)
        existing = await db.finance_invoices.find_one({"id": iid, "workspace_owner": wo})
        if not existing:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if existing.get("status") == "paid":
            raise HTTPException(status_code=400, detail="Cannot edit a paid invoice")
        items = [i.model_dump() for i in payload.items]
        subtotal, tax_total, total = _totals(items)
        update = {
            "client_name": payload.client_name,
            "client_email": payload.client_email,
            "client_address": payload.client_address or "",
            "issue_date": payload.issue_date,
            "due_date": payload.due_date,
            "currency": payload.currency or existing.get("currency") or "EUR",
            "items": items,
            "subtotal": subtotal, "tax_total": tax_total, "total": total,
            "payment_terms": payload.payment_terms or "",
            "bank_details": payload.bank_details or "",
            "notes": payload.notes or "",
            "updated_at": _now(),
        }
        await db.finance_invoices.update_one({"id": iid, "workspace_owner": wo}, {"$set": update})
        doc = await db.finance_invoices.find_one({"id": iid}, {"_id": 0})
        return doc

    @router.delete("/invoices/{iid}")
    async def delete_invoice(iid: str, user=Depends(get_user)):
        wo = _wo(user)
        res = await db.finance_invoices.delete_one({"id": iid, "workspace_owner": wo})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Invoice not found")
        await db.finance_payments.delete_many({"invoice_id": iid, "workspace_owner": wo})
        return {"ok": True, "id": iid}

    # ---- PDF & email ------------------------------------------------------
    @router.get("/invoices/{iid}/pdf")
    async def invoice_pdf(iid: str, user=Depends(get_user)):
        wo = _wo(user)
        inv = await db.finance_invoices.find_one({"id": iid, "workspace_owner": wo}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        settings = await _get_settings(wo)
        pdf_bytes = _render_invoice_pdf(inv, settings)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{inv["number"]}.pdf"',
            },
        )

    @router.post("/invoices/{iid}/send-email")
    async def send_invoice_email(iid: str, user=Depends(get_user)):
        wo = _wo(user)
        inv = await db.finance_invoices.find_one({"id": iid, "workspace_owner": wo})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if not inv.get("client_email"):
            raise HTTPException(status_code=400, detail="Client email is required to send this invoice.")
        settings = await _get_settings(wo)
        pdf_bytes = _render_invoice_pdf(inv, settings)

        sym = _sym(inv.get("currency", "EUR"))
        subject = f"Invoice {inv['number']} from {settings.get('company_name') or 'Zynthoro'}"
        body_html = (
            f"<p>Hi {inv['client_name']},</p>"
            f"<p>Please find your invoice <b>{inv['number']}</b> attached.</p>"
            f"<p>Amount due: <b>{sym}{inv.get('total', 0):,.2f}</b><br/>"
            f"Due date: <b>{inv.get('due_date') or '—'}</b></p>"
            f"<p>{(inv.get('payment_terms') or '').replace(chr(10), '<br/>')}</p>"
            f"<p>Thank you,<br/>{settings.get('company_name') or 'The team'}</p>"
        )
        email_id = await email_service.send_invoice_email(
            to=inv["client_email"],
            subject=subject,
            body_html=body_html,
            pdf_bytes=pdf_bytes,
            pdf_filename=f"{inv['number']}.pdf",
            reply_to=settings.get("company_email") or user.get("email"),
        )
        # send_invoice_email now returns {"email_id":..., "error":...}
        eid = email_id.get("email_id")
        eerr = email_id.get("error")

        await db.finance_invoices.update_one(
            {"id": iid, "workspace_owner": wo},
            {"$set": {
                "status": "sent" if inv.get("status") == "draft" else inv.get("status"),
                "sent_at": _now(), "updated_at": _now(),
            }},
        )
        try:
            await activity_log.log_event(
                db, workspace_owner=wo, actor_email=user.get("email"),
                event_type="invoice_sent", icon="receipt",
                title=f"Invoice {inv['number']} emailed to {inv['client_name']}",
                subtitle=inv["client_email"],
                href="/dashboard/finance",
            )
        except Exception:
            pass
        return {
            "ok": True,
            "email_id": eid,
            "email_sent": eid is not None,
            "error": eerr,
        }

    # ---- Payments ---------------------------------------------------------
    @router.post("/invoices/{iid}/payments", status_code=201)
    async def add_payment(iid: str, payload: PaymentIn, user=Depends(get_user)):
        wo = _wo(user)
        inv = await db.finance_invoices.find_one({"id": iid, "workspace_owner": wo})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        p = payload.model_dump()
        p.update({
            "id": str(uuid.uuid4()),
            "workspace_owner": wo,
            "invoice_id": iid,
            "date": p.get("date") or date.today().isoformat(),
            "created_at": _now(),
        })
        await db.finance_payments.insert_one(p)

        # Auto-mark paid when the sum of payments reaches the invoice total.
        payments = await db.finance_payments.find(
            {"invoice_id": iid, "workspace_owner": wo},
        ).to_list(200)
        paid = round(sum(float(x.get("amount") or 0) for x in payments), 2)
        if paid + 0.005 >= float(inv.get("total", 0)):
            await db.finance_invoices.update_one(
                {"id": iid, "workspace_owner": wo},
                {"$set": {"status": "paid", "paid_at": _now(), "updated_at": _now()}},
            )
            try:
                await activity_log.log_event(
                    db, workspace_owner=wo, actor_email=user.get("email"),
                    event_type="invoice_paid", icon="receipt",
                    title=f"Invoice {inv['number']} marked as paid",
                    subtitle=f"{_sym(inv.get('currency','EUR'))}{paid:,.2f} received",
                    href="/dashboard/finance",
                )
            except Exception:
                pass
        p.pop("_id", None)
        return {"payment": p, "paid_total": paid}

    @router.post("/invoices/{iid}/mark-paid")
    async def mark_paid(iid: str, user=Depends(get_user)):
        wo = _wo(user)
        inv = await db.finance_invoices.find_one({"id": iid, "workspace_owner": wo})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        # Insert a synthetic full-payment record so history is accurate.
        payments = await db.finance_payments.find(
            {"invoice_id": iid, "workspace_owner": wo},
        ).to_list(200)
        paid = round(sum(float(x.get("amount") or 0) for x in payments), 2)
        remaining = round(float(inv.get("total", 0)) - paid, 2)
        if remaining > 0.005:
            await db.finance_payments.insert_one({
                "id": str(uuid.uuid4()),
                "workspace_owner": wo,
                "invoice_id": iid,
                "amount": remaining,
                "method": "manual",
                "date": date.today().isoformat(),
                "notes": "Marked paid manually",
                "created_at": _now(),
            })
        await db.finance_invoices.update_one(
            {"id": iid, "workspace_owner": wo},
            {"$set": {"status": "paid", "paid_at": _now(), "updated_at": _now()}},
        )
        try:
            await activity_log.log_event(
                db, workspace_owner=wo, actor_email=user.get("email"),
                event_type="invoice_paid", icon="receipt",
                title=f"Invoice {inv['number']} marked as paid",
                subtitle=inv.get("client_name"),
                href="/dashboard/finance",
            )
        except Exception:
            pass
        doc = await db.finance_invoices.find_one({"id": iid}, {"_id": 0})
        return doc

    @router.delete("/payments/{pid}")
    async def delete_payment(pid: str, user=Depends(get_user)):
        wo = _wo(user)
        p = await db.finance_payments.find_one({"id": pid, "workspace_owner": wo})
        if not p:
            raise HTTPException(status_code=404, detail="Payment not found")
        await db.finance_payments.delete_one({"id": pid, "workspace_owner": wo})
        # Recompute invoice status if it was marked paid.
        inv = await db.finance_invoices.find_one({"id": p["invoice_id"], "workspace_owner": wo})
        if inv and inv.get("status") == "paid":
            payments = await db.finance_payments.find(
                {"invoice_id": p["invoice_id"], "workspace_owner": wo},
            ).to_list(200)
            paid = round(sum(float(x.get("amount") or 0) for x in payments), 2)
            if paid + 0.005 < float(inv.get("total", 0)):
                new_status = "sent" if inv.get("sent_at") else "draft"
                await db.finance_invoices.update_one(
                    {"id": inv["id"], "workspace_owner": wo},
                    {"$set": {"status": new_status, "paid_at": None, "updated_at": _now()}},
                )
        return {"ok": True, "id": pid}

    return router
