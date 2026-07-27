import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Sparkles, X, Send, Loader2, Paperclip, Eraser } from "lucide-react";
import { ZyLogo } from "@/components/ZyLogo";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";
import AssistantActions from "@/components/dashboard/AssistantActions";
import VoiceButton from "@/components/dashboard/VoiceButton";
import AISeesIndicator from "@/components/dashboard/AISeesIndicator";
import AttachmentChip from "@/components/dashboard/AttachmentChip";
import { streamAssistantChat } from "@/lib/aiStream";
import {
  uploadAiFile,
  deleteAiFile,
  validateUpload,
  AI_UPLOAD_ACCEPT_ATTR,
} from "@/lib/aiUpload";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

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
  const [attachments, setAttachments] = useState([]);
  const fileInputRef = useRef(null);
  const scrollRef = useRef(null);
  // Tracks whether the initial scroll-to-bottom (after resume) has "stuck".
  // Reset every time the user re-opens the panel.
  const didInitialScrollRef = useRef(false);
  const { user } = useAuth();
  const isFounder = !!user?.is_founder;
  const [wipeOpen, setWipeOpen] = useState(false);
  const [wiping, setWiping] = useState(false);

  const wipeMemory = async () => {
    setWiping(true);
    try {
      const { data } = await axios.delete(`${API}/ai/memory/zynthoro_assist`);
      setSessionId(null);
      didInitialScrollRef.current = false;
      setMessages([{
        role: "assistant",
        content: "Hi! I'm Zynthoro Assist. Ask me anything about the platform or your account.",
      }]);
      setInput("");
      setAttachments([]);
      toast.success(
        `Memory cleared — ${data.messages_deleted} message${data.messages_deleted === 1 ? "" : "s"} wiped.`
      );
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't clear memory.");
    }
    setWiping(false);
    setWipeOpen(false);
  };

  // Resume last conversation when the user opens the panel for the first time
  useEffect(() => {
    if (!open || sessionId) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get(`${API}/ai/sessions`, { params: { assistant: "zynthoro_assist", limit: 1 } });
        const last = data.sessions?.[0];
        if (last && !cancelled) {
          const hist = await axios.get(`${API}/ai/history`, { params: { session_id: last.session_id } });
          const msgs = (hist.data.messages || []).map((m) => ({ role: m.role, content: m.content }));
          if (msgs.length) {
            setSessionId(last.session_id);
            setMessages(msgs);
          }
        }
      } catch { /* ignored */ }
    })();
    return () => { cancelled = true; };
  }, [open, sessionId]);

  useEffect(() => {
    if (!open) {
      didInitialScrollRef.current = false;
      return;
    }
    const el = scrollRef.current;
    if (!el || messages.length === 0) return;

    const stick = () => { el.scrollTop = el.scrollHeight; };

    // Avatar images inside resumed messages haven't decoded yet on first
    // render — scrollHeight is short so a naive scroll strands the user
    // near the top. Chain rAF + short retries + per-image load listeners
    // on the initial pass; subsequent updates just need a single scroll.
    if (!didInitialScrollRef.current) {
      didInitialScrollRef.current = true;
      stick();
      const raf = requestAnimationFrame(stick);
      const t1 = setTimeout(stick, 120);
      const t2 = setTimeout(stick, 400);
      const imgs = Array.from(el.querySelectorAll("img"));
      const onLoad = () => stick();
      imgs.forEach((img) => {
        if (!img.complete) img.addEventListener("load", onLoad, { once: true });
      });
      return () => {
        cancelAnimationFrame(raf);
        clearTimeout(t1);
        clearTimeout(t2);
        imgs.forEach((img) => img.removeEventListener("load", onLoad));
      };
    }
    stick();
  }, [messages, open]);

  const send = async (e, override) => {
    e?.preventDefault?.();
    const text = (typeof override === "string" ? override : input).trim();
    if (!text || busy) return;
    if (attachments.some((a) => a.status === "uploading")) {
      toast.info("Please wait for the file upload to finish.");
      return;
    }
    setInput("");

    const readyAttachments = attachments.filter((a) => a.status === "ready" && a.file_id);
    const fileIds = readyAttachments.map((a) => a.file_id);
    const bubbleAttachments = readyAttachments.map((a) => ({
      file_id: a.file_id, filename: a.filename, size: a.size,
    }));
    setAttachments([]);

    setMessages((m) => [
      ...m,
      { role: "user", content: text, attachments: bubbleAttachments },
      { role: "assistant", content: "", streaming: true },
    ]);
    setBusy(true);

    let localSession = sessionId;
    let hadError = false;

    await streamAssistantChat({
      assistant: "zynthoro_assist",
      session_id: sessionId || undefined,
      message: text,
      file_ids: fileIds.length ? fileIds : undefined,
      onMeta: (meta) => {
        if (meta?.session_id && !localSession) {
          localSession = meta.session_id;
          setSessionId(meta.session_id);
        }
        if (meta?.badge) setPoweredBy({ badge: meta.badge, provider: meta.provider });
      },
      onDelta: (d) => {
        const chunk = d?.content || "";
        if (!chunk) return;
        setMessages((m) => {
          const next = [...m];
          const last = next[next.length - 1];
          if (last && last.role === "assistant") {
            next[next.length - 1] = { ...last, content: (last.content || "") + chunk, streaming: true };
          }
          return next;
        });
      },
      onError: (err) => {
        hadError = true;
        toast.error(formatApiError(err?.message) || "Assistant is unavailable.");
        setMessages((m) => {
          const next = [...m];
          const last = next[next.length - 1];
          if (last && last.role === "assistant" && !last.content) {
            next[next.length - 1] = { role: "assistant", content: "I had trouble responding. Please try again shortly." };
          }
          return next;
        });
      },
      onDone: () => {
        setMessages((m) => {
          const next = [...m];
          const last = next[next.length - 1];
          if (last && last.role === "assistant") {
            next[next.length - 1] = { ...last, streaming: false };
          }
          return next;
        });
      },
    });

    setBusy(false);
    if (hadError && !localSession) setSessionId(null);
  };

  // ---- Attachment handlers -------------------------------------------------
  const handleAttachClick = () => {
    if (busy) return;
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    for (const file of files) {
      const err = validateUpload(file);
      if (err) { toast.error(err); continue; }
      const local_id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setAttachments((prev) => [
        ...prev,
        { local_id, filename: file.name, size: file.size, status: "uploading" },
      ]);
      try {
        const res = await uploadAiFile(file);
        setAttachments((prev) =>
          prev.map((a) =>
            a.local_id === local_id
              ? { ...a, file_id: res.file_id, size: res.size, status: "ready" }
              : a
          )
        );
      } catch (uploadErr) {
        const msg = formatApiError(uploadErr?.response?.data?.detail) || uploadErr?.message || "Upload failed.";
        toast.error(msg);
        setAttachments((prev) => prev.filter((a) => a.local_id !== local_id));
      }
    }
  };

  const removeAttachment = async (local_id) => {
    const target = attachments.find((a) => a.local_id === local_id);
    setAttachments((prev) => prev.filter((a) => a.local_id !== local_id));
    if (target?.file_id) deleteAiFile(target.file_id).catch(() => {});
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

        {isFounder && (
          <div className="px-4 py-2 border-b border-[#f1f1f3] bg-white flex justify-end">
            <button
              type="button"
              onClick={() => setWipeOpen(true)}
              disabled={wiping}
              title="Founder only — wipe Zynthoro Assist's stored memory for your workspace"
              data-testid="assist-clear-memory-btn"
              className="inline-flex items-center gap-1.5 rounded-full border border-[#0A162820] px-2.5 py-1 text-[11.5px] font-semibold text-[#0A1628] hover:bg-[#F7F8FA] transition-colors disabled:opacity-50"
            >
              {wiping ? <Loader2 size={11} className="animate-spin" /> : <Eraser size={11} />}
              Clear memory
            </button>
          </div>
        )}

        <div className="px-4 py-1.5 border-b border-[#f1f1f3] bg-[#FAFAFB]">
          <AISeesIndicator testId="assist-ai-sees" />
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3.5" data-testid="assist-messages">
          {messages.map((m, i) => (
            m.role === "user" ? (
              <div key={i} className="max-w-[85%] ml-auto flex flex-col items-end gap-1.5">
                {m.attachments && m.attachments.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 justify-end" data-testid={`assist-msg-${i}-attachments`}>
                    {m.attachments.map((a) => (
                      <AttachmentChip
                        key={a.file_id}
                        filename={a.filename}
                        size={a.size}
                        compact
                        testId={`assist-msg-${i}-attachment-${a.file_id}`}
                      />
                    ))}
                  </div>
                )}
                <div
                  className="text-[13.5px] leading-relaxed px-3.5 py-2.5 rounded-lg rounded-tr-sm text-white whitespace-pre-wrap"
                  style={{ background: "#1A4FFF" }}
                >
                  {m.content}
                </div>
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
                <div className="flex flex-col min-w-0">
                  <div className="text-[13.5px] leading-relaxed px-3.5 py-2.5 rounded-lg rounded-tl-sm bg-[#F4F6FB] whitespace-pre-wrap">
                    {m.content}
                    {m.streaming && (
                      <span
                        className="inline-block w-[6px] h-[12px] ml-0.5 align-middle animate-pulse"
                        style={{ background: "#1A4FFF" }}
                        aria-hidden="true"
                      />
                    )}
                  </div>
                  {!m.streaming && m.content && m.content.length > 10 && (
                    <AssistantActions
                      content={m.content}
                      assistantName="Zynthoro Assist"
                      testIdPrefix={`assist-msg-${i}`}
                    />
                  )}
                </div>
              </div>
            )
          ))}
          {busy && !(messages.length > 0 && messages[messages.length - 1].role === "assistant" && messages[messages.length - 1].streaming) && (
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

        <form onSubmit={send} className="p-3 border-t border-[#eee] flex flex-col gap-2">
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-1.5" data-testid="assist-pending-attachments">
              {attachments.map((a) => (
                <AttachmentChip
                  key={a.local_id}
                  filename={a.filename}
                  size={a.size}
                  status={a.status}
                  onRemove={() => removeAttachment(a.local_id)}
                  testId={`assist-pending-${a.local_id}`}
                />
              ))}
            </div>
          )}
          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept={AI_UPLOAD_ACCEPT_ATTR}
              multiple
              onChange={handleFileSelected}
              className="hidden"
              data-testid="assist-file-input"
            />
            <button
              type="button"
              onClick={handleAttachClick}
              disabled={busy}
              title="Attach a file (PDF, DOCX, XLSX, PPTX, CSV — up to 10 MB)"
              aria-label="Attach a file"
              className="shrink-0 h-[38px] w-[38px] inline-flex items-center justify-center rounded-md border border-[#eee] text-[#555] hover:border-[#1A4FFF] hover:text-[#1A4FFF] disabled:opacity-40 disabled:cursor-not-allowed"
              data-testid="assist-attach-btn"
            >
              <Paperclip size={15} />
            </button>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Zynthoro anything…"
              data-testid="assist-input"
              className="flex-1 text-[13.5px] outline-none px-3 py-2 rounded-md border border-[#eee] focus:border-[#1A4FFF]"
            />
            <VoiceButton
              testId="assist-voice-btn"
              size={14}
              onInterim={(t) => setInput(t)}
              onFinal={(t) => { setInput(""); send(null, t); }}
            />
            <button type="submit" disabled={busy || !input.trim()} className="zy-btn-primary px-3 py-2 disabled:opacity-50" data-testid="assist-send">
              <Send size={15} />
            </button>
          </div>
        </form>
      </div>

      {isFounder && (
        <AlertDialog open={wipeOpen} onOpenChange={setWipeOpen}>
          <AlertDialogContent data-testid="assist-clear-memory-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle>Clear Zynthoro Assist&apos;s memory?</AlertDialogTitle>
              <AlertDialogDescription>
                This permanently deletes every message Zynthoro Assist has stored for your workspace —
                past sessions, context, everything. Your next conversation will start from a clean slate.
                This cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel data-testid="assist-clear-memory-cancel" disabled={wiping}>
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                data-testid="assist-clear-memory-confirm"
                onClick={(e) => { e.preventDefault(); wipeMemory(); }}
                disabled={wiping}
                className="bg-[#B42318] hover:bg-[#8B1A12]"
              >
                {wiping ? "Clearing…" : "Yes, clear memory"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </>
  );
}
