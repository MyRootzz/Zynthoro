/**
 * Compliance module — GDPR checklist, audit log, policy library.
 * Session B (2026-07-21).
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API, formatApiError } from "@/contexts/AuthContext";
import { CheckSquare, ShieldAlert, ScrollText, Loader2, Plus, Trash2, Edit3, Check } from "lucide-react";

const TABS = [
  { id: "checklist", label: "GDPR checklist", icon: CheckSquare },
  { id: "audit",     label: "Audit log",      icon: ShieldAlert },
  { id: "policies",  label: "Policy library", icon: ScrollText },
];

export default function ComplianceModule() {
  const [tab, setTab] = useState("checklist");
  return (
    <div className="space-y-6" data-testid="compliance-module">
      <header>
        <h1 className="text-[26px] font-bold tracking-tight text-black">Compliance</h1>
        <p className="text-[14px] text-[#666] mt-1">GDPR readiness, security audit log, and your organisation's policy library.</p>
      </header>
      <nav className="flex flex-wrap gap-1 border-b border-[#eee]">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`comp-tab-${t.id}`}
            className={`px-4 py-2.5 text-[13.5px] font-medium border-b-2 flex items-center gap-2 ${
              tab === t.id ? "border-[#1A4FFF] text-[#1A4FFF]" : "border-transparent text-[#666] hover:text-black"}`}>
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </nav>
      <div>
        {tab === "checklist" && <ChecklistPanel />}
        {tab === "audit" && <AuditPanel />}
        {tab === "policies" && <PoliciesPanel />}
      </div>
    </div>
  );
}

function ChecklistPanel() {
  const [data, setData] = useState(null);
  const load = async () => {
    try { const { data } = await axios.get(`${API}/compliance/checklist`, { withCredentials: true }); setData(data); }
    catch { toast.error("Failed to load checklist."); }
  };
  useEffect(() => { load(); }, []);
  const toggle = async (item) => {
    try {
      await axios.put(`${API}/compliance/checklist/${item.id}`, { checked: !item.checked, notes: item.notes || null }, { withCredentials: true });
      load();
    } catch { toast.error("Failed to update."); }
  };
  if (!data) return <Loader2 className="animate-spin text-[#999]" />;
  return (
    <div className="space-y-4">
      <div className="border border-[#eee] rounded-xl p-4 bg-white flex items-center gap-4">
        <div className="flex-1">
          <div className="text-[15px] font-semibold">{data.done} of {data.total} tasks complete</div>
          <div className="text-[13px] text-[#666]">GDPR readiness score for your workspace</div>
        </div>
        <div className="text-right">
          <div className="text-[36px] font-bold text-[#1A4FFF] leading-none" data-testid="comp-checklist-pct">{data.progress_pct}%</div>
        </div>
      </div>
      <div className="bg-[#F4F6FB] rounded-full h-2 overflow-hidden"><div className="h-2 bg-[#1A4FFF]" style={{ width: `${data.progress_pct}%` }} /></div>
      <div className="space-y-2">
        {data.items.map((it) => (
          <div key={it.id} className="border border-[#eee] rounded-xl p-3 flex items-start gap-3 bg-white" data-testid={`comp-check-${it.key}`}>
            <button onClick={() => toggle(it)} className={`w-5 h-5 rounded border-2 shrink-0 mt-0.5 flex items-center justify-center ${it.checked ? "bg-[#1A4FFF] border-[#1A4FFF]" : "border-[#ccc]"}`} data-testid={`comp-check-btn-${it.key}`}>
              {it.checked && <Check size={12} className="text-white" />}
            </button>
            <div className="flex-1">
              <div className={`text-[13.5px] font-semibold ${it.checked ? "line-through text-[#888]" : "text-[#111]"}`}>{it.title}</div>
              <div className="text-[12.5px] text-[#666] mt-0.5">{it.description}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AuditPanel() {
  const [items, setItems] = useState([]);
  const [source, setSource] = useState("all");
  useEffect(() => {
    axios.get(`${API}/compliance/audit-log`, { params: { source, limit: 100 }, withCredentials: true })
      .then((r) => setItems(r.data.items || []))
      .catch(() => toast.error("Failed to load audit log."));
  }, [source]);
  const badgeColor = (s) => s === "security" ? "bg-[#FFE8E8] text-[#a10404]" : s === "payments" ? "bg-[#FFF6D6] text-[#8a6e1d]" : "bg-[#E9EEFF] text-[#1A4FFF]";
  return (
    <div className="space-y-4">
      <div className="flex gap-1">
        {["all", "activity", "security", "payments"].map((s) => (
          <button key={s} onClick={() => setSource(s)} data-testid={`comp-audit-filter-${s}`}
            className={`px-3 py-1.5 text-[12.5px] rounded-full ${source === s ? "bg-[#1A4FFF] text-white" : "border border-[#eee] text-[#555] hover:border-[#1A4FFF]"}`}>
            {s === "all" ? "All sources" : s[0].toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>
      {items.length === 0 ? (
        <div className="border border-dashed border-[#e5e7ee] rounded-xl p-10 text-center text-[#888]">No events for this filter.</div>
      ) : (
        <div className="space-y-1.5">
          {items.map((it, i) => (
            <div key={i} className="border border-[#eee] rounded-lg p-3 bg-white flex items-start gap-3 text-[13px]" data-testid={`comp-audit-row-${i}`}>
              <span className={`text-[10.5px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full shrink-0 mt-0.5 ${badgeColor(it.source)}`}>{it.source}</span>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-[#111] truncate">{it.title || it.type}</div>
                {it.subtitle && <div className="text-[12px] text-[#666] truncate">{it.subtitle}</div>}
                <div className="text-[11px] text-[#999] mt-1">
                  {it.actor && <span>{it.actor} · </span>}
                  {it.at ? new Date(it.at).toLocaleString("nl-NL") : "—"}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PoliciesPanel() {
  const [rows, setRows] = useState([]);
  const [editing, setEditing] = useState(null); // policy being edited (or {} for new)
  const [form, setForm] = useState({ title: "", body: "" });
  const load = async () => {
    try { const { data } = await axios.get(`${API}/compliance/policies`, { withCredentials: true }); setRows(data.policies || []); }
    catch { toast.error("Failed to load policies."); }
  };
  useEffect(() => { load(); }, []);
  const openNew = () => { setEditing({ id: null }); setForm({ title: "", body: "" }); };
  const openEdit = (p) => { setEditing(p); setForm({ title: p.title, body: p.body }); };
  const save = async () => {
    if (!form.title.trim() || !form.body.trim()) return toast.error("Title and body are required.");
    try {
      if (editing?.id) {
        await axios.put(`${API}/compliance/policies/${editing.id}`, form, { withCredentials: true });
        toast.success("Policy updated.");
      } else {
        await axios.post(`${API}/compliance/policies`, form, { withCredentials: true });
        toast.success("Policy created.");
      }
      setEditing(null); load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this policy?")) return;
    try { await axios.delete(`${API}/compliance/policies/${id}`, { withCredentials: true }); load(); } catch { /* noop */ }
  };
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold">{rows.length} polic{rows.length === 1 ? "y" : "ies"}</h2>
        <button onClick={openNew} className="zy-btn-primary flex items-center gap-1.5 text-[13px]" data-testid="comp-policy-new-btn"><Plus size={14} /> New policy</button>
      </div>
      {editing && (
        <div className="border border-[#eee] rounded-xl p-4 bg-white space-y-3">
          <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Policy title" className="w-full text-[14px] font-semibold px-3 py-2 border border-[#eee] rounded-md" data-testid="comp-policy-title" />
          <textarea value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} placeholder="Policy body (markdown supported)" className="w-full text-[13px] px-3 py-2 border border-[#eee] rounded-md min-h-[200px] font-mono" data-testid="comp-policy-body" />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setEditing(null)} className="px-3 py-2 text-[13px] text-[#666]">Cancel</button>
            <button onClick={save} className="zy-btn-primary text-[13px]" data-testid="comp-policy-save">{editing.id ? "Save changes" : "Create policy"}</button>
          </div>
        </div>
      )}
      <div className="space-y-2">
        {rows.map((p) => (
          <div key={p.id} className="border border-[#eee] rounded-xl p-4 bg-white" data-testid={`comp-policy-${p.id}`}>
            <div className="flex items-start gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-[14px] font-semibold text-[#111]">{p.title}</h3>
                  {p.is_template && <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-[#F4F6FB] text-[#888]">Template</span>}
                  <span className="text-[11px] text-[#888]">v{p.version}</span>
                </div>
                <p className="text-[12.5px] text-[#555] mt-1 line-clamp-2">{p.body}</p>
              </div>
              <div className="flex gap-1 shrink-0">
                <button onClick={() => openEdit(p)} className="text-[#555] hover:text-[#1A4FFF] p-1" data-testid={`comp-policy-edit-${p.id}`}><Edit3 size={14} /></button>
                {!p.is_template && <button onClick={() => remove(p.id)} className="text-[#c00] p-1" data-testid={`comp-policy-del-${p.id}`}><Trash2 size={14} /></button>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
