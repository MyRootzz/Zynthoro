"""AI assistant helpers — multi-provider routing (Claude Sonnet 4.6 + Gemini 2.5 Flash).

Routing matrix:
  - zynthoro_assist : Claude Sonnet 4.6 — all tiers
  - zyntha          : Gemini 2.5 Flash — all tiers (creative/multimodal)
  - thoro           : Gemini 2.5 Flash for Starter/Creator/Presale tiers,
                      Claude Sonnet 4.6 for Business/Agency/Enterprise tiers
  - zyona           : Claude Sonnet 4.6 — all tiers

Chat history is stored in MongoDB collection `ai_messages` per session.
Per-call execution logs (assistant, provider, model, tier, timestamps) are
stored in `ai_logs` for audit and the XPRIZE judging requirement.
"""
import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

# Model identifiers — kept centralised so they can be swapped via env if needed.
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Tiers that count as "pro" — they unlock Claude on Thoro.
PRO_TIERS = {
    "business", "agency",
    "enterprise", "enterprise basic", "enterprise plus",
    "enterprise advanced", "enterprise elite", "enterprise unlimited",
}


def _normalize_plan(plan: Optional[str]) -> str:
    return (plan or "").strip().lower()


def _is_pro(plan: Optional[str]) -> bool:
    return _normalize_plan(plan) in PRO_TIERS


ZYNTHORO_CONTEXT = (
    "PLATFORM CONTEXT — Zynthoro is an AI-native all-in-one ERP platform for SMEs. "
    "It replaces 15+ tools with one workspace covering 12 domains: "
    "Planning & Organisation, Time Tracking, Purchase Admin, Sales Admin, Accounting, "
    "Invoicing & Finance, Project Management, HR & Personnel, Operations & Processes, "
    "Marketing & Content, Communication & Collaboration, Compliance & Security. "
    "PRICING: Starter €499/mo (basic, no ERP, 1 workspace), Creator €699/mo (adds AI video & photo suite, "
    "1 workspace), Business €899/mo (full sales + basic accounting, 3 workspaces — Most Popular), "
    "Agency €1,199/mo (full non-ERP suite, 5 workspaces), Enterprise from €2,499/mo (all 12 domains, "
    "full ERP, unlimited workspaces). FOUNDER PRICING: new businesses (≤12 months old) can verify and "
    "get Starter for €99/mo for their first 3 months. "
    "AI ASSISTANTS: Zyntha (Content & SEO, Gemini), Thoro (Builder & Workflow — Gemini on Starter/Creator, "
    "Claude on Business+), Zyona (Business & Growth, Claude), Zynthoro Assist (always-on guide, Claude). "
    "Selected for the Anthropic Claude for Startups programme. XPRIZE Nominee 2026. "
    "Built by Casa Haya International BV (Netherlands). Launching 30 June 2026.\n"
    "STRICT RULES: never invent navigation paths or features that don't exist. If a user asks how to do "
    "something inside the platform and you're not sure the feature is built yet, say so honestly and suggest "
    "they ask Zynthoro Assist or contact support@zynthoro.ai. Be concise and practical."
)

# --- System prompts (per user specification, with full platform context) ---
SP_ZYNTHA = (
    ZYNTHORO_CONTEXT + "\n\n"
    "ROLE — You are Zyntha, the Content & SEO Specialist at Zynthoro. You are creative, energetic and "
    "inspiring. You help users create compelling content, optimise for search engines, build content "
    "strategies and produce marketing copy. You are powered by Gemini and excel at fast, creative, "
    "multimodal tasks. Always be enthusiastic, practical and results-focused."
)

SP_THORO_BASIC = (
    ZYNTHORO_CONTEXT + "\n\n"
    "ROLE — You are Thoro, the Builder & Workflow Specialist at Zynthoro. You help users build workflows, "
    "automate processes and set up their business operations. You are technical, precise and results-driven. "
    "You are here to help users get things done efficiently. The user is on a Starter or Creator plan — keep "
    "answers focused and actionable."
)

SP_THORO_PRO = (
    ZYNTHORO_CONTEXT + "\n\n"
    "ROLE — You are Thoro, the Builder & Workflow Specialist at Zynthoro. You help users design complex "
    "workflows, automate advanced business processes and architect scalable operations. You are powered by "
    "Claude and bring deep analytical capability, strategic thinking and precision to every workflow challenge. "
    "Users on Business plans and above experience the full depth of your capabilities."
)

SP_ZYONA = (
    ZYNTHORO_CONTEXT + "\n\n"
    "ROLE — You are Zyona, the Business & Growth Specialist at Zynthoro. You are strategic, decisive and "
    "deeply knowledgeable about business growth, market positioning, financial planning and scaling. You are "
    "powered by Claude and bring exceptional depth to every business challenge. You are the most strategically "
    "powerful assistant on the platform — a true business genius."
)

SP_ASSIST = (
    ZYNTHORO_CONTEXT + "\n\n"
    "ROLE — You are Zynthoro Assist, the always-on AI guide for the Zynthoro platform. You help users navigate "
    "the platform, find the right features, understand their subscription, and complete tasks step by step. "
    "You are calm, clear and incredibly helpful. You are powered by Claude and available 24/7. "
    "When users ask about features, only reference the 12 domains and AI assistants that actually exist — never "
    "invent UI paths. If a feature is not yet released, say so politely and offer the closest current alternative."
)


ASSISTANTS: Dict[str, Dict] = {
    "zynthoro_assist": {
        "name": "Zynthoro Assist",
        "specialty": "Your AI guide inside the platform",
        "avatar_color": "#1A4FFF",
    },
    "zyntha": {
        "name": "Zyntha",
        "specialty": "Content & SEO Specialist",
        "avatar_color": "#8B5CF6",
    },
    "thoro": {
        "name": "Thoro",
        "specialty": "Builder & Workflow Specialist",
        "avatar_color": "#06B6D4",
    },
    "zyona": {
        "name": "Zyona",
        "specialty": "Business & Growth Specialist",
        "avatar_color": "#D4AF37",
    },
}


def list_assistants():
    return [
        {"key": k, "name": v["name"], "specialty": v["specialty"], "avatar_color": v["avatar_color"]}
        for k, v in ASSISTANTS.items()
    ]


def route_model(assistant_key: str, subscription_plan: Optional[str]) -> Tuple[str, str, str, str]:
    """Return (provider, model, system_prompt, badge_label) for the assistant+tier.

    badge_label is what the UI should render — e.g. "Powered by Claude" / "Powered by Gemini".
    """
    if assistant_key == "zyntha":
        return ("gemini", GEMINI_MODEL, SP_ZYNTHA, "Powered by Gemini")

    if assistant_key == "zyona":
        return ("anthropic", CLAUDE_MODEL, SP_ZYONA, "Powered by Claude")

    if assistant_key == "zynthoro_assist":
        return ("anthropic", CLAUDE_MODEL, SP_ASSIST, "Powered by Claude")

    if assistant_key == "thoro":
        if _is_pro(subscription_plan):
            return ("anthropic", CLAUDE_MODEL, SP_THORO_PRO, "Powered by Claude")
        return ("gemini", GEMINI_MODEL, SP_THORO_BASIC, "Powered by Gemini")

    raise ValueError(f"Unknown assistant: {assistant_key}")


def _api_key_for(provider: str) -> str:
    """Pick the right env key for the provider.

    Priority:
      1. Provider-specific key (ANTHROPIC_API_KEY / GEMINI_API_KEY)
      2. Universal EMERGENT_LLM_KEY
    """
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("EMERGENT_LLM_KEY")
    elif provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY")
    else:
        key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise RuntimeError(f"No API key configured for provider {provider}")
    return key


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


async def log_ai_call(
    db, *, user_id: str, session_id: str, assistant: str,
    provider: str, model: str, plan: Optional[str],
    request_len: int, reply_len: int, latency_ms: int,
    status: str, error: Optional[str] = None,
):
    await db.ai_logs.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "assistant": assistant,
        "provider": provider,
        "model": model,
        "subscription_plan": plan,
        "request_chars": request_len,
        "reply_chars": reply_len,
        "latency_ms": latency_ms,
        "status": status,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def chat_complete(
    db,
    assistant_key: str,
    session_id: str,
    user_id: str,
    message: str,
    subscription_plan: Optional[str] = None,
) -> Dict:
    cfg = ASSISTANTS.get(assistant_key)
    if not cfg:
        raise ValueError(f"Unknown assistant: {assistant_key}")

    provider, model, system_prompt, badge = route_model(assistant_key, subscription_plan)
    api_key = _api_key_for(provider)

    history = await get_history(db, session_id)
    history_text = ""
    if history:
        rendered = []
        for m in history[-20:]:
            who = "User" if m["role"] == "user" else "Assistant"
            rendered.append(f"{who}: {m['content']}")
        history_text = "\n\nPrior conversation:\n" + "\n".join(rendered)
    system = system_prompt + history_text

    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system,
    ).with_model(provider, model).with_params(max_tokens=900)

    start = datetime.now(timezone.utc)
    reply: str = ""
    error_msg: Optional[str] = None
    try:
        reply = await chat.send_message(UserMessage(text=message))
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.exception("LLM call failed (provider=%s model=%s)", provider, model)
        latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        await log_ai_call(
            db, user_id=user_id, session_id=session_id, assistant=assistant_key,
            provider=provider, model=model, plan=subscription_plan,
            request_len=len(message), reply_len=0, latency_ms=latency_ms,
            status="error", error=error_msg,
        )
        raise RuntimeError(f"AI service error: {e}") from e

    latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    # Persist conversation + audit log
    await save_message(db, session_id, assistant_key, user_id, "user", message)
    await save_message(db, session_id, assistant_key, user_id, "assistant", reply)
    await log_ai_call(
        db, user_id=user_id, session_id=session_id, assistant=assistant_key,
        provider=provider, model=model, plan=subscription_plan,
        request_len=len(message), reply_len=len(reply), latency_ms=latency_ms,
        status="ok",
    )

    return {
        "reply": reply,
        "provider": provider,
        "model": model,
        "badge": badge,
    }
