"""Weekly founder digest.

Aggregates the last 7 days of:
  - New presale signups (excluding `is_test=True`)
  - New voice-tryout leads (with email — anonymous tryouts are summarised as a count)
  - Kickstart / Compleet / AI+Social purchases (payment_transactions.provisioned=True)
  - AI assistant messages sent by real users (ai_messages)

Sends a single HTML email to ``DIGEST_TO`` (defaults to info@zynthoro.ai) via
the existing Resend integration. Runs as a background asyncio task that wakes
every hour and fires exactly once when the configured send hour (UTC) is
reached on the configured weekday.

2026-07-21 — changed from daily to weekly. The email is now skipped entirely
if all activity counts are zero, so ops don't get a spam message on quiet
weeks.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Configurable via env. Defaults: Monday (weekday=0) at 07:00 UTC
# == 08:00 CET / 09:00 CEST.
DIGEST_HOUR_UTC = int(os.environ.get("DIGEST_HOUR_UTC", "7"))
DIGEST_WEEKDAY = int(os.environ.get("DIGEST_WEEKDAY", "0"))  # 0=Mon … 6=Sun
DIGEST_WINDOW_DAYS = int(os.environ.get("DIGEST_WINDOW_DAYS", "7"))
DIGEST_TO = os.environ.get("DIGEST_TO", "info@zynthoro.ai")
DIGEST_FROM = os.environ.get(
    "RESEND_FROM_HELLO", "Zynthoro <hello@zynthoro.ai>"
)


# ---------------------------------------------------------------------- data
async def _collect(db) -> Dict[str, Any]:
    """Pull the last-N-days slice of leads + signups + purchases + AI usage."""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=DIGEST_WINDOW_DAYS)).isoformat()

    presale = await db.presale_signups.find(
        {"is_test": {"$ne": True}, "created_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)

    voice = await db.voice_tryout_leads.find(
        {"is_test": {"$ne": True}, "created_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)

    voice_with_email = [v for v in voice if v.get("email")]
    voice_anon = [v for v in voice if not v.get("email")]

    # Real paid purchases in the window — Kickstart lifetime, Compleet,
    # AI+Social top-ups. `provisioned=True` filters out abandoned checkouts;
    # `provisioning_blocked` excludes coupon-abuse blocks.
    purchases = await db.payment_transactions.find(
        {
            "provisioned": True,
            "provisioning_blocked": {"$ne": True},
            "provisioned_at": {"$gte": cutoff},
        },
        {"_id": 0, "session_id": 1, "user_id": 1, "amount_total": 1,
         "provisioned_at": 1, "metadata": 1},
    ).sort("provisioned_at", -1).to_list(500)

    # AI messages sent by real users in the window. Real users = have a
    # `user_id` (not the anonymous voice-tryout demo endpoint).
    ai_messages_count = await db.ai_messages.count_documents(
        {"created_at": {"$gte": cutoff}, "role": "user"}
    )

    # New user signups in the window (real accounts, not demo/QA).
    new_users_count = await db.users.count_documents({
        "created_at": {"$gte": cutoff},
        "is_demo": {"$ne": True},
        "is_qa_test": {"$ne": True},
    })

    return {
        "window_days": DIGEST_WINDOW_DAYS,
        "window_start": cutoff,
        "window_end": now.isoformat(),
        "presale": presale,
        "voice_leads": voice_with_email,
        "voice_anonymous_count": len(voice_anon),
        "purchases": purchases,
        "ai_messages_count": ai_messages_count,
        "new_users_count": new_users_count,
        "presale_total_real": await db.presale_signups.count_documents(
            {"is_test": {"$ne": True}}
        ),
        "voice_total_real": await db.voice_tryout_leads.count_documents(
            {"is_test": {"$ne": True}}
        ),
    }


def _has_activity(data: Dict[str, Any]) -> bool:
    """True if there is any real activity worth emailing about.

    Silence rule (2026-07-21): if all of the following are zero, we skip the
    email entirely so ops isn't spammed on quiet weeks.
    """
    return bool(
        len(data.get("presale") or [])
        or len(data.get("voice_leads") or [])
        or data.get("voice_anonymous_count")
        or len(data.get("purchases") or [])
        or data.get("ai_messages_count")
        or data.get("new_users_count")
    )


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
            f'<p style="margin:0;color:#999;font-size:13px;">No new entries this week.</p>'
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

    def render_purchase(r):
        meta = r.get("metadata") or {}
        plan = meta.get("plan_key") or "—"
        tier = meta.get("tier_key") or "—"
        amount_cents = r.get("amount_total") or 0
        try:
            amount_eur = f"€{amount_cents/100:,.2f}"
        except Exception:
            amount_eur = "—"
        return (
            f"<b>{plan}</b> <span style='color:#0F7A2A;font-weight:600;'>{amount_eur}</span>"
            f"<br><span style='color:#666;font-size:12.5px;'>tier: {tier} · session: {r.get('session_id','—')[:22]}…</span>"
        )

    revenue_cents = sum((p.get("amount_total") or 0) for p in data["purchases"])

    header_kpis = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 4px 0;">'
        + _row(f"New user signups ({data['window_days']}d)", str(data["new_users_count"]))
        + _row(f"New presale signups ({data['window_days']}d)", str(len(data["presale"])))
        + _row(f"Voice tryout leads with email ({data['window_days']}d)", str(len(data["voice_leads"])))
        + _row(f"Anonymous voice tryouts ({data['window_days']}d)", str(data["voice_anonymous_count"]))
        + _row(f"Kickstart / Compleet purchases ({data['window_days']}d)", str(len(data["purchases"])))
        + _row(f"Revenue this week", f"€{revenue_cents/100:,.2f}")
        + _row(f"AI assistant messages ({data['window_days']}d)", str(data["ai_messages_count"]))
        + _row("Total real presale signups (all-time)", str(data["presale_total_real"]))
        + _row("Total real voice tryouts (all-time)", str(data["voice_total_real"]))
        + "</table>"
    )

    body = (
        '<p style="margin:0 0 12px 0;color:#444;font-size:14px;">'
        f"Here&rsquo;s your weekly Zynthoro pipeline digest — activity from the last {data['window_days']} days."
        "</p>"
        + header_kpis
        + _list_block("Purchases", data["purchases"], render_purchase)
        + _list_block("New presale signups", data["presale"], render_presale)
        + _list_block("Voice tryout leads", data["voice_leads"], render_voice)
        + '<p style="margin:24px 0 0 0;color:#999;font-size:12px;">'
        "Test/QA/demo entries are filtered out. See the founder dashboard for full history."
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
      <tr><td style="font-size:22px;font-weight:700;color:#000;padding-top:10px;">Weekly pipeline digest</td></tr>
      <tr><td style="padding-top:12px;">{body}</td></tr>
    </table>
  </td></tr>
</table></body></html>"""


# ---------------------------------------------------------------------- send
def _iso_week_key(dt: datetime) -> str:
    """Return the ISO week identifier `YYYY-Www` for idempotency."""
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


async def send_digest_now(db, force: bool = False) -> Dict[str, Any]:
    """Build and send the digest immediately. Returns a summary.

    Skips the send if there is no activity in the window (unless
    force=True), so ops don't get an empty email on quiet weeks.
    """
    data = await _collect(db)
    now = datetime.now(timezone.utc)
    week_key = _iso_week_key(now)

    # Idempotency: at most one digest per ISO week (unless forced).
    if not force:
        already = await db.system_state.find_one({"_id": "weekly_digest"}, {"_id": 0})
        if already and already.get("last_sent_iso_week") == week_key:
            return {"sent": False, "reason": "already_sent_this_week", "iso_week": week_key}

    # No-activity skip. Force overrides this so the admin can force a
    # send for debugging.
    if not force and not _has_activity(data):
        logger.info(
            "Weekly digest skipped — no activity in the last %d days (iso_week=%s)",
            data["window_days"], week_key,
        )
        # Record the skip so the scheduler doesn't try again this week.
        await db.system_state.update_one(
            {"_id": "weekly_digest"},
            {"$set": {
                "last_sent_iso_week": week_key,
                "last_sent_at": now.isoformat(),
                "last_action": "skipped_no_activity",
            }},
            upsert=True,
        )
        return {"sent": False, "reason": "no_activity", "iso_week": week_key}

    html = render_html(data)

    # Resend send via existing email_service helper
    from email_service import _send  # noqa: WPS433
    subject = (
        f"Zynthoro weekly · {week_key} · "
        f"{data['new_users_count']} signups · "
        f"{len(data['purchases'])} purchases · "
        f"€{sum((p.get('amount_total') or 0) for p in data['purchases'])/100:,.2f}"
    )
    msg_id = await _send(DIGEST_FROM, DIGEST_TO, subject, html)

    await db.system_state.update_one(
        {"_id": "weekly_digest"},
        {"$set": {
            "last_sent_iso_week": week_key,
            "last_sent_at": now.isoformat(),
            "last_msg_id": msg_id,
            "last_action": "sent",
        }},
        upsert=True,
    )
    logger.info(
        "Weekly digest sent (to=%s, msg_id=%s, presale=%d, voice=%d, purchases=%d, ai_msgs=%d)",
        DIGEST_TO, msg_id,
        len(data["presale"]), len(data["voice_leads"]),
        len(data["purchases"]), data["ai_messages_count"],
    )
    return {
        "sent": True,
        "to": DIGEST_TO,
        "msg_id": msg_id,
        "iso_week": week_key,
        "presale_count": len(data["presale"]),
        "voice_lead_count": len(data["voice_leads"]),
        "purchase_count": len(data["purchases"]),
        "ai_messages_count": data["ai_messages_count"],
        "new_users_count": data["new_users_count"],
    }


async def _scheduler_loop(db) -> None:
    """Wake every hour, fire the digest when DIGEST_WEEKDAY + DIGEST_HOUR_UTC
    are reached and we haven't sent this ISO week yet.
    """
    while True:
        try:
            now = datetime.now(timezone.utc)
            if now.weekday() == DIGEST_WEEKDAY and now.hour == DIGEST_HOUR_UTC:
                await send_digest_now(db, force=False)
        except Exception:  # pragma: no cover — never let the loop die
            logger.exception("Weekly digest loop iteration failed")
        # Sleep until ~the top of the next hour (with a small floor).
        now = datetime.now(timezone.utc)
        next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        delay = max(60.0, (next_hour - now).total_seconds())
        await asyncio.sleep(delay)


def start_scheduler(db) -> asyncio.Task:
    """Fire-and-forget scheduler task. Returns the task handle."""
    weekday_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][DIGEST_WEEKDAY]
    logger.info(
        "Starting weekly digest scheduler (%s %02d:00Z, window=%dd, to=%s)",
        weekday_name, DIGEST_HOUR_UTC, DIGEST_WINDOW_DAYS, DIGEST_TO,
    )
    return asyncio.create_task(_scheduler_loop(db))
