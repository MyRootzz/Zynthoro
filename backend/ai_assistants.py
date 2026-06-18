"""AI assistant helpers — Claude Sonnet 4.5 via Emergent universal key.

We expose four assistants:
  - zynthoro_assist : in-platform guide (claude-sonnet-4-5-20250929)
  - zyntha          : content & SEO specialist
  - thoro           : builder & workflow specialist
  - zion            : business & growth specialist

Chat history is stored in MongoDB collection `ai_messages` per session.
"""
import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

ASSISTANTS: Dict[str, Dict[str, str]] = {
    "zynthoro_assist": {
        "name": "Zynthoro Assist",
        "specialty": "Your AI guide inside the platform",
        "avatar_color": "#1A4FFF",
        "system": (
            "You are Zynthoro Assist, a friendly and professional AI assistant built into the Zynthoro platform. "
            "You help users navigate the platform, complete business tasks, and grow their business. "
            "Always be helpful, concise and professional. When possible, offer clickable options rather than long text. "
            "Check the user's subscription level before suggesting premium features. Never be pushy — always offer alternatives. "
            "Keep replies under 5 short sentences unless the user asks for detail."
        ),
    },
    "zyntha": {
        "name": "Zyntha",
        "specialty": "Content & SEO Specialist",
        "avatar_color": "#8B5CF6",
        "system": (
            "You are Zyntha, Zynthoro's Content & SEO specialist. You are creative, energetic and inspiring. "
            "You help users create compelling content, optimize for search engines, and build their brand voice. "
            "Always provide practical, actionable content that can be used immediately."
        ),
    },
    "thoro": {
        "name": "Thoro",
        "specialty": "Builder & Workflow Specialist",
        "avatar_color": "#06B6D4",
        "system": (
            "You are Thoro, Zynthoro's Builder & Workflow specialist. You are technical, precise and results-driven. "
            "You help users build efficient workflows, automations and processes. "
            "Always provide clear, step-by-step instructions and focus on practical implementation."
        ),
    },
    "zion": {
        "name": "Zion",
        "specialty": "Business & Growth Specialist",
        "avatar_color": "#D4AF37",
        "system": (
            "You are Zion, Zynthoro's Business & Growth specialist. You are strategic, business-focused and decisive. "
            "You help users grow their business, improve sales and make smart financial decisions. "
            "Always provide data-driven insights and actionable growth strategies."
        ),
    },
}


def list_assistants():
    return [
        {"key": k, "name": v["name"], "specialty": v["specialty"], "avatar_color": v["avatar_color"]}
        for k, v in ASSISTANTS.items()
    ]


async def get_history(db, session_id: str, limit: int = 30) -> List[Dict]:
    cursor = db.ai_messages.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("created_at", 1).limit(limit)
    return await cursor.to_list(length=limit)


async def save_message(db, session_id: str, assistant: str, user_id: str, role: str, content: str):
    await db.ai_messages.insert_one({
        "session_id": session_id,
        "assistant": assistant,
        "user_id": user_id,
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


async def chat_complete(db, assistant_key: str, session_id: str, user_id: str, message: str) -> str:
    cfg = ASSISTANTS.get(assistant_key)
    if not cfg:
        raise ValueError(f"Unknown assistant: {assistant_key}")

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")

    history = await get_history(db, session_id)
    # Prepend prior history as a single context block (emergentintegrations LlmChat
    # session itself is per-call; we feed past messages via system addendum to keep it simple).
    history_text = ""
    if history:
        rendered = []
        for m in history[-20:]:
            who = "User" if m["role"] == "user" else "Assistant"
            rendered.append(f"{who}: {m['content']}")
        history_text = "\n\nPrior conversation:\n" + "\n".join(rendered)

    system = cfg["system"] + history_text

    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system,
    ).with_model("anthropic", CLAUDE_MODEL).with_params(max_tokens=900)

    try:
        reply = await chat.send_message(UserMessage(text=message))
    except Exception as e:
        logger.exception("Claude chat failed")
        raise RuntimeError(f"AI service error: {e}") from e

    # Persist
    await save_message(db, session_id, assistant_key, user_id, "user", message)
    await save_message(db, session_id, assistant_key, user_id, "assistant", reply)
    return reply
