"""Blog module — receives published articles from Outrank.so via webhook
and exposes a public read API so the frontend can render them.

Collections:
  - blog_posts { id, source, outrank_id, title, slug, content_markdown,
                 content_html, excerpt, cover_image_url, tags,
                 published_at, raw_payload, created_at, updated_at }

Endpoints:
  - POST /api/webhooks/outrank      (Bearer token auth)
  - GET  /api/blog/posts            (public)
  - GET  /api/blog/posts/{slug}     (public)

Outrank webhook payload (per https://www.outrank.so/docs/webhook):
{
  "event_type": "publish_articles",
  "data": {
    "articles": [
      { "id", "title", "slug", "content_markdown", "content_html",
        "meta_description", "created_at", "image_url", "tags": [...] }
    ]
  }
}
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(doc: dict) -> dict:
    """Strip Mongo internals before returning over the API."""
    doc.pop("_id", None)
    doc.pop("raw_payload", None)  # internal debug field, don't expose
    return doc


class BlogPost(BaseModel):
    id: str
    source: str
    title: str
    slug: str
    content_markdown: str
    content_html: str
    excerpt: Optional[str] = None
    cover_image_url: Optional[str] = None
    tags: List[str] = []
    published_at: str
    created_at: str
    updated_at: str


def _validate_bearer(auth_header: Optional[str]) -> None:
    """Fail closed if OUTRANK_WEBHOOK_TOKEN is unset — we never accept
    unauthenticated writes."""
    expected = os.environ.get("OUTRANK_WEBHOOK_TOKEN")
    if not expected:
        logger.error("OUTRANK_WEBHOOK_TOKEN is not configured on the server.")
        raise HTTPException(status_code=503, detail="Webhook receiver not configured.")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    token = auth_header.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid access token.")


async def _upsert_articles(
    db: AsyncIOMotorDatabase,
    articles: List[dict],
    *,
    allow_create: bool,
) -> List[dict]:
    """Upsert (or update-only) a list of Outrank article dicts into
    `blog_posts`, keyed by slug. Returns the list of processed articles
    with their action ("created" / "updated" / "skipped")."""
    now = _now_iso()
    results: List[dict] = []

    for art in articles:
        if not isinstance(art, dict):
            continue
        slug = (art.get("slug") or "").strip()
        title = (art.get("title") or "").strip()
        if not slug or not title:
            logger.warning("Outrank article skipped — missing slug/title: %r", art.get("id"))
            continue

        doc = {
            "source": "outrank",
            "outrank_id": art.get("id"),
            "title": title,
            "slug": slug,
            "content_markdown": art.get("content_markdown") or "",
            "content_html": art.get("content_html") or "",
            "excerpt": art.get("meta_description") or None,
            "cover_image_url": art.get("image_url") or None,
            "tags": art.get("tags") or [],
            "published_at": art.get("created_at") or now,
            "raw_payload": art,
            "updated_at": now,
        }

        existing = await db.blog_posts.find_one(
            {"slug": slug}, {"_id": 1, "id": 1, "created_at": 1, "published_at": 1}
        )

        # Preserve the original published_at on updates if the payload
        # doesn't explicitly ship a new one.
        if existing and not art.get("created_at"):
            doc["published_at"] = existing.get("published_at") or doc["published_at"]

        if existing:
            await db.blog_posts.update_one({"_id": existing["_id"]}, {"$set": doc})
            results.append({
                "id": existing.get("id") or str(existing["_id"]),
                "slug": slug,
                "action": "updated",
            })
        elif allow_create:
            doc["id"] = str(uuid.uuid4())
            doc["created_at"] = now
            await db.blog_posts.insert_one(doc)
            results.append({"id": doc["id"], "slug": slug, "action": "created"})
        else:
            # update_article for an unknown slug — skip (caller returns 404
            # if nothing was processed).
            results.append({"slug": slug, "action": "skipped_not_found"})

    # For update-only calls, treat 'skipped_not_found' as no-op so the
    # caller can distinguish "nothing found" from real updates.
    if not allow_create:
        return [r for r in results if r["action"] == "updated"]
    return results


def build_router(db: AsyncIOMotorDatabase, get_founder_user=None) -> APIRouter:
    router = APIRouter(tags=["blog"])

    # ---- Webhook (Outrank → us) ------------------------------------------
    @router.post("/api/webhooks/outrank")
    async def outrank_webhook(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        _validate_bearer(authorization)

        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body.")

        event_type = (payload or {}).get("event_type")
        data = (payload or {}).get("data") or {}

        # ---- publish_articles: create/upsert new articles -----------------
        if event_type == "publish_articles":
            articles = data.get("articles") or []
            if not isinstance(articles, list) or not articles:
                raise HTTPException(status_code=400, detail="No articles in payload.")
            processed = await _upsert_articles(db, articles, allow_create=True)
            logger.info("Outrank publish_articles → %d article(s): %s", len(processed), processed)
            return {"ok": True, "event": event_type, "processed": len(processed), "articles": processed}

        # ---- update_article: update an existing article by slug -----------
        if event_type == "update_article":
            # Outrank may send a single article at data.article, or a list at
            # data.articles — accept both shapes.
            single = data.get("article")
            articles = [single] if single else (data.get("articles") or [])
            if not articles:
                raise HTTPException(status_code=400, detail="No article in payload.")
            processed = await _upsert_articles(db, articles, allow_create=False)
            if not processed:
                raise HTTPException(status_code=404, detail="Article slug not found.")
            logger.info("Outrank update_article → %d article(s): %s", len(processed), processed)
            return {"ok": True, "event": event_type, "processed": len(processed), "articles": processed}

        # Acknowledge unknown event types with 200 so Outrank doesn't retry.
        logger.info("Outrank webhook: ignoring event_type=%r", event_type)
        return {"ok": True, "ignored": True, "reason": f"unsupported event_type: {event_type}"}

    # ---- Public read API --------------------------------------------------
    @router.get("/api/blog/posts")
    async def list_posts(limit: int = 50):
        limit = max(1, min(int(limit or 50), 100))
        cursor = db.blog_posts.find().sort("published_at", -1).limit(limit)
        posts = [_clean(p) async for p in cursor]
        return {"posts": posts, "count": len(posts)}

    @router.get("/api/blog/posts/{slug}")
    async def get_post(slug: str):
        post = await db.blog_posts.find_one({"slug": slug})
        if not post:
            raise HTTPException(status_code=404, detail="Post not found.")
        return _clean(post)

    # ---- Founder-only admin: delete a post -------------------------------
    if get_founder_user is not None:
        from fastapi import Depends

        @router.delete("/api/blog/posts/{slug}")
        async def delete_post(slug: str, user=Depends(get_founder_user)):
            r = await db.blog_posts.delete_one({"slug": slug})
            if r.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Post not found.")
            logger.info("Founder %s deleted blog post slug=%r", user.get("email"), slug)
            return {"ok": True, "slug": slug, "deleted": r.deleted_count}

    # ---- SEO: dynamic sitemap --------------------------------------------
    @router.get("/api/sitemap.xml")
    async def sitemap():
        from fastapi.responses import Response

        base = os.environ.get("PUBLIC_SITE_URL", "https://zynthoro.ai").rstrip("/")

        # Static, publicly-indexable routes. Add here when new public pages
        # ship. Non-crawlable routes (dashboard, subscribe, auth) omitted.
        static = [
            ("/",              "daily",  "1.0"),
            ("/modules",       "weekly", "0.9"),
            ("/assistants",    "weekly", "0.9"),
            ("/pricing",       "weekly", "0.9"),
            ("/blog",          "daily",  "0.9"),
            ("/legal/privacy-policy",    "yearly", "0.3"),
            ("/legal/terms-of-service",  "yearly", "0.3"),
            ("/legal/cookie-policy",     "yearly", "0.3"),
            ("/legal/dpa",     "yearly", "0.3"),
            ("/legal/sla",     "yearly", "0.3"),
        ]

        posts = await db.blog_posts.find(
            {}, {"slug": 1, "updated_at": 1, "published_at": 1}
        ).to_list(5000)

        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for loc, freq, prio in static:
            lines.append(
                f"  <url><loc>{base}{loc}</loc>"
                f"<changefreq>{freq}</changefreq>"
                f"<priority>{prio}</priority></url>"
            )
        for p in posts:
            slug = p.get("slug")
            if not slug:
                continue
            lastmod = (p.get("updated_at") or p.get("published_at") or "").split("T")[0]
            lastmod_tag = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
            lines.append(
                f"  <url><loc>{base}/blog/{slug}</loc>"
                f"{lastmod_tag}"
                f"<changefreq>weekly</changefreq>"
                f"<priority>0.7</priority></url>"
            )
        lines.append("</urlset>")

        return Response(content="\n".join(lines), media_type="application/xml")

    return router
