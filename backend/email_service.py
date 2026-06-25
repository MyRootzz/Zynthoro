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
