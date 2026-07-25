"""Accounting CSV auto-ingest — parse bank statements, AI-classify each
line into a chart-of-accounts category, stage for review, then post to
the double-entry journal on confirmation.

Two-stage flow:
  1. `bank_transactions` — one doc per CSV row. Stores raw + parsed data
     plus a `proposed_journal` block drafted by the AI. Status starts as
     "pending".
  2. On confirmation, we build an `acc_journal_entries` doc using the
     existing double-entry model (Cash & bank on one side + the AI-
     classified counterpart account on the other) and mark the
     `bank_transactions` doc as "posted".

Collections:
  - bank_transactions { id, workspace_owner, batch_id, source_bank?,
                        row_index, raw_row, parsed { date, description,
                        amount, currency }, proposed_journal {
                        counterpart_code, counterpart_name, confidence,
                        rationale }, status, journal_entry_id?,
                        created_at, updated_at }

Endpoints (all under /api/accounting/csv):
  - POST /preview  — parse first ~20 rows, guess column mapping
  - POST /ingest   — full parse + AI classify + stage
  - GET  /staged   — list pending staged transactions
  - POST /staged/{id}/confirm  — post to journal
  - POST /staged/{id}/reject   — mark rejected
  - POST /staged/{id}          — patch (edit counterpart_code / amount)
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---- Column-mapping heuristics ---------------------------------------------
_DATE_KEYS = {"date", "datum", "boekingsdatum", "transaction date", "trans date", "buchungsdatum", "posted date"}
_DESC_KEYS = {"description", "omschrijving", "reference", "referentie", "details", "verwendungszweck", "counterparty", "memo", "narrative"}
_AMOUNT_KEYS = {"amount", "bedrag", "value", "sum", "betrag", "transaction amount", "amount (eur)", "amount eur"}
_CURRENCY_KEYS = {"currency", "valuta", "ccy", "curr"}


def _guess_columns(headers: List[str]) -> Dict[str, Optional[str]]:
    """Best-effort column detection for a bank CSV header row."""
    lower = {h: h.lower().strip() for h in headers}
    def _match(keys):
        for h, low in lower.items():
            if low in keys or any(k in low for k in keys):
                return h
        return None
    return {
        "date": _match(_DATE_KEYS),
        "description": _match(_DESC_KEYS),
        "amount": _match(_AMOUNT_KEYS),
        "currency": _match(_CURRENCY_KEYS),
    }


def _parse_amount(raw: Any) -> Optional[float]:
    """Handle European (1.234,56) and Anglo (1,234.56) formats, sign flags."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # Handle "1.234,56" and "1,234.56"
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # Assume comma is decimal separator (EU banks)
        s = s.replace(".", "").replace(",", ".")
    s = s.replace(" ", "").replace("\u00a0", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[str]:
    """Return YYYY-MM-DD or None. Accepts common EU/ISO formats."""
    if not raw:
        return None
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _sniff_reader(csv_text: str) -> csv.DictReader:
    sample = csv_text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return csv.DictReader(io.StringIO(csv_text), dialect=dialect)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


# ---- AI classification -----------------------------------------------------
# We ask Claude to pick from the workspace's chart of accounts. Batched
# per ingest to save credits. Rate limit awareness: the request payload
# includes a compact JSON list, LLM returns a JSON array of same length.
async def _ai_classify_transactions(
    transactions: List[Dict[str, Any]],
    accounts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return a list of {counterpart_code, counterpart_name, confidence,
    rationale} — same length as `transactions`."""
    if not transactions:
        return []
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        logger.warning("EMERGENT_LLM_KEY missing — falling back to heuristic classification")
        return [_heuristic_classify(t, accounts) for t in transactions]

    # Compact account list for prompt (expense + revenue accounts only,
    # since bank counterparts are typically P&L accounts + AR/AP).
    relevant = [
        {"code": a["code"], "name": a["name"], "type": a["type"]}
        for a in accounts
        if a.get("type") in ("expense", "revenue", "liability", "asset")
        and a.get("code") != "1000"  # exclude cash — that's always the debit/credit counter
    ]

    system = (
        "You are an accountant classifying bank statement rows into a chart of accounts.\n"
        "For each transaction, return a JSON object with keys: "
        '"counterpart_code" (string, must be one of the provided codes), '
        '"confidence" (0.0-1.0), and "rationale" (max 90 chars).\n'
        "Rules:\n"
        "- Positive amount = money IN (choose a revenue or AR account).\n"
        "- Negative amount = money OUT (choose an expense or AP account).\n"
        "- If the description is vague, pick the closest match and lower the confidence.\n"
        "- ALWAYS pick a code from the provided list — never invent one.\n"
        "Return ONLY a JSON array of length N in the same order — no prose."
    )

    payload = {"accounts": relevant, "transactions": transactions}
    user_msg = UserMessage(text=json.dumps(payload, ensure_ascii=False))
    chat = (
        LlmChat(api_key=api_key, session_id=f"csv-{uuid.uuid4()}", system_message=system)
        .with_model("anthropic", "claude-sonnet-4-6")
        .with_params(max_tokens=4000)
    )

    try:
        reply = await chat.send_message(user_msg)
        parsed = _extract_json_array(reply)
        if isinstance(parsed, list) and len(parsed) == len(transactions):
            valid_codes = {a["code"] for a in relevant}
            result = []
            for i, item in enumerate(parsed):
                code = str(item.get("counterpart_code") or "").strip()
                if code not in valid_codes:
                    result.append(_heuristic_classify(transactions[i], accounts))
                    continue
                name = next((a["name"] for a in relevant if a["code"] == code), code)
                result.append({
                    "counterpart_code": code,
                    "counterpart_name": name,
                    "confidence": float(item.get("confidence") or 0.6),
                    "rationale": str(item.get("rationale") or "")[:120],
                })
            return result
    except Exception as e:
        logger.warning("AI classification failed, falling back to heuristics: %s", e)

    return [_heuristic_classify(t, accounts) for t in transactions]


_JSON_ARRAY_RE = re.compile(r"\[[\s\S]*\]")


def _extract_json_array(text: str) -> Any:
    """Extract the first JSON array from a possibly-noisy LLM reply."""
    if not text:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    m = _JSON_ARRAY_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except (ValueError, TypeError):
        return None


# ---- Heuristic fallback ----------------------------------------------------
_HEURISTIC_RULES: List[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(stripe|paypal|adyen|mollie)\b", re.I), "4100"),  # Service revenue on positives
    (re.compile(r"\b(rent|huur|mietvertrag|lease)\b", re.I), "5200"),
    (re.compile(r"\b(google|meta|facebook|linkedin ads|tiktok|instagram)\b", re.I), "5300"),
    (re.compile(r"\b(google workspace|microsoft|zoom|slack|notion|figma|github|aws|render|vercel|hosting|domain|saas)\b", re.I), "5100"),
    (re.compile(r"\b(salaris|salary|payroll|wage)\b", re.I), "5400"),
    (re.compile(r"\b(accountant|lawyer|notary|advocaat)\b", re.I), "5500"),
    (re.compile(r"\b(uber|taxi|train|ns\b|dutch railways|db bahn|flixbus|hotel|restaurant|lunch|coffee)\b", re.I), "5600"),
    (re.compile(r"\b(bank fee|transactiekosten|interest|rente)\b", re.I), "5900"),
    (re.compile(r"\b(btw|vat|belastingdienst|finanzamt)\b", re.I), "2100"),
]


def _heuristic_classify(t: Dict[str, Any], accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    desc = (t.get("description") or "").lower()
    amt = t.get("amount") or 0
    by_code = {a["code"]: a for a in accounts}
    for rx, code in _HEURISTIC_RULES:
        if rx.search(desc) and code in by_code:
            return {
                "counterpart_code": code,
                "counterpart_name": by_code[code]["name"],
                "confidence": 0.55,
                "rationale": f"Matched pattern: {rx.pattern[:60]}",
            }
    # Fallback by sign
    fallback_code = "4900" if amt >= 0 else "5900"
    if fallback_code not in by_code:
        fallback_code = "4000" if amt >= 0 else "5100"
    a = by_code.get(fallback_code)
    return {
        "counterpart_code": fallback_code,
        "counterpart_name": a["name"] if a else fallback_code,
        "confidence": 0.3,
        "rationale": "Fallback by sign (no keyword match).",
    }


# ---- Pydantic I/O ----------------------------------------------------------
class ColumnMap(BaseModel):
    date: str
    description: str
    amount: str
    currency: Optional[str] = None


class CsvPreviewIn(BaseModel):
    csv_text: str = Field(min_length=1, max_length=8_000_000)


class CsvIngestIn(BaseModel):
    csv_text: str = Field(min_length=1, max_length=8_000_000)
    column_map: ColumnMap
    source_bank: Optional[str] = Field(default=None, max_length=60)


class StagedPatchIn(BaseModel):
    counterpart_code: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None


# ---- Router ----------------------------------------------------------------
def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/accounting/csv", tags=["accounting-csv"])

    async def _load_accounts(wo: str) -> List[Dict[str, Any]]:
        rows = await db.acc_accounts.find({"workspace_owner": wo}, {"_id": 0}).to_list(500)
        if not rows:
            # Trigger seed via the main accounting router by calling its
            # first-use path — cheapest: mirror the default here.
            from accounting_module import DEFAULT_COA
            docs = [
                {
                    "id": str(uuid.uuid4()),
                    "workspace_owner": wo,
                    "code": c, "name": n, "type": t,
                    "is_system": True, "created_at": _now(),
                }
                for c, n, t in DEFAULT_COA
            ]
            await db.acc_accounts.insert_many(docs)
            rows = docs
        return rows

    @router.post("/preview")
    async def preview(payload: CsvPreviewIn, user=Depends(get_user)):
        reader = _sniff_reader(payload.csv_text)
        headers = reader.fieldnames or []
        sample = []
        for i, row in enumerate(reader):
            if i >= 20:
                break
            sample.append(row)
        return {
            "headers": headers,
            "sample_rows": sample,
            "suggested_map": _guess_columns(headers),
            "row_count_sampled": len(sample),
        }

    @router.post("/ingest")
    async def ingest(payload: CsvIngestIn, user=Depends(get_user)):
        wo = _wo(user)
        accounts = await _load_accounts(wo)

        reader = _sniff_reader(payload.csv_text)
        headers = reader.fieldnames or []
        cm = payload.column_map
        for f in (cm.date, cm.description, cm.amount):
            if f not in headers:
                raise HTTPException(status_code=400, detail=f"Column '{f}' not found in CSV headers")

        batch_id = str(uuid.uuid4())
        parsed_txs: List[Dict[str, Any]] = []
        raw_rows: List[Dict[str, Any]] = []
        for idx, row in enumerate(reader):
            amt = _parse_amount(row.get(cm.amount))
            dt = _parse_date(row.get(cm.date, ""))
            desc = (row.get(cm.description) or "").strip()
            if amt is None or not dt:
                continue  # skip unparseable rows
            currency = "EUR"
            if cm.currency and row.get(cm.currency):
                currency = (row.get(cm.currency) or "").strip().upper() or "EUR"
            parsed_txs.append({
                "row_index": idx,
                "date": dt,
                "description": desc,
                "amount": round(amt, 2),
                "currency": currency,
            })
            raw_rows.append(dict(row))

        if not parsed_txs:
            raise HTTPException(status_code=400, detail="No parseable rows found. Check the column mapping.")

        classifications = await _ai_classify_transactions(
            [{"date": t["date"], "description": t["description"], "amount": t["amount"]} for t in parsed_txs],
            accounts,
        )

        now = _now()
        docs = []
        for parsed, raw, cls in zip(parsed_txs, raw_rows, classifications):
            docs.append({
                "id": str(uuid.uuid4()),
                "workspace_owner": wo,
                "batch_id": batch_id,
                "source_bank": payload.source_bank,
                "row_index": parsed["row_index"],
                "raw_row": raw,
                "parsed": {
                    "date": parsed["date"],
                    "description": parsed["description"],
                    "amount": parsed["amount"],
                    "currency": parsed["currency"],
                },
                "proposed_journal": cls,
                "status": "pending",
                "journal_entry_id": None,
                "created_at": now,
                "updated_at": now,
            })
        if docs:
            await db.bank_transactions.insert_many(docs)
        return {
            "batch_id": batch_id,
            "ingested": len(docs),
            "skipped": (idx + 1 if parsed_txs else 0) - len(docs),
        }

    @router.get("/staged")
    async def list_staged(
        user=Depends(get_user),
        status: str = Query(default="pending"),
        limit: int = Query(default=200, ge=1, le=1000),
    ):
        q = {"workspace_owner": _wo(user), "status": status}
        rows = await db.bank_transactions.find(q, {"_id": 0}).sort([("parsed.date", -1), ("row_index", 1)]).to_list(limit)
        return {"transactions": rows, "count": len(rows)}

    @router.post("/staged/{tid}")
    async def patch_staged(tid: str, payload: StagedPatchIn, user=Depends(get_user)):
        wo = _wo(user)
        doc = await db.bank_transactions.find_one({"id": tid, "workspace_owner": wo})
        if not doc:
            raise HTTPException(status_code=404, detail="Not found")
        if doc["status"] != "pending":
            raise HTTPException(status_code=400, detail="Only pending transactions can be edited.")

        set_fields: Dict[str, Any] = {"updated_at": _now()}
        if payload.counterpart_code:
            accounts = await _load_accounts(wo)
            match = next((a for a in accounts if a["code"] == payload.counterpart_code), None)
            if not match:
                raise HTTPException(status_code=400, detail=f"Unknown account code {payload.counterpart_code}")
            set_fields["proposed_journal.counterpart_code"] = match["code"]
            set_fields["proposed_journal.counterpart_name"] = match["name"]
            set_fields["proposed_journal.confidence"] = 1.0
            set_fields["proposed_journal.rationale"] = "Manually set by user."
        if payload.description is not None:
            set_fields["parsed.description"] = payload.description.strip()
        if payload.amount is not None:
            set_fields["parsed.amount"] = round(float(payload.amount), 2)
        await db.bank_transactions.update_one({"id": tid, "workspace_owner": wo}, {"$set": set_fields})
        updated = await db.bank_transactions.find_one({"id": tid, "workspace_owner": wo}, {"_id": 0})
        return updated

    @router.post("/staged/{tid}/reject")
    async def reject_staged(tid: str, user=Depends(get_user)):
        wo = _wo(user)
        res = await db.bank_transactions.update_one(
            {"id": tid, "workspace_owner": wo, "status": "pending"},
            {"$set": {"status": "rejected", "updated_at": _now()}},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Pending transaction not found")
        return {"ok": True, "id": tid, "status": "rejected"}

    @router.post("/staged/{tid}/confirm")
    async def confirm_staged(tid: str, user=Depends(get_user)):
        wo = _wo(user)
        doc = await db.bank_transactions.find_one({"id": tid, "workspace_owner": wo})
        if not doc:
            raise HTTPException(status_code=404, detail="Not found")
        if doc["status"] != "pending":
            raise HTTPException(status_code=400, detail="Only pending transactions can be posted.")

        # Build double-entry: Cash & bank (1000) vs. the AI counterpart.
        accounts = await _load_accounts(wo)
        by_code = {a["code"]: a for a in accounts}
        cash = by_code.get("1000")
        counter_code = doc["proposed_journal"]["counterpart_code"]
        counter = by_code.get(counter_code)
        if not cash or not counter:
            raise HTTPException(status_code=400, detail="Chart of accounts missing required entries.")

        amt = abs(round(float(doc["parsed"]["amount"]), 2))
        if amt == 0:
            raise HTTPException(status_code=400, detail="Amount is zero — cannot post.")

        # Sign convention: positive amount = cash IN → Dr Cash, Cr counterpart.
        # Negative amount = cash OUT → Dr counterpart, Cr Cash.
        if doc["parsed"]["amount"] >= 0:
            lines = [
                {"account_id": cash["id"], "account_code": cash["code"], "account_name": cash["name"], "account_type": cash["type"], "description": doc["parsed"]["description"], "debit": amt, "credit": 0.0},
                {"account_id": counter["id"], "account_code": counter["code"], "account_name": counter["name"], "account_type": counter["type"], "description": doc["parsed"]["description"], "debit": 0.0, "credit": amt},
            ]
        else:
            lines = [
                {"account_id": counter["id"], "account_code": counter["code"], "account_name": counter["name"], "account_type": counter["type"], "description": doc["parsed"]["description"], "debit": amt, "credit": 0.0},
                {"account_id": cash["id"], "account_code": cash["code"], "account_name": cash["name"], "account_type": cash["type"], "description": doc["parsed"]["description"], "debit": 0.0, "credit": amt},
            ]

        entry_no = (await db.acc_journal_entries.count_documents({"workspace_owner": wo})) + 1
        entry_id = str(uuid.uuid4())
        entry = {
            "id": entry_id,
            "workspace_owner": wo,
            "entry_no": entry_no,
            "date": doc["parsed"]["date"],
            "description": doc["parsed"]["description"] or "Bank statement import",
            "lines": lines,
            "total_debit": amt,
            "total_credit": amt,
            "created_at": _now(),
            "created_by": user.get("email"),
            "source": "bank_csv_import",
            "bank_transaction_id": doc["id"],
        }
        await db.acc_journal_entries.insert_one(entry)
        await db.bank_transactions.update_one(
            {"id": tid, "workspace_owner": wo},
            {"$set": {"status": "posted", "journal_entry_id": entry_id, "updated_at": _now()}},
        )
        entry.pop("_id", None)
        return {"ok": True, "journal_entry": entry}

    return router
