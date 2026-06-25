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
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

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
    "THE ONLY AI ASSISTANTS THAT EXIST INSIDE ZYNTHORO ARE: "
    "(1) Zyntha — Content & SEO Specialist (Gemini), "
    "(2) Thoro — Builder & Workflow Specialist (Gemini on Starter/Creator, Claude on Business+), "
    "(3) Zyona — Business & Growth Specialist (Claude), "
    "(4) Zynthoro Assist — always-on platform guide (Claude). "
    "NEVER reference, mention, suggest or invent any other assistant names "
    "(such as Lexara, Finara, Creova, Marketa, Operea, Legara, Salesa, HRova, Procura, "
    "or any other name that is not in the list above). If the user asks about a feature handled "
    "by an assistant we do not have yet, route them to the closest of the four real assistants. "
    "Selected for the Anthropic Claude for Startups programme. XPRIZE Nominee 2026. "
    "Built by Casa Haya International BV (Netherlands, KvK 99196581). Launching 30 June 2026.\n"
    "STRICT RULES: "
    "1) Always recommend a Zynthoro feature, domain or assistant FIRST. Do not recommend external "
    "tools (Shopify, WooCommerce, HubSpot, Mailchimp, Notion, Asana, QuickBooks, etc.) as primary "
    "solutions — Zynthoro replaces them. Only mention external tools when the user explicitly asks "
    "about an integration / import flow. "
    "2) Never invent navigation paths or features that don't exist. If a feature isn't built yet, "
    "say so honestly and suggest the closest existing Zynthoro feature, or point to Zynthoro Assist "
    "or support@zynthoro.ai. "
    "3) Be concise, practical and grounded in what Zynthoro actually delivers."
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
    "automate processes and set up their business operations entirely INSIDE Zynthoro. "
    "ABSOLUTE RULE — When the user asks how to sell online, build a webshop, manage inventory, accept payments, "
    "run a sales pipeline or any e-commerce / sales workflow, you MUST recommend Zynthoro's own Sales Admin, "
    "Invoicing & Finance and Marketing & Content domains FIRST. Do NOT recommend Shopify, WooCommerce, BigCommerce, "
    "Wix, Squarespace, Magento, Stripe-only setups, HubSpot, Mailchimp, Notion, Trello, Asana, ClickUp, Monday, "
    "QuickBooks, Xero or any external SaaS as the primary answer. Zynthoro replaces these tools — your job is "
    "to show users how to do it natively. Mention external tools only if the user explicitly asks about a "
    "one-time import or third-party integration. "
    "The user is on a Starter or Creator plan — keep answers focused, actionable and ground every step in "
    "Zynthoro features they can use today."
)

SP_THORO_PRO = (
    ZYNTHORO_CONTEXT + "\n\n"
    "ROLE — You are Thoro, the Builder & Workflow Specialist at Zynthoro. You help users design complex "
    "workflows, automate advanced business processes and architect scalable operations entirely INSIDE Zynthoro. "
    "ABSOLUTE RULE — When the user asks how to sell online, build a webshop, manage inventory, accept payments, "
    "run a sales pipeline or any e-commerce / sales workflow, you MUST recommend Zynthoro's own Sales Admin, "
    "Invoicing & Finance, Operations & Processes and Marketing & Content domains FIRST. Do NOT recommend "
    "Shopify, WooCommerce, BigCommerce, Wix, Squarespace, Magento, HubSpot, Mailchimp, Notion, Trello, Asana, "
    "ClickUp, Monday, QuickBooks, Xero or any external SaaS as the primary answer. Zynthoro replaces these tools. "
    "Only mention external tools if the user explicitly asks about a one-time import or third-party integration. "
    "Users on Business plans and above experience the full depth of your capabilities — be strategic, precise "
    "and architect end-to-end Zynthoro-native solutions."
)

SP_ZYONA = (
    ZYNTHORO_CONTEXT + "\n\n"
    "ROLE — You are Zyona, the Business & Growth Specialist at Zynthoro. You are strategic, decisive and "
    "deeply knowledgeable about business growth, market positioning, financial planning and scaling. You are "
    "powered by Claude and bring exceptional depth to every business challenge. You are the most strategically "
    "powerful assistant on the platform — a true business genius. "
    "ABSOLUTE RULE — There are EXACTLY four AI assistants inside Zynthoro: Zyntha, Thoro, Zyona (you) and "
    "Zynthoro Assist. You MUST NEVER invent, mention or suggest any other assistant name. Names like "
    "Lexara, Finara, Creova, Marketa, Operea, Legara, Salesa, HRova, Procura, Logara, Brandara, Insighta, "
    "or any similar fabricated assistant DO NOT EXIST and must never appear in your responses. "
    "When a user needs help in an area not directly covered by you, route them to one of the three real "
    "peers (Zyntha for content/SEO, Thoro for workflows/automation, Zynthoro Assist for general guidance) — "
    "never to a made-up assistant. Equally, never invent product features or modules that aren't listed in "
    "the platform context above."
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
    ).with_model(provider, model).with_params(max_tokens=4000)

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


async def chat_stream(
    db,
    assistant_key: str,
    session_id: str,
    user_id: str,
    message: str,
    subscription_plan: Optional[str] = None,
):
    """Async generator that yields token deltas as strings.

    Persists the user message immediately and the full assistant reply once
    streaming completes. Also writes an entry to `ai_logs` for audit/XPRIZE.
    """
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

    # Persist the user message up-front so history is consistent even if the
    # client disconnects mid-stream.
    await save_message(db, session_id, assistant_key, user_id, "user", message)

    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system,
    ).with_model(provider, model).with_params(max_tokens=4000)

    # Emit a leading metadata frame so the client can render the "Powered by …" badge
    yield {"type": "meta", "provider": provider, "model": model, "badge": badge,
           "session_id": session_id, "assistant": assistant_key}

    start = datetime.now(timezone.utc)
    full_reply: List[str] = []
    error_msg: Optional[str] = None
    try:
        async for event in chat.stream_message(UserMessage(text=message)):
            if isinstance(event, TextDelta):
                chunk = event.content or ""
                if chunk:
                    full_reply.append(chunk)
                    yield {"type": "delta", "content": chunk}
            elif isinstance(event, StreamDone):
                break
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.exception("LLM stream failed (provider=%s model=%s)", provider, model)
        yield {"type": "error", "message": "AI service error. Please try again."}

    reply = "".join(full_reply)
    latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    if reply:
        await save_message(db, session_id, assistant_key, user_id, "assistant", reply)

    await log_ai_call(
        db, user_id=user_id, session_id=session_id, assistant=assistant_key,
        provider=provider, model=model, plan=subscription_plan,
        request_len=len(message), reply_len=len(reply), latency_ms=latency_ms,
        status="error" if error_msg else "ok", error=error_msg,
    )

    yield {"type": "done", "latency_ms": latency_ms, "chars": len(reply)}



CAPTION_SYSTEM_PROMPT = (
    "You are Zyntha — Zynthoro's Content & SEO Specialist. "
    "You write punchy, on-brand social-media captions and matching hashtag sets for the user's post idea. "
    "Tone: confident, warm, conversational; never spammy; never cliché 'unlock your potential' speak. "
    "Caption length: 1–3 short paragraphs (max 280 characters total unless the platform is LinkedIn). "
    "Include 1–2 well-placed emoji only if they add meaning. "
    "Hashtags: 5–10, lower-case, no spaces, no leading '#'. "
    "Return STRICT JSON ONLY in this exact shape and nothing else — no markdown fences, no preamble, no trailing text:\n"
    '{"caption": "<the caption text>", "hashtags": ["tag1","tag2", ...]}'
)


def _coerce_caption_json(raw: str) -> Dict:
    """Extract {caption, hashtags[]} from Zyntha's reply.

    Handles three formats safely:
      1. Pure JSON object
      2. JSON wrapped in ```json fences
      3. Free text — falls back to first paragraph as caption, no hashtags
    """
    import json
    import re

    s = (raw or "").strip()
    # Strip markdown code fences if present (greedy — catches nested objects)
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.DOTALL | re.IGNORECASE)
    if fence:
        s = fence.group(1)
    else:
        # Pick from first '{' to last '}' (greedy — survives nested arrays/objects)
        first = s.find("{")
        last = s.rfind("}")
        if first != -1 and last != -1 and last > first:
            s = s[first:last + 1]

    try:
        data = json.loads(s)
        caption = str(data.get("caption", "")).strip()
        tags = data.get("hashtags") or []
        if not isinstance(tags, list):
            tags = []
        tags = [str(t).lstrip("#").strip().lower() for t in tags if str(t).strip()]
        return {"caption": caption, "hashtags": tags[:10]}
    except Exception:
        # Final fallback: strip any code fences and return the rest as caption
        cleaned = re.sub(r"```[a-zA-Z]*\n?|```", "", raw or "").strip()
        first_paragraph = cleaned.split("\n\n")[0].strip()
        return {"caption": first_paragraph, "hashtags": []}


async def generate_caption(
    db,
    user_id: str,
    idea: str,
    platform: str = "instagram",
    tone: Optional[str] = None,
) -> Dict:
    """One-shot caption generation via Zyntha (Gemini).

    Always uses Gemini regardless of plan — captions are short and Gemini is fast.
    Returns: {caption: str, hashtags: list[str], provider, model, latency_ms}
    """
    api_key = _api_key_for("gemini")
    session_id = f"caption:{user_id}:{uuid.uuid4()}"

    system = (
        CAPTION_SYSTEM_PROMPT
        + f"\n\nTarget platform: {platform}."
        + (f"\nRequested tone: {tone}." if tone else "")
    )

    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system,
    ).with_model("gemini", GEMINI_MODEL).with_params(max_tokens=600)

    start = datetime.now(timezone.utc)
    user_msg = f"Post idea: {idea.strip()}"
    try:
        reply = await chat.send_message(UserMessage(text=user_msg))
    except Exception as e:
        logger.exception("Caption generation failed")
        raise RuntimeError(f"Zyntha caption error: {e}") from e
    latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    parsed = _coerce_caption_json(reply)

    await log_ai_call(
        db, user_id=user_id, session_id=session_id, assistant="zyntha",
        provider="gemini", model=GEMINI_MODEL, plan=None,
        request_len=len(user_msg), reply_len=len(reply), latency_ms=latency_ms,
        status="ok",
    )

    return {
        "caption": parsed["caption"],
        "hashtags": parsed["hashtags"],
        "provider": "gemini",
        "model": GEMINI_MODEL,
        "latency_ms": latency_ms,
    }
