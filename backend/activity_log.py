"""Lightweight, workspace-scoped activity event log.

Every event is a small document written to `db.activity_events`. The
dashboard summary endpoint reads the most recent events per workspace and
renders them in the "Recent activity" feed.

Keep this module dependency-free (only motor db is required) so it can be
called from any router or background task.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional


async def log_event(
    db,
    *,
    workspace_owner: str,
    actor_email: Optional[str] = None,
    event_type: str,
    icon: str,
    title: str,
    subtitle: Optional[str] = None,
    href: Optional[str] = None,
) -> None:
    """Insert one activity event. Never raises — activity logging must not
    break the primary user action.

    Args:
        workspace_owner: The user_id whose dashboard should show this event.
        actor_email: The email of the person who triggered it (for audit).
        event_type: Short machine key, e.g. "team_member_invited".
        icon: Icon key rendered by DashboardHome (`user_plus`, `receipt`,
            `folder_plus`, `sparkles`).
        title: Human-readable line — appears bold on the feed.
        subtitle: Optional smaller line under the title.
        href: Optional destination for the row when clicked.
    """
    try:
        await db.activity_events.insert_one({
            "id": str(uuid.uuid4()),
            "workspace_owner": workspace_owner,
            "actor_email": actor_email,
            "event_type": event_type,
            "icon": icon,
            "title": title,
            "subtitle": subtitle,
            "href": href,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        # Never let activity logging break the primary flow.
        pass
