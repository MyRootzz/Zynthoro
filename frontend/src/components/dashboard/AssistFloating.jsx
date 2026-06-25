import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Sparkles, X, Send, Loader2 } from "lucide-react";
import { ZyLogo } from "@/components/ZyLogo";
import { API, formatApiError } from "@/contexts/AuthContext";
import { toast } from "sonner";

export default function AssistFloating() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Hi! I'm Zynthoro Assist. Ask me anything about the platform or your account.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [poweredBy, setPoweredBy] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, open]);

  const send = async (e) => {
    e?.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/ai/chat`, {
        assistant: "zynthoro_assist",
        session_id: sessionId || undefined,
        message: text,
      });
      if (!sessionId) setSessionId(data.session_id);
      if (data.badge) setPoweredBy({ badge: data.badge, provider: data.provider });
      setMessages((m) => [...m, { role: "assistant", content: data.reply }]);
    } catch (err) {
      toast.error(formatApiError(err?.response?.data?.detail) || "Assistant is unavailable.");
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "I had trouble responding. Please try again shortly." },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        data-testid="assist-bubble"
        className={`fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full inline-flex items-center justify-center shadow-2xl transition-all ${open ? "scale-0 opacity-0" : "scale-100 opacity-100"}`}
        style={{ background: "#1A4FFF", color: "#fff" }}
        aria-label="Open Zynthoro Assist"
      >
        <Sparkles size={22} />
      </button>

      <div
        data-testid="assist-panel"
        className={`fixed bottom-6 right-6 z-40 w-[360px] max-w-[calc(100vw-2rem)] h-[520px] max-h-[80vh] rounded-2xl shadow-2xl border flex flex-col transition-all ${open ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4 pointer-events-none"}`}
        style={{ background: "#fff", borderColor: "#1A4FFF" }}
      >
        <div className="px-4 py-3 border-b border-[#eee] flex items-center gap-3" style={{ background: "#0A1628" }}>
          <ZyLogo size={15} />
          <div className="flex-1">
            <p className="text-[12.5px] font-semibold text-white">Zynthoro Assist</p>
            <p className="text-[10.5px] text-white/65">
              {poweredBy?.badge || "Powered by Claude AI"}
            </p>
          </div>
          <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white p-1" aria-label="Close" data-testid="assist-close">
            <X size={16} />
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3.5" data-testid="assist-messages">
          {messages.map((m, i) => (
            m.role === "user" ? (
              <div
                key={i}
                className="max-w-[85%] ml-auto text-[13.5px] leading-relaxed px-3.5 py-2.5 rounded-lg rounded-tr-sm text-white whitespace-pre-wrap"
                style={{ background: "#1A4FFF" }}
              >
                {m.content}
              </div>
            ) : (
              <div key={i} className="flex items-start gap-2 max-w-[92%]">
                <span
                  className="w-7 h-7 rounded-full inline-flex items-center justify-center shrink-0 text-[10px] font-extrabold tracking-[0.04em]"
                  style={{ background: "#0A1628", color: "#D4AF37", border: "1.5px solid #D4AF37" }}
                  aria-label="Zynthoro Assist"
                  data-testid="assist-msg-avatar"
                >
                  Z
                </span>
                <div className="text-[13.5px] leading-relaxed px-3.5 py-2.5 rounded-lg rounded-tl-sm bg-[#F4F6FB] whitespace-pre-wrap">
                  {m.content}
                </div>
              </div>
            )
          ))}
          {busy && (
            <div className="flex items-center gap-2">
              <span
                className="w-7 h-7 rounded-full inline-flex items-center justify-center text-[10px] font-extrabold opacity-80"
                style={{ background: "#0A1628", color: "#D4AF37", border: "1.5px solid #D4AF37" }}
              >
                Z
              </span>
              <div className="flex items-center gap-2 text-[#888] text-[12.5px] bg-[#F4F6FB] px-3.5 py-2 rounded-lg rounded-tl-sm">
                <Loader2 size={13} className="animate-spin" /> Zynthoro Assist is thinking…
              </div>
            </div>
          )}
        </div>

        <form onSubmit={send} className="p-3 border-t border-[#eee] flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Zynthoro anything…"
            data-testid="assist-input"
            className="flex-1 text-[13.5px] outline-none px-3 py-2 rounded-md border border-[#eee] focus:border-[#1A4FFF]"
          />
          <button type="submit" disabled={busy || !input.trim()} className="zy-btn-primary px-3 py-2 disabled:opacity-50" data-testid="assist-send">
            <Send size={15} />
          </button>
        </form>
      </div>
    </>
  );
}
