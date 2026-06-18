import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Send, Loader2, Sparkles, BrainCircuit, TrendingUp } from "lucide-react";
import { API, formatApiError } from "@/contexts/AuthContext";
import { toast } from "sonner";

const CONFIGS = {
  zyntha: {
    name: "Zyntha",
    specialty: "Content & SEO Specialist",
    description: "Creative, energetic, inspiring. Ask Zyntha for blog posts, captions, ad copy and SEO ideas.",
    color: "#8B5CF6",
    bg: "linear-gradient(135deg,#8B5CF6 0%,#6D28D9 100%)",
    icon: Sparkles,
    starters: [
      "Write 5 LinkedIn captions for our launch",
      "Draft an SEO blog post on AI ERP for SMEs",
      "Repurpose this idea across 4 formats",
    ],
  },
  thoro: {
    name: "Thoro",
    specialty: "Builder & Workflow Specialist",
    description: "Technical, precise, results-driven. Use Thoro to design automations, SOPs and funnels.",
    color: "#06B6D4",
    bg: "linear-gradient(135deg,#06B6D4 0%,#0E7490 100%)",
    icon: BrainCircuit,
    starters: [
      "Build a customer onboarding workflow",
      "Write an SOP for invoice approval",
      "Plan a 3-step product funnel",
    ],
  },
  zyon: {
    name: "Zyon",
    specialty: "Business & Growth Specialist",
    description: "Strategic, business-focused, decisive. Talk to Zyon about growth, pricing and KPIs.",
    color: "#D4AF37",
    bg: "linear-gradient(135deg,#D4AF37 0%,#8a6e1d 100%)",
    icon: TrendingUp,
    starters: [
      "Outline a 90-day growth plan",
      "Build a sales script for first calls",
      "Which 3 KPIs should I track weekly?",
    ],
  },
};

export default function AssistantPage({ assistantKey }) {
  const cfg = CONFIGS[assistantKey];
  const Icon = cfg.icon;
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    setMessages([
      {
        role: "assistant",
        content: `Hi! I'm ${cfg.name}, your ${cfg.specialty.toLowerCase()}. What are we working on today?`,
      },
    ]);
    setSessionId(null);
    // eslint-disable-next-line
  }, [assistantKey]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const send = async (text) => {
    const value = (text ?? input).trim();
    if (!value || busy) return;
    if (!text) setInput("");
    setMessages((m) => [...m, { role: "user", content: value }]);
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/ai/chat`, {
        assistant: assistantKey,
        session_id: sessionId || undefined,
        message: value,
      });
      if (!sessionId) setSessionId(data.session_id);
      setMessages((m) => [...m, { role: "assistant", content: data.reply }]);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || `${cfg.name} is unavailable.`);
      setMessages((m) => [...m, { role: "assistant", content: "I had trouble responding. Please try again shortly." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid={`assistant-page-${assistantKey}`} className="max-w-4xl">
      <div className="flex items-start gap-4">
        <span
          className="w-14 h-14 rounded-2xl inline-flex items-center justify-center shrink-0 text-white shadow-md"
          style={{ background: cfg.bg }}
        >
          <Icon size={22} />
        </span>
        <div className="flex-1">
          <p className="zy-eyebrow mb-1.5" style={{ color: cfg.color }}>AI Assistant</p>
          <h1 className="text-[28px] font-bold tracking-tight">{cfg.name}</h1>
          <p className="text-[14.5px] text-[#555] mt-1">{cfg.description}</p>
        </div>
      </div>

      <div className="mt-7 bg-white border border-[#eee] rounded-2xl flex flex-col" style={{ minHeight: 480 }}>
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-3" data-testid={`${assistantKey}-messages`}>
          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[80%] text-[14px] leading-relaxed px-4 py-2.5 rounded-lg whitespace-pre-wrap ${
                m.role === "user" ? "ml-auto rounded-tr-sm text-white" : "rounded-tl-sm bg-[#F4F6FB]"
              }`}
              style={m.role === "user" ? { background: "#1A4FFF" } : {}}
            >
              {m.content}
            </div>
          ))}
          {busy && (
            <div className="flex items-center gap-2 text-[#888] text-[12.5px]">
              <Loader2 size={13} className="animate-spin" /> {cfg.name} is thinking…
            </div>
          )}
        </div>

        {messages.length <= 1 && (
          <div className="px-5 pb-3 flex flex-wrap gap-2">
            {cfg.starters.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="text-[12.5px] px-3 py-1.5 rounded-full border border-[#eee] hover:border-[#1A4FFF] hover:text-[#1A4FFF]"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <form
          onSubmit={(e) => { e.preventDefault(); send(); }}
          className="p-3 border-t border-[#eee] flex items-center gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Message ${cfg.name}…`}
            data-testid={`${assistantKey}-input`}
            className="flex-1 text-[14px] outline-none px-3 py-2.5 rounded-md border border-[#eee] focus:border-[#1A4FFF]"
          />
          <button type="submit" disabled={busy || !input.trim()} className="zy-btn-primary px-3.5 py-2.5 disabled:opacity-50" data-testid={`${assistantKey}-send`}>
            <Send size={15} />
          </button>
        </form>
      </div>
    </div>
  );
}
