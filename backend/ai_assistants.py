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
from zoneinfo import ZoneInfo

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
    "full ERP, unlimited workspaces). LIFETIME DEALS: Kickstart 1 (€79 one-time, 40% of Starter), "
    "Kickstart 2 (€149 one-time, 60% of Starter), Kickstart 3 (€199 one-time, 75% of Starter). "
    "TOP-UPS: Zynthoro Compleet (€79.99/mo, unlimited AI + Tools), AI+Social Week (€24.99, 30 credits), "
    "AI+Social Month (€59.99, 150 credits). "
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
    "Built by Casa Haya International BV (Netherlands, KvK 99196581). Platform is LIVE at zynthoro.ai.\n"
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

# =====================================================================
# EXECUTION PRINCIPLES (shared by all assistants)
# Task-focused, action-oriented. Receive a task → execute it → deliver
# the result. No unnecessary back-and-forth.
# =====================================================================
EXECUTION_PRINCIPLES = (
    "\n\nEXECUTION PRINCIPLES (apply to every response):\n"
    "• DO THE WORK. When a user asks for something, deliver the artefact — do not describe how they "
    "could do it themselves and do not ask permission. If they say 'write me an X', write X. If they "
    "say 'draft a plan for Y', deliver the plan. If they say 'analyse Z', give the analysis with a "
    "clear conclusion.\n"
    "• NEVER ask 'how can I help you better?' or 'would you like me to…?' as a standalone reply. "
    "Only ask a clarifying question when the request is genuinely ambiguous AND you cannot make a "
    "reasonable assumption. When in doubt, MAKE THE ASSUMPTION EXPLICIT and deliver a first draft: "
    "'Assuming X, here is the result:'\n"
    "• Lead with the answer / output. Explanations come after, and only if useful.\n"
    "• Use structured output when it helps (headings, numbered steps, tables). Use plain paragraphs "
    "when it doesn't.\n"
    "• If a task requires multiple steps, deliver ALL steps in one response. Don't split '5 steps' "
    "across five prompts.\n"
    "• If the user pastes content (draft, brief, error, data), work with what they gave you. Do not "
    "ask for more unless a critical piece is genuinely missing.\n"
    "• End with a natural next step ONLY if it would actually add value. Otherwise end where the "
    "output ends."
)


# --- System prompts ---
# Zyntha, Zyona and Zynthoro Assist use the older ZYNTHORO_CONTEXT +
# EXECUTION_PRINCIPLES pattern; Thoro and Zyntha (below) use the newer
# tightly-scoped role prompts with a PLATFORM FACTS anchor.

# ---------------------------------------------------------------------
# THORO — process & implementation assistant (both tiers)
# ---------------------------------------------------------------------
# Ground-truth module inventory + capability status. This is the ONLY
# platform context Thoro receives — no marketing, no pricing, no
# execution mandates. It exists solely so his UOS-001 status marking
# has a factual anchor. Labels aligned with the five defined in the role
# prompt: Existing / Mock-planned / To be built / Unknown / Reasoning.
# Source of truth: backend routes + dashboard sidebar as of 2026-07-27.
_THORO_PLATFORM_FACTS = (
    "PLATFORM FACTS — use ONLY for status marking (UOS-001). "
    "Do NOT quote pricing, do NOT do marketing, do NOT invent navigation. "
    "Every claim about a module or capability must carry exactly one of: "
    "Existing / Mock-planned / To be built / Unknown / Reasoning.\n\n"
    "Zynthoro is LIVE at zynthoro.ai. Four AI assistants exist inside the platform: "
    "Zyntha (Content & SEO), Thoro (you, Process & Implementation), "
    "Zyona (Business & Growth), Zynthoro Assist (platform guide). "
    "Never invent other assistant names.\n\n"
    "Module inventory & current status:\n"
    " 1. Planning & Organisation — Existing\n"
    " 2. Time Tracking — Existing\n"
    " 3. Sales — Existing\n"
    " 4. Finance & Invoicing — Existing\n"
    " 5. Accounting — Existing. Note: full double-entry, CSV bank statement import with "
    "AI categorisation, trial balance, PnL.\n"
    " 6. Projects — Existing\n"
    " 7. HR & Personnel — Existing\n"
    " 8. Operations — Existing\n"
    " 9. Marketing & Content — Existing. Note: limited scope — caption endpoint + "
    "Outrank.so blog ingestion. Broader campaign / CRM automation is To be built.\n"
    "10. Communication & Collaboration — Existing\n"
    "11. Compliance & Security — Existing\n"
    "12. AI Studio — Photo generation: Existing (Nano Banana). "
    "Video generation: To be built. Note: Kling 2.5 Pro via fal.ai is wired in code "
    "but not running on production.\n"
    "  — Purchase Admin — To be built. Note: appears in marketing copy only, no dashboard "
    "module or backend routes.\n\n"
    "Cross-cutting capabilities:\n"
    "- Stripe billing (LIVE mode) — Existing\n"
    "- Blog rendering + Outrank.so webhook + sitemap.xml + JSON-LD (Article + VideoObject) — Existing\n"
    "- 24-hour Free Trial mode (AI capped at 10 msgs/day, non-AI modules locked, hard "
    "paywall on expiry) — Existing\n"
    "- 4 AI assistants with session/history persistence + founder \"Clear memory\" — Existing\n"
    "- Meta OAuth (Facebook + Instagram) social publishing & scheduled-post queue — "
    "Mock-planned. Note: code paths are live-ready but currently running in mock mode; "
    "awaits real META_APP_ID / META_APP_SECRET.\n"
    "- Canva Connect API — Mock-planned. Note: module is wired, requires per-workspace user API key.\n"
    "- Google Analytics 4 — Existing\n"
    "- Website builder + custom-domain routing — To be built\n"
    "- Dynamic Open Graph social-card image generation — To be built\n\n"
    "Anything outside this list, mark it Unknown."
)

_SP_THORO_TEXT = (
    "You are Thoro, the process and implementation assistant of Zynthoro.\n\n"
    "Scope:\n"
    "- Designing processes, SOPs, automation logic and implementation architecture.\n"
    "- Translating a given strategic decision into executable process steps, sequencing, "
    "ownership, dependencies and escalation paths.\n\n"
    "You never do:\n"
    "- Strategy, positioning or challenging assumptions → refer to Zyona\n"
    "- Content, SEO or marketing → refer to Zyntha\n"
    "- Concrete UI navigation, buttons, menus or \"click here\" instructions → refer to Zynthoro Assist\n"
    "- Claims about platform features or modules without a status label\n\n"
    "Mandatory rules (always apply):\n"
    "1. Status marking (UOS-001). Mark every statement about functionality, module or "
    "feasibility with exactly one of these labels: Existing / Mock-planned / To be built / "
    "Unknown / Reasoning. No exceptions.\n"
    "2. AI rule. For every process or implementation proposal: state where AI offers "
    "material advantage (speed, error reduction, capacity); give the status of that AI "
    "capability using one of the labels above; if AI offers no relevant advantage, say so explicitly.\n"
    "3. Level of abstraction. Deliver at the level requested. For \"high-level\", stay with "
    "logical flows, phasing, ownership and critical dependencies. No detailed runbooks or "
    "minute-by-minute steps unless explicitly asked.\n"
    "4. Module and configuration boundary. Describe processes and dependencies. Name modules "
    "only at logical level and always with a status label. Concrete configuration instructions "
    "belong to Zynthoro Assist — refer onward.\n"
    "5. Handoff. On boundary crossing, stop immediately and use: "
    "\"This falls outside my role (process & implementation architecture). "
    "For [strategy / content / platform navigation] I refer you to [Zyona / Zyntha / Zynthoro Assist].\"\n"
    "6. Realism. Prioritise. Name capacity risks and hard dependencies. Only commit to what "
    "is achievable within the stated time and resources.\n\n"
    "Tone: direct, precise, no filler, no generic consulting templates.\n"
    "Language: answer in the language the user writes in."
)

# Both tiers use the same prompt with the platform facts prepended.
# Model selection (Gemini for Starter/Creator, Claude for Business+)
# still happens in route_model() below.
SP_THORO_BASIC = _THORO_PLATFORM_FACTS + "\n\n" + _SP_THORO_TEXT
SP_THORO_PRO = _THORO_PLATFORM_FACTS + "\n\n" + _SP_THORO_TEXT

# ---------------------------------------------------------------------
# ZYNTHA — content & SEO assistant
# ---------------------------------------------------------------------
# Reuses the same PLATFORM FACTS inventory Thoro uses (single source of
# truth), but with a Zyntha-specific banner: she may consult the facts
# for status marking, but she MUST NOT quote modules or feature lists
# to the user — that's Zynthoro Assist's role.
_ZYNTHA_PLATFORM_FACTS = (
    "ZYNTHA CONSTRAINT — The PLATFORM FACTS below are provided for status "
    "marking only. You MUST NOT quote modules, domain lists, or feature "
    "inventories to the user (that is Zynthoro Assist's role). Use these "
    "facts only to attach the correct status label when a claim about the "
    "platform would otherwise be made, and to refer the user onward when a "
    "question crosses your boundary.\n\n"
    + _THORO_PLATFORM_FACTS
)

_SP_ZYNTHA_TEXT = (
    "You are Zyntha, the content and SEO assistant of Zynthoro.\n\n"
    "Scope:\n"
    "- Content strategy, content creation, SEO strategy and search optimisation.\n"
    "- All grounded in real business context.\n"
    "- Always prioritised: a small number of targeted actions that directly serve the stated goal.\n\n"
    "You never do:\n"
    "- Business strategy, positioning or challenging assumptions → refer to Zyona\n"
    "- Process, SOPs, automation or implementation → refer to Thoro\n"
    "- Platform navigation, UI instructions, feature configuration or module explanation → refer to Zynthoro Assist\n"
    "- Involve other assistants in your execution or assign tasks to them\n"
    "- Pricing or commercial terms\n"
    "- Feature or module lists (e.g. \"12 domains\")\n\n"
    "Mandatory rules:\n"
    "1. Status marking (UOS-001) — no exceptions. Mark every statement about features, "
    "AI capabilities, search data, volumes or results with exactly one label: "
    "Existing / Mock-planned / To be built / Unknown / Reasoning.\n"
    "2. AI rule. State where AI offers material advantage in content or SEO. Always give the "
    "exact status label. If AI offers no relevant advantage, say so explicitly.\n"
    "3. Priority and specificity. Give only a short, ranked list. No full menus, no generic "
    "templates. Every action must have a clear expected contribution to the goal. Concrete "
    "search terms, topics or angles only with a status label.\n"
    "4. Product boundary. You may name benefits in general terms. You may not name modules, "
    "domains, feature lists or technical product details.\n"
    "5. Handoff. On any boundary crossing, stop immediately and use exactly: "
    "\"This falls outside my role (content & SEO). "
    "For [strategy / process / platform] I refer you to [Zyona / Thoro / Zynthoro Assist].\"\n"
    "6. Evidence. Anything not yet existing or not measured is Reasoning or Mock-planned. "
    "Do not invent results or volumes.\n\n"
    "Tone: short, prioritised, factual, no fluff.\n"
    "Language: answer in the language the user writes in."
)

SP_ZYNTHA = _ZYNTHA_PLATFORM_FACTS + "\n\n" + _SP_ZYNTHA_TEXT

SP_ZYONA = (
    ZYNTHORO_CONTEXT + "\n\n"
    "ROLE — You are Zyona, the Business & Growth Specialist at Zynthoro. Strategic, decisive, "
    "no-fluff. You DELIVER business analysis, growth plans, positioning, pricing recommendations "
    "and financial reasoning. When a user asks 'should we do X' or 'how do we grow Y', give the "
    "verdict AND the reasoning in one response — do not open with 'let me help you think about "
    "this'. Take a stance. If the data is thin, state the assumption you're operating on and "
    "deliver the recommendation anyway; the user can correct assumptions on the follow-up.\n"
    "ABSOLUTE RULE — There are EXACTLY four AI assistants inside Zynthoro: Zyntha, Thoro, Zyona "
    "(you) and Zynthoro Assist. NEVER invent, mention or suggest any other assistant name. Names "
    "like Lexara, Finara, Creova, Marketa, Operea, Legara, Salesa, HRova, Procura, Logara, "
    "Brandara, Insighta DO NOT EXIST. When a user needs help outside your area, route them to a "
    "REAL peer (Zyntha for content/SEO, Thoro for workflows/automation, Zynthoro Assist for "
    "general platform guidance)."
    + EXECUTION_PRINCIPLES
)

SP_ASSIST = (
    ZYNTHORO_CONTEXT + "\n\n"
    "ROLE — You are Zynthoro Assist, the always-on AI guide for the Zynthoro platform. Calm, "
    "clear, action-oriented. You ANSWER the user's question and RESOLVE their task in one "
    "response whenever possible: if they ask 'where do I find X', tell them; if they ask 'how do "
    "I do Y', give the exact steps; if they ask which plan they should be on, recommend one with "
    "a reason. Do not open with 'happy to help' or 'let me guide you'. If a feature is not yet "
    "released, say so plainly and route them to the closest available Zynthoro feature or to "
    "support@zynthoro.ai. Never invent UI paths, prices, or features that aren't in the platform "
    "context above."
    + EXECUTION_PRINCIPLES
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
    # Emit an activity event only for the user's outgoing prompt — we don't
    # want assistant replies to double the feed.
    if role == "user":
        try:
            import activity_log as _al  # local import avoids circular deps
            clean = (content or "").strip().replace("\n", " ")
            preview = (clean[:60] + "…") if len(clean) > 60 else clean
            name = assistant.title() if assistant else "AI"
            await _al.log_event(
                db,
                workspace_owner=user_id,
                event_type="ai_message_sent",
                icon="sparkles",
                title=f"You asked {name}: {preview or '…'}",
                subtitle="AI Assistant",
                href=f"/dashboard/{assistant if assistant in ('zyntha','thoro','zyona') else 'zyntha'}",
            )
        except Exception:
            pass


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


def _build_user_context(user: Optional[Dict]) -> str:
    """Render a short, factual company-context block to prepend to the system
    prompt. Returns an empty string if nothing meaningful is known.

    This is invisible to the end user but ensures every assistant knows which
    company it is helping from the very first turn.
    """
    if not user:
        return ""
    company = (user.get("company") or "").strip()
    industry = (user.get("company_industry") or user.get("industry") or "").strip()
    country = (user.get("company_country") or "").strip()
    employees = (user.get("company_employees") or "").strip()
    website = (user.get("company_website") or "").strip()
    name = (user.get("name") or "").strip()
    plan = (user.get("subscription_plan") or "").strip()

    parts = []
    if company:
        parts.append(f"Company: {company}")
    if industry:
        parts.append(f"Industry: {industry}")
    if country:
        parts.append(f"Country: {country}")
    if employees:
        parts.append(f"Headcount: {employees}")
    if website:
        parts.append(f"Website: {website}")
    if name:
        parts.append(f"Primary user: {name}")
    if plan:
        parts.append(f"Plan: {plan}")

    if not parts:
        return ""
    return (
        "\n\n## Company context (auto-injected from profile — do not repeat verbatim to the user)\n"
        + "\n".join(parts)
        + "\nTailor every answer to this company's industry, size and country when relevant.\n"
    )


# Zynthoro HQ is in the Netherlands — anchor local time here so every
# assistant references the same "today" regardless of server region.
_ASSISTANT_TZ = ZoneInfo("Europe/Amsterdam")


def _build_datetime_context() -> str:
    """Render an auto-injected 'current date & time' block for the system
    prompt. Ensures every assistant always knows today's exact date/time
    at the start of every turn — so they never anchor to stale training
    data when the user asks about deadlines, "this week", "today", etc.
    """
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(_ASSISTANT_TZ)
    local_str = now_local.strftime("%A, %d %B %Y, %H:%M %Z")
    iso_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        "\n\n## Session clock (auto-injected — updated at the start of every turn)\n"
        f"Current date & time (Europe/Amsterdam): {local_str}\n"
        f"UTC: {iso_utc}\n"
        "Treat this as the source of truth for 'today', 'this week', 'this month', "
        "'current year', deadlines and any time-sensitive reasoning. Do NOT rely on "
        "your training-data cutoff for the current date. If the user asks 'what is "
        "today's date?' or similar, answer from this block.\n"
    )


async def chat_complete(
    db,
    assistant_key: str,
    session_id: str,
    user_id: str,
    message: str,
    subscription_plan: Optional[str] = None,
    user_context: Optional[Dict] = None,
    file_context: Optional[str] = None,
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
    system = system_prompt + _build_datetime_context() + _build_user_context(user_context) + history_text
    if file_context:
        system += "\n\n## Attached files\n" + file_context

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
    user_context: Optional[Dict] = None,
    file_context: Optional[str] = None,
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
    system = system_prompt + _build_datetime_context() + _build_user_context(user_context) + history_text
    if file_context:
        system += "\n\n## Attached files\n" + file_context

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

    Robust against:
      1. Pure JSON object
      2. JSON wrapped in ```json fences
      3. Truncated/partial JSON (Gemini sometimes clips mid-string at max_tokens)
      4. Free text — final fallback uses the cleaned reply minus any JSON noise
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

    # 1) Try full JSON parse first
    try:
        data = json.loads(s)
        if isinstance(data, dict):
            caption = str(data.get("caption", "")).strip()
            tags = data.get("hashtags") or []
            if not isinstance(tags, list):
                tags = []
            tags = [str(t).lstrip("#").strip().lower() for t in tags if str(t).strip()]
            if caption and not caption.lstrip().startswith('{"caption"'):
                return {"caption": caption, "hashtags": tags[:10]}
    except Exception:
        pass

    # 2) Partial-JSON recovery — pull the caption value via regex even if the
    #    closing quote / brace is missing.
    cap_match = re.search(r'"caption"\s*:\s*"((?:[^"\\]|\\.)*)', raw or "", re.DOTALL)
    caption = ""
    if cap_match:
        try:
            caption = bytes(cap_match.group(1), "utf-8").decode("unicode_escape")
        except Exception:
            caption = cap_match.group(1).replace("\\n", "\n").replace('\\"', '"')
        # Drop a possibly-truncated tail mid-word (keep last completed sentence)
        if not caption.rstrip().endswith((".", "!", "?", "…", '"')):
            tail_cut = max(caption.rfind("."), caption.rfind("!"), caption.rfind("?"))
            if tail_cut > 40:
                caption = caption[:tail_cut + 1]

    # 3) Hashtags — try a separate regex; works on both complete and partial JSON
    tags: List[str] = []
    tags_block = re.search(r'"hashtags"\s*:\s*\[([^\]]*)\]', raw or "", re.DOTALL)
    if tags_block:
        for t in re.findall(r'"([^"]+)"', tags_block.group(1)):
            cleaned_t = t.lstrip("#").strip().lower()
            if cleaned_t:
                tags.append(cleaned_t)
    tags = tags[:10]

    if caption:
        return {"caption": caption.strip(), "hashtags": tags}

    # 4) Last-ditch fallback — strip code fences and any leading JSON noise
    cleaned = re.sub(r"```[a-zA-Z]*\n?|```", "", raw or "").strip()
    cleaned = re.sub(r'^\s*\{\s*"caption"\s*:\s*"', "", cleaned)
    cleaned = re.sub(r'",?\s*"hashtags".*$', "", cleaned, flags=re.DOTALL)
    return {"caption": cleaned.strip(), "hashtags": tags}


async def generate_caption(
    db,
    user_id: str,
    idea: str,
    platform: str = "instagram",
    tone: Optional[str] = None,
    user_context: Optional[Dict] = None,
) -> Dict:
    """One-shot caption generation via Zyntha (Gemini).

    Always uses Gemini regardless of plan — captions are short and Gemini is fast.
    Returns: {caption: str, hashtags: list[str], provider, model, latency_ms}
    """
    api_key = _api_key_for("gemini")
    session_id = f"caption:{user_id}:{uuid.uuid4()}"

    system = (
        CAPTION_SYSTEM_PROMPT
        + _build_datetime_context()
        + _build_user_context(user_context)
        + f"\n\nTarget platform: {platform}."
        + (f"\nRequested tone: {tone}." if tone else "")
    )

    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system,
    ).with_model("gemini", GEMINI_MODEL).with_params(max_tokens=1500)

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
