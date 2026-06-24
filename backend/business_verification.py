"""Business registration verification — AI-powered.

Flow:
1. User uploads a PDF of their business registration document.
2. We extract raw text from the PDF with pypdf.
3. We ask Claude to extract structured fields (company name, registration
   number, country, registration date) and return them as JSON.
4. Eligibility: company registered ≤ 12 months ago → eligible for founder pricing.

If the PDF can't be parsed, or Claude can't find a registration date, or
the company is older than 12 months → user is marked NOT eligible and
the standard €499/mo applies.
"""
import io
import os
import re
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

import pypdf
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
ELIGIBILITY_WINDOW_DAYS = 365

EXTRACTION_PROMPT = """You are a strict document classifier and information extractor.
You will be given the raw text of a PDF that the user claims is an OFFICIAL business
registration document (e.g. KvK uittreksel, LLC Articles of Incorporation, EIN letter,
UK Companies House certificate, German Handelsregister, Spanish CIF / Registro Mercantil,
French SIRET / Kbis, Belgian KBO uittreksel, or equivalent from any country).

Tasks:
1. Determine if this PDF is a real business registration document (true/false).
2. If true, extract:
   - country (ISO country name)
   - company_name (exact legal name)
   - registration_number (the official registration / incorporation number)
   - registration_date (ISO 8601 date string YYYY-MM-DD if present)
   - document_type (e.g. "KvK uittreksel", "LLC Articles", "Companies House", ...)
3. Be strict: only return is_business_registration=true if the document
   clearly contains a registration number AND the issuing authority.

Respond with ONLY a single JSON object, no prose, no markdown fence:
{
  "is_business_registration": true|false,
  "country": string|null,
  "company_name": string|null,
  "registration_number": string|null,
  "registration_date": "YYYY-MM-DD"|null,
  "document_type": string|null,
  "confidence": 0.0-1.0,
  "reason": "short explanation if is_business_registration=false"
}
"""


def extract_pdf_text(pdf_bytes: bytes, max_chars: int = 12000) -> str:
    """Extract text from a PDF byte string. Returns empty string on failure."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pieces = []
        for page in reader.pages[:10]:  # cap at first 10 pages
            try:
                pieces.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(pieces).strip()
        return text[:max_chars]
    except Exception:
        logger.exception("PDF parse failed")
        return ""


def _parse_json_from_reply(reply: str) -> Optional[dict]:
    """Extract the first valid JSON object from a possibly-noisy Claude reply."""
    if not reply:
        return None
    # Strip code fences if any
    cleaned = reply.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # Greedy single-object match
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


async def extract_with_claude(text: str, session_id: str) -> Optional[dict]:
    """Send the document text to Claude and return the structured extraction."""
    if not text:
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("No Claude API key configured")

    chat = (
        LlmChat(api_key=api_key, session_id=session_id, system_message=EXTRACTION_PROMPT)
        .with_model("anthropic", CLAUDE_MODEL)
        .with_params(max_tokens=600)
    )
    user_text = f"Document text (truncated):\n\n---\n{text}\n---"
    try:
        reply = await chat.send_message(UserMessage(text=user_text))
    except Exception:
        logger.exception("Claude extraction call failed")
        return None
    return _parse_json_from_reply(reply)


def _parse_iso_date(value) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    # Tolerate YYYY-MM, YYYY
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def decide_eligibility(extraction: Optional[dict]) -> Tuple[str, str, Optional[datetime]]:
    """Returns (status, message, registration_date_dt).

    status one of: 'eligible' | 'not_eligible' | 'failed'
    """
    if not extraction or not extraction.get("is_business_registration"):
        return (
            "failed",
            "We couldn't verify your document — standard pricing applies at €499/month.",
            None,
        )

    reg_dt = _parse_iso_date(extraction.get("registration_date"))
    if not reg_dt:
        return (
            "failed",
            "We couldn't read the registration date — standard pricing applies at €499/month.",
            None,
        )

    age_days = (datetime.now(timezone.utc) - reg_dt).days
    if age_days < 0:
        # Future-dated doc — treat as failed
        return (
            "failed",
            "We couldn't verify your document — standard pricing applies at €499/month.",
            reg_dt,
        )

    if age_days <= ELIGIBILITY_WINDOW_DAYS:
        return (
            "eligible",
            "Verified! You qualify for Founder pricing — €99/month for your first 3 months, then €499/month.",
            reg_dt,
        )
    return (
        "not_eligible",
        "Your business is established — standard Starter pricing applies at €499/month.",
        reg_dt,
    )


async def verify_pdf(pdf_bytes: bytes, session_id: str) -> dict:
    """Full pipeline: parse PDF -> Claude extract -> decide eligibility."""
    text = extract_pdf_text(pdf_bytes)
    extraction = await extract_with_claude(text, session_id) if text else None
    status, message, reg_dt = decide_eligibility(extraction)
    return {
        "status": status,
        "message": message,
        "extraction": extraction or {},
        "registration_date": reg_dt.isoformat() if reg_dt else None,
        "age_days": (datetime.now(timezone.utc) - reg_dt).days if reg_dt else None,
    }
