/**
 * Communication module — Channels + Messages.
 * Session B (2026-07-21) — internal messaging.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API, formatApiError } from "@/contexts/AuthContext";
import { Hash, Inbox, Plus, Send, Trash2, Loader2 } from "lucide-react";

export default function CommunicationModule() {
  const [channels, setChannels] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");

  const loadChannels = async () => {
    try {
      const { data } = await axios.get(`${API}/comm/channels`, { withCredentials: true });
      setChannels(data.channels || []);
      if (!selected && data.channels?.length) setSelected(data.channels[0].id);
    } catch { toast.error("Failed to load channels."); }
  };
  useEffect(() => { loadChannels(); }, []);

  const loadMessages = async () => {
    if (!selected) return;
    setLoadingMsgs(true);
    try {
      const { data } = await axios.get(`${API}/comm/messages`, { params: { channel_id: selected }, withCredentials: true });
      setMessages(data.messages || []);
    } catch { toast.error("Failed to load messages."); }
    setLoadingMsgs(false);
  };
  useEffect(() => { loadMessages(); /* eslint-disable-next-line */ }, [selected]);

  // Poll every 12s
  useEffect(() => {
    if (!selected) return;
    const id = setInterval(loadMessages, 12000);
    return () => clearInterval(id);
    // eslint-disable-next-line
  }, [selected]);

  const send = async () => {
    const body = input.trim();
    if (!body || !selected) return;
    setInput("");
    try {
      await axios.post(`${API}/comm/messages`, { channel_id: selected, body }, { withCredentials: true });
      loadMessages();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to send."); }
  };

  const createChannel = async () => {
    if (!newName.trim()) return;
    try {
      await axios.post(`${API}/comm/channels`, { name: newName }, { withCredentials: true });
      toast.success("Channel created.");
      setNewName(""); setShowNew(false);
      loadChannels();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const removeChannel = async (id) => {
    if (!window.confirm("Delete this channel and all its messages?")) return;
    try {
      await axios.delete(`${API}/comm/channels/${id}`, { withCredentials: true });
      loadChannels();
      if (selected === id) setSelected(null);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Cannot delete."); }
  };

  const selChan = channels.find((c) => c.id === selected);

  return (
    <div className="space-y-4" data-testid="comm-module">
      <header>
        <h1 className="text-[26px] font-bold tracking-tight text-black">Communication</h1>
        <p className="text-[14px] text-[#666] mt-1">Internal channels and shared inbox for your team.</p>
      </header>
      <div className="grid grid-cols-1 md:grid-cols-[240px_1fr] gap-4 border border-[#eee] rounded-2xl overflow-hidden bg-white" style={{ minHeight: 520 }}>
        <aside className="border-r border-[#eee] bg-[#FAFAFB] flex flex-col">
          <div className="p-3 flex items-center justify-between border-b border-[#eee]">
            <span className="text-[11px] uppercase tracking-wider font-bold text-[#888]">Channels</span>
            <button onClick={() => setShowNew(!showNew)} className="text-[#1A4FFF]" data-testid="comm-new-channel-btn"><Plus size={14} /></button>
          </div>
          {showNew && (
            <div className="p-2 border-b border-[#eee]">
              <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="channel-name" className="w-full text-[13px] px-2.5 py-1.5 border border-[#eee] rounded-md" data-testid="comm-new-channel-input" />
              <button onClick={createChannel} className="zy-btn-primary w-full mt-1.5 text-[12px]" data-testid="comm-new-channel-save">Create</button>
            </div>
          )}
          <ul className="flex-1 overflow-y-auto py-1">
            {channels.map((c) => (
              <li key={c.id} className="group flex items-center">
                <button onClick={() => setSelected(c.id)} data-testid={`comm-channel-${c.id}`}
                  className={`flex-1 text-left px-3 py-2 text-[13px] flex items-center gap-2 ${selected === c.id ? "bg-[#E9EEFF] text-[#1A4FFF] font-semibold" : "text-[#333] hover:bg-white"}`}>
                  {c.kind === "inbox" ? <Inbox size={14} /> : <Hash size={14} />}
                  <span className="truncate">{c.name}</span>
                  {c.message_count > 0 && <span className="ml-auto text-[10px] text-[#888]">{c.message_count}</span>}
                </button>
                {c.kind !== "inbox" && (
                  <button onClick={() => removeChannel(c.id)} className="opacity-0 group-hover:opacity-100 text-[#c00] px-2" data-testid={`comm-channel-del-${c.id}`}>
                    <Trash2 size={12} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </aside>
        <section className="flex flex-col">
          <div className="p-4 border-b border-[#eee] flex items-center gap-2">
            {selChan?.kind === "inbox" ? <Inbox size={16} /> : <Hash size={16} />}
            <h2 className="text-[15px] font-semibold">{selChan?.name || "Select a channel"}</h2>
            {selChan?.description && <span className="text-[12.5px] text-[#888]">· {selChan.description}</span>}
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3" style={{ maxHeight: 420 }}>
            {loadingMsgs ? <Loader2 className="animate-spin text-[#999]" /> : messages.length === 0 ? (
              <p className="text-center text-[#888] text-[13px] py-10">No messages yet — say hi to your team!</p>
            ) : messages.map((m) => (
              <div key={m.id} data-testid={`comm-msg-${m.id}`}>
                <div className="text-[12px] text-[#888]"><b className="text-[#111]">{m.author_name}</b> · {new Date(m.created_at).toLocaleString("nl-NL")}</div>
                <div className="text-[13.5px] text-[#222] whitespace-pre-wrap">{m.body}</div>
              </div>
            ))}
          </div>
          <div className="border-t border-[#eee] p-3 flex gap-2">
            <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder={selChan ? `Message #${selChan.name}` : "Select a channel"} disabled={!selChan}
              className="flex-1 text-[13.5px] px-3 py-2 border border-[#eee] rounded-md focus:border-[#1A4FFF] outline-none" data-testid="comm-msg-input" />
            <button onClick={send} disabled={!selChan || !input.trim()} className="zy-btn-primary text-[13px] disabled:opacity-50" data-testid="comm-msg-send"><Send size={14} /></button>
          </div>
        </section>
      </div>
    </div>
  );
}
