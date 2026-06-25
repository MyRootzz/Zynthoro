"""Resend transactional email service.

Sends real emails when RESEND_API_KEY is set. When the key is missing, we
fall back to logging the message and returning the rendered code/link so
the UI can still surface it as a `dev_*` field (development).
"""
import os
import asyncio
import logging
from typing import Optional

import resend

logger = logging.getLogger(__name__)

DEFAULT_FROM_HELLO = os.environ.get("RESEND_FROM_HELLO", "Zynthoro <hello@zynthoro.ai>")
DEFAULT_FROM_SUPPORT = os.environ.get("RESEND_FROM_SUPPORT", "Zynthoro Support <support@zynthoro.ai>")


def is_enabled() -> bool:
    return bool(os.environ.get("RESEND_API_KEY"))


def _init():
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        return False
    resend.api_key = key
    return True


def _layout(title: str, body_html: str, button: Optional[dict] = None) -> str:
    btn = ""
    if button:
        btn = f"""
          <tr><td align="center" style="padding: 28px 0 8px 0;">
            <a href="{button['href']}" style="background:#1A4FFF;color:#fff;text-decoration:none;font-weight:600;font-size:15px;padding:14px 28px;border-radius:6px;display:inline-block;font-family:Inter,Helvetica,Arial,sans-serif;">{button['label']}</a>
          </td></tr>
        """
    return f"""<!doctype html>
<html><body style="margin:0;background:#fff;font-family:Inter,Helvetica,Arial,sans-serif;color:#0A1628;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#fff;">
  <tr><td align="center" style="padding: 28px 16px 8px 16px;">
    <div style="background:#0A1628;color:#D4AF37;font-weight:800;letter-spacing:.04em;padding:8px 14px;border-radius:8px;display:inline-block;font-size:14px;">ZYNTHORO</div>
  </td></tr>
  <tr><td align="center" style="padding: 12px 24px 0 24px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:520px;text-align:left;">
      <tr><td style="font-size:22px;font-weight:700;letter-spacing:-0.01em;color:#000;padding-top:10px;">{title}</td></tr>
      <tr><td style="font-size:14.5px;line-height:1.6;color:#333;padding-top:14px;">{body_html}</td></tr>
      {btn}
      <tr><td style="font-size:12px;color:#888;padding-top:24px;border-top:1px solid #eee;margin-top:24px;">
        © 2026 Zynthoro — Casa Haya International BV. Questions? <a href="mailto:support@zynthoro.ai" style="color:#1A4FFF;">support@zynthoro.ai</a>
      </td></tr>
    </table>
  </td></tr>
</table></body></html>"""


async def _send(from_addr: str, to: str, subject: str, html: str) -> Optional[str]:
    if not _init():
        logger.info("[email-mock from=%s to=%s subject=%s] %s", from_addr, to, subject, html[:160].replace("\n", " "))
        return None
    params = {"from": from_addr, "to": [to], "subject": subject, "html": html}
    try:
        res = await asyncio.to_thread(resend.Emails.send, params)
        return res.get("id") if isinstance(res, dict) else None
    except Exception as e:
        logger.exception("Resend send failed (to=%s, subject=%s): %s", to, subject, e)
        return None


async def send_verification(to: str, link: str) -> Optional[str]:
    return await _send(
        DEFAULT_FROM_HELLO, to, "Verify your Zynthoro account",
        _layout(
            "Verify your email",
            "Welcome to Zynthoro. Click the button below to verify your email and activate your workspace.",
            {"label": "Verify email", "href": link},
        ),
    )


async def send_password_reset(to: str, link: str) -> Optional[str]:
    return await _send(
        DEFAULT_FROM_SUPPORT, to, "Reset your Zynthoro password",
        _layout(
            "Reset your password",
            "We received a request to reset your password. This link is valid for one hour. If you didn't request a reset, you can safely ignore this email.",
            {"label": "Reset password", "href": link},
        ),
    )


async def send_2fa_code(to: str, code: str) -> Optional[str]:
    body = (
        "Use the code below to finish signing in to Zynthoro. "
        "The code is valid for 10 minutes and can only be used once."
    )
    html = _layout(
        "Your security code",
        body + f"<div style='margin-top:20px;font-size:32px;font-weight:700;letter-spacing:0.18em;color:#1A4FFF;font-family:monospace;'>{code}</div>",
    )
    return await _send(DEFAULT_FROM_SUPPORT, to, f"Your Zynthoro security code: {code}", html)


async def send_team_invite(to: str, inviter_email: str, accept_link: str, role: str) -> Optional[str]:
    body = f"<b>{inviter_email}</b> invited you to join their Zynthoro workspace as <b>{role}</b>."
    return await _send(
        DEFAULT_FROM_HELLO, to, f"You're invited to join Zynthoro ({role})",
        _layout("Join your team on Zynthoro", body, {"label": "Accept invitation", "href": accept_link}),
    )



# ===============================================================
# Internal founder alert — fires from the Stripe webhook
# ===============================================================
INTERNAL_ALERT_FROM = os.environ.get("RESEND_FROM_ALERT", "Zynthoro Alerts <alerts@zynthoro.ai>")
INTERNAL_ALERT_TO = os.environ.get("INTERNAL_ALERT_TO", "info@zynthoro.ai")

_EMOJI_FOR_KIND = {
    "subscribe":          ("New subscription",      "#16a34a", "🎉"),
    "upgrade":            ("Plan upgraded",         "#16a34a", "🚀"),
    "downgrade":          ("Plan downgraded",       "#D97706", "⬇️"),
    "seats":              ("Extra seats purchased", "#1A4FFF", "👥"),
    "cancel":             ("Subscription cancelled", "#dc2626", "💔"),
    "payment_failed":     ("Payment failed",        "#dc2626", "⚠️"),
    "trial_end":          ("Trial ending soon",     "#D97706", "⏳"),
    "other":              ("Stripe event",          "#1A4FFF", "ℹ️"),
}


def _fmt_eur(cents_or_eur, already_eur: bool = False) -> str:
    if cents_or_eur is None:
        return "—"
    try:
        v = float(cents_or_eur) if already_eur else float(cents_or_eur) / 100.0
    except (TypeError, ValueError):
        return "—"
    if v >= 1000:
        return f"€{v:,.0f}".replace(",", ".")
    return f"€{v:,.2f}"


async def send_stripe_alert(
    *,
    kind: str,
    event_type: str,
    user_email: Optional[str] = None,
    user_id: Optional[str] = None,
    plan_key: Optional[str] = None,
    amount_eur: Optional[float] = None,
    quantity: Optional[int] = None,
    stripe_session_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    extra: Optional[dict] = None,
) -> Optional[str]:
    """Send a branded internal alert email to info@zynthoro.ai for any Stripe event.

    `kind` is a high-level category from _EMOJI_FOR_KIND. `event_type` is the
    raw Stripe event name (e.g. 'checkout.session.completed').
    """
    title, accent, emoji = _EMOJI_FOR_KIND.get(kind, _EMOJI_FOR_KIND["other"])

    def _row(label: str, value: str) -> str:
        return (
            f"<tr>"
            f"<td style='padding:6px 12px 6px 0;color:#888;font-size:13px;width:130px;vertical-align:top;'>{label}</td>"
            f"<td style='padding:6px 0;color:#0A1628;font-size:13.5px;font-weight:600;'>{value}</td>"
            f"</tr>"
        )

    rows = []
    if user_email:
        rows.append(_row("Customer", user_email))
    if user_id:
        rows.append(_row("User ID", f"<code style='font-size:12px;color:#555;'>{user_id}</code>"))
    if plan_key:
        rows.append(_row("Plan", plan_key))
    if quantity is not None:
        rows.append(_row("Quantity", str(quantity)))
    if amount_eur is not None:
        rows.append(_row("Amount / MRR", _fmt_eur(amount_eur, already_eur=True)))
    if stripe_session_id:
        rows.append(_row("Stripe session", f"<code style='font-size:12px;color:#555;'>{stripe_session_id}</code>"))
    if stripe_subscription_id:
        rows.append(_row("Stripe sub", f"<code style='font-size:12px;color:#555;'>{stripe_subscription_id}</code>"))
    rows.append(_row("Event type", f"<code style='font-size:12px;color:#555;'>{event_type}</code>"))
    if extra:
        for k, v in extra.items():
            rows.append(_row(k, str(v)))

    body_html = (
        f"<p style='margin:0 0 14px 0;font-size:14.5px;color:#333;'>"
        f"<span style='font-size:18px;'>{emoji}</span> A <b>{event_type}</b> event just fired in your Stripe account."
        f"</p>"
        f"<table role='presentation' cellspacing='0' cellpadding='0' style='margin-top:10px;border-collapse:collapse;'>"
        f"{''.join(rows)}"
        f"</table>"
    )

    subject_bits = [title]
    if plan_key:
        subject_bits.append(plan_key)
    if amount_eur:
        subject_bits.append(_fmt_eur(amount_eur, already_eur=True) + "/mo")
    subject = f"[Zynthoro] {' · '.join(subject_bits)}"

    html = _layout(
        title,
        body_html,
        {"label": "Open Stripe dashboard", "href": "https://dashboard.stripe.com/subscriptions"},
    )
    # Override the accent dot using inline-style — fall back to default layout colours
    html = html.replace(
        "<div style=\"background:#0A1628;color:#D4AF37",
        f"<div style=\"background:#0A1628;color:#D4AF37;border-left:4px solid {accent}",
        1,
    )
    return await _send(INTERNAL_ALERT_FROM, INTERNAL_ALERT_TO, subject, html)
