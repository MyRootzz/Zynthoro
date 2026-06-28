"""Generic outbound webhook for Slack / Discord / any URL.

Auto-detects the target platform from the URL:
  * ``hooks.slack.com``   → Slack incoming-webhook JSON shape
  * ``discord.com`` / ``discordapp.com`` → Discord webhook shape
  * anything else          → generic JSON payload

Fire-and-forget: errors are logged, never raised. Safe to call from inside
critical webhook paths.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 6.0


def _detect_kind(url: str) -> str:
    u = (url or "").lower()
    if "hooks.slack.com" in u:
        return "slack"
    if "discord.com" in u or "discordapp.com" in u:
        return "discord"
    return "generic"


def _format(kind: str, title: str, body: str, fields: dict) -> dict:
    """Render the payload in the target platform's expected shape."""
    if kind == "slack":
        # Slack Block Kit — looks great in modern Slack workspaces.
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": title, "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": body}},
        ]
        if fields:
            blocks.append({
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*{k}*\n{v}"}
                    for k, v in fields.items()
                ],
            })
        return {"text": title, "blocks": blocks}

    if kind == "discord":
        # Discord embed.
        embed = {
            "title": title,
            "description": body,
            "color": 0x1A4FFF,  # Zynthoro blue
        }
        if fields:
            embed["fields"] = [
                {"name": str(k), "value": str(v), "inline": True}
                for k, v in fields.items()
            ]
        return {"embeds": [embed]}

    # Generic JSON
    return {"title": title, "body": body, "fields": fields}


async def send(
    url: str,
    title: str,
    body: str,
    fields: Optional[dict] = None,
) -> bool:
    """Send a structured notification. Returns True on 2xx, False otherwise.

    Never raises — errors are logged. Empty or falsy URL is treated as
    "disabled" and quietly skipped.
    """
    if not url:
        return False
    kind = _detect_kind(url)
    payload = _format(kind, title, body, fields or {})
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            r = await client.post(url, json=payload)
        if r.status_code // 100 != 2:
            logger.warning("Webhook %s returned %d: %s", kind, r.status_code, r.text[:300])
            return False
        return True
    except Exception:  # pragma: no cover — best-effort
        logger.exception("Webhook %s POST failed", kind)
        return False
