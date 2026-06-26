"""Daily founder digest.

Aggregates the last 24 hours of:
  - New presale signups (excluding `is_test=True`)
  - New voice-tryout leads (with email — anonymous tryouts are summarised as a count)
  - Stripe MRR / ARR snapshot (best-effort)

Sends a single HTML email to ``DIGEST_TO`` (defaults to info@zynthoro.ai) via the
existing Resend integration. Runs as a background asyncio task that wakes every
hour and fires exactly once when the configured send hour (UTC) is reached.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Configurable via env. Default: 07:00 UTC == 08:00 CET / 09:00 CEST.
DIGEST_HOUR_UTC = int(os.environ.get("DIGEST_HOUR_UTC", "7"))
DIGEST_TO = os.environ.get("DIGEST_TO", "info@zynthoro.ai")
DIGEST_FROM = os.environ.get(
    "RESEND_FROM_HELLO", "Zynthoro <hello@zynthoro.ai>"
)


# ---------------------------------------------------------------------- data
async def _collect(db) -> Dict[str, Any]:
    """Pull the last-24h slice of leads + signups."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    presale = await db.presale_signups.find(
        {"is_test": {"$ne": True}, "created_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    voice = await db.voice_tryout_leads.find(
        {"is_test": {"$ne": True}, "created_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    voice_with_email = [v for v in voice if v.get("email")]
    voice_anon = [v for v in voice if not v.get("email")]

    return {
        "window_start": cutoff,
        "window_end": datetime.now(timezone.utc).isoformat(),
        "presale": presale,
        "voice_leads": voice_with_email,
        "voice_anonymous_count": len(voice_anon),
        "presale_total_real": await db.presale_signups.count_documents(
            {"is_test": {"$ne": True}}
        ),
        "voice_total_real": await db.voice_tryout_leads.count_documents(
            {"is_test": {"$ne": True}}
        ),
    }


# ---------------------------------------------------------------------- html
def _row(label: str, value: str) -> str:
    return (
        f'<tr><td style="padding:6px 12px 6px 0;color:#666;font-size:13px;">{label}</td>'
        f'<td style="padding:6px 0;color:#0A1628;font-size:13.5px;font-weight:600;">{value}</td></tr>'
    )


def _list_block(title: str, items: List[Dict[str, Any]], render) -> str:
    if not items:
        return (
            f'<h3 style="margin:24px 0 8px 0;font-size:15px;color:#0A1628;">{title}</h3>'
            '<p style="margin:0;color:#999;font-size:13px;">No new entries in the last 24 hours.</p>'
        )
    rows = "".join(
        f'<tr><td style="padding:8px 0;border-top:1px solid #eee;font-size:13.5px;color:#0A1628;">{render(it)}</td></tr>'
        for it in items
    )
    return (
        f'<h3 style="margin:24px 0 4px 0;font-size:15px;color:#0A1628;">{title} '
        f'<span style="color:#1A4FFF;">({len(items)})</span></h3>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>'
    )


def render_html(data: Dict[str, Any]) -> str:
    def render_presale(r):
        plan = r.get("plan_interest") or "—"
        company = r.get("company") or "—"
        return (
            f"<b>{r.get('name','—')}</b> &lt;{r.get('email','—')}&gt;"
            f"<br><span style='color:#666;font-size:12.5px;'>{company} · interested in {plan}</span>"
        )

    def render_voice(r):
        snippet = (r.get("transcript") or "").strip()
        if len(snippet) > 140:
            snippet = snippet[:137] + "…"
        return (
            f"<b>{r.get('email','—')}</b>"
            f"<br><span style='color:#666;font-size:12.5px;font-style:italic;'>“{snippet or '(no transcript)'}”</span>"
        )

    header_kpis = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 4px 0;">'
        + _row("New presale signups (24h)", str(len(data["presale"])))
        + _row("Voice tryout leads with email (24h)", str(len(data["voice_leads"])))
        + _row("Anonymous voice tryouts (24h)", str(data["voice_anonymous_count"]))
        + _row("Total real presale signups", str(data["presale_total_real"]))
        + _row("Total real voice tryouts", str(data["voice_total_real"]))
        + "</table>"
    )

    body = (
        '<p style="margin:0 0 12px 0;color:#444;font-size:14px;">'
        "Here&rsquo;s your daily Zynthoro pipeline digest — leads from the last 24 hours."
        "</p>"
        + header_kpis
        + _list_block("New presale signups", data["presale"], render_presale)
        + _list_block("Voice tryout leads", data["voice_leads"], render_voice)
        + '<p style="margin:24px 0 0 0;color:#999;font-size:12px;">'
        "Test/QA entries are filtered out. See the founder dashboard for full history."
        "</p>"
    )

    return f"""<!doctype html>
<html><body style="margin:0;background:#fff;font-family:Inter,Helvetica,Arial,sans-serif;color:#0A1628;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr><td align="center" style="padding:24px 16px 8px 16px;">
    <div style="background:#0A1628;color:#D4AF37;font-weight:800;letter-spacing:.04em;padding:8px 14px;border-radius:8px;display:inline-block;font-size:14px;">ZYNTHORO</div>
  </td></tr>
  <tr><td align="center" style="padding: 8px 16px 32px 16px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;text-align:left;">
      <tr><td style="font-size:22px;font-weight:700;color:#000;padding-top:10px;">Daily pipeline digest</td></tr>
      <tr><td style="padding-top:12px;">{body}</td></tr>
    </table>
  </td></tr>
</table></body></html>"""


# ---------------------------------------------------------------------- send
async def send_digest_now(db, force: bool = False) -> Dict[str, Any]:
    """Build and send the digest immediately. Returns a summary."""
    data = await _collect(db)
    html = render_html(data)

    today = datetime.now(timezone.utc).date().isoformat()
    if not force:
        already = await db.system_state.find_one({"_id": "daily_digest"}, {"_id": 0})
        if already and already.get("last_sent_date") == today:
            return {"sent": False, "reason": "already_sent_today", "date": today}

    # Resend send via existing email_service helper
    from email_service import _send  # noqa: WPS433
    subject = f"Zynthoro digest · {today} · {len(data['presale'])} presale · {len(data['voice_leads'])} voice leads"
    msg_id = await _send(DIGEST_FROM, DIGEST_TO, subject, html)

    await db.system_state.update_one(
        {"_id": "daily_digest"},
        {"$set": {"last_sent_date": today, "last_sent_at": datetime.now(timezone.utc).isoformat(), "last_msg_id": msg_id}},
        upsert=True,
    )
    logger.info(
        "Daily digest sent (to=%s, msg_id=%s, presale=%d, voice=%d)",
        DIGEST_TO, msg_id, len(data["presale"]), len(data["voice_leads"]),
    )
    return {
        "sent": True,
        "to": DIGEST_TO,
        "msg_id": msg_id,
        "presale_count": len(data["presale"]),
        "voice_lead_count": len(data["voice_leads"]),
        "date": today,
    }


async def _scheduler_loop(db) -> None:
    """Wake every hour, fire the digest when DIGEST_HOUR_UTC is reached and we
    haven't sent today yet.
    """
    while True:
        try:
            now = datetime.now(timezone.utc)
            if now.hour == DIGEST_HOUR_UTC:
                await send_digest_now(db, force=False)
        except Exception:  # pragma: no cover — never let the loop die
            logger.exception("Daily digest loop iteration failed")
        # Sleep until ~the top of the next hour (with a small jitter for safety).
        now = datetime.now(timezone.utc)
        next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        delay = max(60.0, (next_hour - now).total_seconds())
        await asyncio.sleep(delay)


def start_scheduler(db) -> asyncio.Task:
    """Fire-and-forget scheduler task. Returns the task handle."""
    logger.info(
        "Starting daily digest scheduler (hour=%dZ, to=%s)", DIGEST_HOUR_UTC, DIGEST_TO
    )
    return asyncio.create_task(_scheduler_loop(db))
