"""AI Studio — text-to-image (Nano Banana / Gemini 3 Flash Image via
Emergent LLM key) and text-to-video (fal.ai Kling 2.5 Pro).

Endpoints:
  POST /api/ai-studio/photo/generate  — Nano Banana
  POST /api/ai-studio/video/generate  — fal.ai (Kling 2.5 Pro by default)
  GET  /api/ai-studio/history         — user's recent generations

Storage: `ai_generations` collection with `{id, workspace_owner, kind
('photo'|'video'), prompt, provider, model, output_url, aspect_ratio,
duration_s?, status ('completed'|'failed'), error?, created_at,
completed_at}`.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# fal.ai model IDs — kept as constants so we can swap models without
# breaking the endpoint contract.
FAL_VIDEO_MODEL = os.environ.get("FAL_VIDEO_MODEL", "fal-ai/kling-video/v2.5/pro/text-to-video")
FAL_VIDEO_TIMEOUT_S = 480  # Kling can take a few minutes


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wo(user: dict) -> str:
    return user.get("id") or user.get("email")


# ---- Pydantic --------------------------------------------------------------
class PhotoIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    aspect_ratio: str = Field(default="1:1")


class VideoIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    duration: str = Field(default="5")  # Kling: "5" or "10"
    aspect_ratio: str = Field(default="16:9")


# ---- Router ----------------------------------------------------------------
def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    router = APIRouter(prefix="/api/ai-studio", tags=["ai-studio"])

    # ---- Photo: Nano Banana --------------------------------------------
    @router.post("/photo/generate")
    async def photo_generate(payload: PhotoIn, user=Depends(get_user)):
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="AI image key not configured.")

        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
        except ImportError:  # pragma: no cover
            raise HTTPException(status_code=503, detail="emergentintegrations not installed.")

        gen_id = str(uuid.uuid4())
        started = _now()
        # Nano Banana doesn't take a native aspect-ratio param — bake it
        # into the prompt so the model composes in the right shape.
        prompt = (
            f"{payload.prompt}\n\n"
            f"Composition: {payload.aspect_ratio} aspect ratio."
        )

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"aistudio-photo-{gen_id}",
                system_message="You are a professional image generation assistant. Generate a single high-quality image matching the user's brief.",
            )
            chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
                modalities=["image", "text"]
            )
            _text, images = await asyncio.wait_for(
                chat.send_message_multimodal_response(UserMessage(text=prompt)),
                timeout=120,
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Photo generation timed out.")
        except Exception as e:
            logger.exception("Nano Banana photo generation failed")
            raise HTTPException(status_code=502, detail=f"Photo generation failed: {e}")

        if not images:
            raise HTTPException(status_code=502, detail="AI returned no image.")

        first = images[0]
        mime = first.get("mime_type") or "image/png"
        b64 = first.get("data")
        output_url = f"data:{mime};base64,{b64}" if b64 else None
        if not output_url:
            raise HTTPException(status_code=502, detail="AI returned an empty image payload.")

        doc = {
            "id": gen_id,
            "workspace_owner": _wo(user),
            "kind": "photo",
            "prompt": payload.prompt,
            "provider": "emergent",
            "model": "gemini-3.1-flash-image-preview",
            "aspect_ratio": payload.aspect_ratio,
            "output_url": output_url,
            "status": "completed",
            "created_at": started,
            "completed_at": _now(),
        }
        await db.ai_generations.insert_one(doc)
        doc.pop("_id", None)
        return doc

    # ---- Video: fal.ai Kling -------------------------------------------
    @router.post("/video/generate")
    async def video_generate(payload: VideoIn, user=Depends(get_user)):
        fal_key = os.environ.get("FAL_KEY")
        if not fal_key:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "FAL_KEY_MISSING",
                    "message": "Video generation isn't available yet — the site owner needs to add FAL_KEY to Secrets. Ask an admin.",
                },
            )

        os.environ["FAL_KEY"] = fal_key  # fal_client reads from env
        try:
            import fal_client
        except ImportError:  # pragma: no cover
            raise HTTPException(status_code=503, detail="fal_client not installed.")

        gen_id = str(uuid.uuid4())
        started = _now()

        # Insert an "in_progress" record so the client can poll history
        # for status if it wants (not required for the sync flow).
        await db.ai_generations.insert_one({
            "id": gen_id,
            "workspace_owner": _wo(user),
            "kind": "video",
            "prompt": payload.prompt,
            "provider": "fal",
            "model": FAL_VIDEO_MODEL,
            "aspect_ratio": payload.aspect_ratio,
            "duration_s": int(payload.duration),
            "status": "in_progress",
            "created_at": started,
        })

        try:
            handler = await asyncio.wait_for(
                fal_client.submit_async(
                    FAL_VIDEO_MODEL,
                    arguments={
                        "prompt": payload.prompt,
                        "duration": payload.duration,
                        "aspect_ratio": payload.aspect_ratio,
                    },
                ),
                timeout=30,
            )
            result = await asyncio.wait_for(handler.get(), timeout=FAL_VIDEO_TIMEOUT_S)
        except asyncio.TimeoutError:
            await db.ai_generations.update_one(
                {"id": gen_id},
                {"$set": {"status": "failed", "error": "timeout", "completed_at": _now()}},
            )
            raise HTTPException(status_code=504, detail="Video generation timed out.")
        except Exception as e:
            logger.exception("fal.ai video generation failed")
            await db.ai_generations.update_one(
                {"id": gen_id},
                {"$set": {"status": "failed", "error": str(e)[:400], "completed_at": _now()}},
            )
            raise HTTPException(status_code=502, detail=f"Video generation failed: {e}")

        output_url = _extract_video_url(result)
        if not output_url:
            await db.ai_generations.update_one(
                {"id": gen_id},
                {"$set": {"status": "failed", "error": "no video url", "completed_at": _now()}},
            )
            raise HTTPException(status_code=502, detail="fal.ai returned no video URL.")

        await db.ai_generations.update_one(
            {"id": gen_id},
            {"$set": {"status": "completed", "output_url": output_url, "completed_at": _now()}},
        )
        doc = await db.ai_generations.find_one({"id": gen_id}, {"_id": 0})
        return doc

    # ---- History -------------------------------------------------------
    @router.get("/history")
    async def history(user=Depends(get_user), limit: int = 30):
        limit = max(1, min(int(limit or 30), 100))
        rows = await (
            db.ai_generations
            .find({"workspace_owner": _wo(user)}, {"_id": 0})
            .sort("created_at", -1)
            .limit(limit)
            .to_list(limit)
        )
        return {"generations": rows, "count": len(rows)}

    return router


# ---- helpers ---------------------------------------------------------------
def _extract_image_url(result: Any) -> Optional[str]:
    """Emergent ImageGeneration returns different shapes across models —
    normalise into a single URL."""
    if not result:
        return None
    if isinstance(result, str):
        return result if result.startswith(("http", "data:")) else None
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("image_url")
    if isinstance(result, dict):
        if result.get("url"):
            return result["url"]
        if isinstance(result.get("images"), list) and result["images"]:
            img = result["images"][0]
            return img.get("url") if isinstance(img, dict) else img
        if result.get("image_b64"):
            return f"data:image/png;base64,{result['image_b64']}"
    # Bytes → embed inline
    if isinstance(result, (bytes, bytearray)):
        b64 = base64.b64encode(bytes(result)).decode()
        return f"data:image/png;base64,{b64}"
    return None


def _extract_video_url(result: Any) -> Optional[str]:
    """Kling / most fal.ai video models return
    `{"video": {"url": "..."}}`. Fall back to first video-like URL."""
    if not result:
        return None
    if isinstance(result, dict):
        v = result.get("video")
        if isinstance(v, dict) and v.get("url"):
            return v["url"]
        if isinstance(v, str) and v.startswith("http"):
            return v
        # Some models return `{output: <url>}` or `{videos: [...]}`
        if isinstance(result.get("videos"), list) and result["videos"]:
            first = result["videos"][0]
            return first.get("url") if isinstance(first, dict) else first
        if isinstance(result.get("output"), str):
            return result["output"]
    return None
