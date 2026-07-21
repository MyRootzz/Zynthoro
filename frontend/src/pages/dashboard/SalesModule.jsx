/**
 * Sales module — Leads CRUD + Kanban pipeline.
 * Session C1 (2026-02) — jury-ready CRUD.
 */
import { useEffect, useState, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API, formatApiError } from "@/contexts/AuthContext";
import {
  ShoppingCart, Plus, Trash2, Loader2, Users, TrendingUp,
  Trophy, XCircle, KanbanSquare, List, Edit3, Building2, Mail, Phone, Calendar, Euro,
} from "lucide-react";

const STAGES = [
  { id: "new",       label: "New",       color: "#94a3b8" },
  { id: "contacted", label: "Contacted", color: "#1A4FFF" },
  { id: "proposal",  label: "Proposal",  color: "#D97706" },
  { id: "won",       label: "Won",       color: "#16a34a" },
  { id: "lost",      label: "Lost",      color: "#94a3b8" },
];

const CURRENCY_SYMBOL = { EUR: "€", USD: "$", GBP: "£" };
const sym = (c) => CURRENCY_SYMBOL[c] || c || "€";
const fmt = (v) => Number(v || 0).toLocaleString("nl-NL", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

const emptyForm = () => ({
  name: "", company: "", email: "", phone: "", source: "",
  stage: "new", value: 0, currency: "EUR", expected_close: "", notes: "",
});

export default function SalesModule() {
  const [tab, setTab] = useState("pipeline");
  const [leads, setLeads] = useState([]);
  const [pipe, setPipe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [l, p] = await Promise.all([
        axios.get(`${API}/sales/leads`, { withCredentials: true }),
        axios.get(`${API}/sales/pipeline`, { withCredentials: true }),
      ]);
      setLeads(l.data.leads || []);
      setPipe(p.data);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to load."); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const saveLead = async () => {
    if (!editing.name) return toast.error("Lead name is required.");
    try {
      const payload = {
        ...editing,
        value: parseFloat(editing.value) || 0,
        email: editing.email || null,
        expected_close: editing.expected_close || null,
      };
      if (editing.id) {
        await axios.put(`${API}/sales/leads/${editing.id}`, payload, { withCredentials: true });
        toast.success("Lead updated.");
      } else {
        await axios.post(`${API}/sales/leads`, payload, { withCredentials: true });
        toast.success("Lead added.");
      }
      setEditing(null);
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to save."); }
  };

  const removeLead = async (id) => {
    if (!window.confirm("Delete this lead?")) return;
    try {
      await axios.delete(`${API}/sales/leads/${id}`, { withCredentials: true });
      toast.success("Lead deleted.");
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const moveStage = async (id, stage) => {
    try {
      await axios.put(`${API}/sales/leads/${id}/stage`, { stage }, { withCredentials: true });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const totals = pipe?.totals || { total_leads: 0, open_value: 0, won_value: 0, lost_count: 0 };

  return (
    <div className="space-y-6" data-testid="sales-module">
      <header>
        <h1 className="text-[26px] font-bold tracking-tight text-black flex items-center gap-2">
          <ShoppingCart size={22} style={{ color: "#1A4FFF" }} /> Sales
        </h1>
        <p className="text-[14px] text-[#666] mt-1">
          Track leads through your pipeline — from first touch to closed-won.
        </p>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatPill label="Total leads" value={totals.total_leads} icon={Users} accent="#1A4FFF" />
        <StatPill label="Open value" value={`€${fmt(totals.open_value)}`} icon={TrendingUp} accent="#D97706" />
        <StatPill label="Won value" value={`€${fmt(totals.won_value)}`} icon={Trophy} accent="#16a34a" />
        <StatPill label="Lost" value={totals.lost_count} icon={XCircle} accent="#94a3b8" />
      </div>

      <nav className="flex items-center justify-between border-b border-[#eee]">
        <div className="flex gap-1">
          {[
            { id: "pipeline", label: "Pipeline", icon: KanbanSquare },
            { id: "leads",    label: "All leads", icon: List },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              data-testid={`sales-tab-${t.id}`}
              className={`px-4 py-2.5 text-[13.5px] font-medium border-b-2 flex items-center gap-2 transition-colors ${
                tab === t.id ? "border-[#1A4FFF] text-[#1A4FFF]" : "border-transparent text-[#666] hover:text-black"
              }`}
            >
              <t.icon size={15} /> {t.label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setEditing({ ...emptyForm(), id: null })}
          className="zy-btn-primary flex items-center gap-1.5 text-[13px] mb-1"
          data-testid="sales-new-lead-btn"
        >
          <Plus size={14} /> New lead
        </button>
      </nav>

      {loading ? (
        <Loader2 className="animate-spin text-[#999]" />
      ) : tab === "pipeline" ? (
        <PipelineBoard columns={pipe?.columns || []} onMove={moveStage} onEdit={setEditing} onDelete={removeLead} />
      ) : (
        <LeadsTable rows={leads} onEdit={setEditing} onDelete={removeLead} />
      )}

      {editing && (
        <LeadEditor value={editing} onChange={setEditing} onCancel={() => setEditing(null)} onSave={saveLead} />
      )}
    </div>
  );
}

// -------- Kanban board -----------------------------------------------------
function PipelineBoard({ columns, onMove, onEdit, onDelete }) {
  const [dragId, setDragId] = useState(null);
  const [overStage, setOverStage] = useState(null);

  const byStage = useMemo(() => {
    const m = {};
    for (const c of columns) m[c.stage] = c;
    return m;
  }, [columns]);

  const handleDrop = (stage) => {
    if (dragId && byStage[stage]) {
      const lead = columns.flatMap((c) => c.leads).find((l) => l.id === dragId);
      if (lead && lead.stage !== stage) onMove(dragId, stage);
    }
    setDragId(null);
    setOverStage(null);
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3" data-testid="sales-kanban">
      {STAGES.map((s) => {
        const col = byStage[s.id] || { leads: [], count: 0, total_value: 0 };
        const isOver = overStage === s.id;
        return (
          <div
            key={s.id}
            data-testid={`sales-kanban-col-${s.id}`}
            className={`bg-[#F4F6FB] rounded-xl p-2.5 flex flex-col min-h-[400px] transition-colors ${isOver ? "ring-2 ring-[#1A4FFF]" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setOverStage(s.id); }}
            onDragLeave={() => setOverStage((v) => (v === s.id ? null : v))}
            onDrop={() => handleDrop(s.id)}
          >
            <div className="flex items-center justify-between px-2 pb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ background: s.color }} />
                <span className="text-[12.5px] font-bold uppercase tracking-wider text-[#0A1628]">{s.label}</span>
                <span className="text-[11px] text-[#888]">({col.count})</span>
              </div>
              <span className="text-[11px] text-[#888] tabular-nums">€{fmt(col.total_value)}</span>
            </div>
            <div className="flex-1 space-y-2 overflow-y-auto">
              {col.leads.length === 0 && (
                <div className="text-[11.5px] text-[#aaa] text-center py-6 italic">Drop a lead here</div>
              )}
              {col.leads.map((l) => (
                <LeadCard key={l.id} lead={l} onDragStart={() => setDragId(l.id)} onEdit={() => onEdit(l)} onDelete={() => onDelete(l.id)} />
              ))}
            </div>
            {/* Mobile-friendly stage move dropdown for touch devices */}
            <div className="pt-2 border-t border-[#e5e7ee] mt-2 lg:hidden">
              <select
                onChange={(e) => {
                  const [lid, stage] = e.target.value.split("|");
                  if (lid && stage) onMove(lid, stage);
                  e.target.value = "";
                }}
                className="w-full text-[11.5px] bg-white border border-[#eee] rounded-md px-2 py-1.5"
              >
                <option value="">Move a lead → stage</option>
                {col.leads.map((l) => (
                  STAGES.filter((s2) => s2.id !== s.id).map((s2) => (
                    <option key={`${l.id}-${s2.id}`} value={`${l.id}|${s2.id}`}>
                      {l.name} → {s2.label}
                    </option>
                  ))
                ))}
              </select>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LeadCard({ lead, onDragStart, onEdit, onDelete }) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      className="bg-white border border-[#e5e7ee] rounded-lg p-2.5 shadow-sm hover:shadow-md transition-shadow cursor-grab active:cursor-grabbing"
      data-testid={`sales-lead-card-${lead.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[13px] font-semibold text-black truncate">{lead.name}</div>
          {lead.company && (
            <div className="text-[11.5px] text-[#666] flex items-center gap-1 mt-0.5 truncate">
              <Building2 size={10} /> {lead.company}
            </div>
          )}
        </div>
        <div className="flex gap-1 opacity-70 shrink-0">
          <button onClick={onEdit} className="text-[#666] hover:text-[#1A4FFF]" data-testid={`sales-lead-edit-${lead.id}`}><Edit3 size={12} /></button>
          <button onClick={onDelete} className="text-[#666] hover:text-[#c00]" data-testid={`sales-lead-del-${lead.id}`}><Trash2 size={12} /></button>
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between text-[11.5px]">
        {lead.value > 0 ? (
          <span className="inline-flex items-center gap-0.5 font-semibold text-[#0A1628]">
            <Euro size={10} /> {fmt(lead.value)}
          </span>
        ) : <span className="text-[#aaa]">—</span>}
        {lead.expected_close && (
          <span className="text-[#888] flex items-center gap-0.5">
            <Calendar size={10} /> {lead.expected_close}
          </span>
        )}
      </div>
    </div>
  );
}

// -------- Table view -------------------------------------------------------
function LeadsTable({ rows, onEdit, onDelete }) {
  if (rows.length === 0) {
    return (
      <div className="border border-dashed border-[#e5e7ee] rounded-xl p-10 text-center text-[#888]">
        No leads yet. Click <b>New lead</b> to add your first one.
      </div>
    );
  }
  return (
    <div className="border border-[#eee] rounded-xl overflow-hidden bg-white">
      <table className="w-full text-[13px]">
        <thead className="bg-[#F4F6FB] text-[#555]">
          <tr>
            <th className="text-left px-4 py-2.5">Name</th>
            <th className="text-left px-4 py-2.5">Company</th>
            <th className="text-left px-4 py-2.5">Contact</th>
            <th className="text-left px-4 py-2.5">Stage</th>
            <th className="text-right px-4 py-2.5">Value</th>
            <th className="text-left px-4 py-2.5">Close</th>
            <th className="w-1" />
          </tr>
        </thead>
        <tbody>
          {rows.map((l) => {
            const st = STAGES.find((s) => s.id === l.stage) || STAGES[0];
            return (
              <tr key={l.id} className="border-t border-[#eee]" data-testid={`sales-lead-row-${l.id}`}>
                <td className="px-4 py-2.5 font-medium text-black">{l.name}</td>
                <td className="px-4 py-2.5 text-[#555]">{l.company || "—"}</td>
                <td className="px-4 py-2.5 text-[#666] text-[12px]">
                  {l.email && <div className="flex items-center gap-1"><Mail size={10} /> {l.email}</div>}
                  {l.phone && <div className="flex items-center gap-1"><Phone size={10} /> {l.phone}</div>}
                </td>
                <td className="px-4 py-2.5">
                  <span className="inline-flex items-center gap-1 text-[11px] uppercase font-bold px-2 py-0.5 rounded-full" style={{ background: `${st.color}22`, color: st.color }}>
                    {st.label}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">{l.value > 0 ? `${sym(l.currency)}${fmt(l.value)}` : "—"}</td>
                <td className="px-4 py-2.5 text-[#555]">{l.expected_close || "—"}</td>
                <td className="px-4 py-2.5 whitespace-nowrap text-right">
                  <button onClick={() => onEdit(l)} className="text-[#1A4FFF] mx-1"><Edit3 size={13} /></button>
                  <button onClick={() => onDelete(l.id)} className="text-[#c00] mx-1"><Trash2 size={13} /></button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// -------- Editor -----------------------------------------------------------
function LeadEditor({ value, onChange, onCancel, onSave }) {
  const set = (patch) => onChange({ ...value, ...patch });
  return (
    <div className="fixed inset-0 bg-black/40 z-40 flex items-start justify-center overflow-y-auto p-4" data-testid="sales-editor-modal">
      <div className="bg-white rounded-2xl w-full max-w-lg mt-16 shadow-xl overflow-hidden">
        <div className="p-5 border-b border-[#eee] flex items-center justify-between">
          <h3 className="text-[16px] font-semibold">{value.id ? "Edit lead" : "New lead"}</h3>
          <button onClick={onCancel} className="text-[#666] hover:text-black">✕</button>
        </div>
        <div className="p-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Full name*">
            <input value={value.name} onChange={(e) => set({ name: e.target.value })} className="zy-input" data-testid="sales-editor-name" />
          </Field>
          <Field label="Company">
            <input value={value.company || ""} onChange={(e) => set({ company: e.target.value })} className="zy-input" data-testid="sales-editor-company" />
          </Field>
          <Field label="Email">
            <input type="email" value={value.email || ""} onChange={(e) => set({ email: e.target.value })} className="zy-input" />
          </Field>
          <Field label="Phone">
            <input value={value.phone || ""} onChange={(e) => set({ phone: e.target.value })} className="zy-input" />
          </Field>
          <Field label="Source">
            <input value={value.source || ""} onChange={(e) => set({ source: e.target.value })} placeholder="Website, referral, LinkedIn…" className="zy-input" />
          </Field>
          <Field label="Stage">
            <select value={value.stage} onChange={(e) => set({ stage: e.target.value })} className="zy-input" data-testid="sales-editor-stage">
              {STAGES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </Field>
          <Field label="Deal value">
            <input type="number" step="0.01" value={value.value} onChange={(e) => set({ value: e.target.value })} className="zy-input" data-testid="sales-editor-value" />
          </Field>
          <Field label="Currency">
            <select value={value.currency} onChange={(e) => set({ currency: e.target.value })} className="zy-input">
              <option value="EUR">EUR</option><option value="USD">USD</option><option value="GBP">GBP</option>
            </select>
          </Field>
          <Field label="Expected close date" className="sm:col-span-2">
            <input type="date" value={value.expected_close || ""} onChange={(e) => set({ expected_close: e.target.value })} className="zy-input" />
          </Field>
          <Field label="Notes" className="sm:col-span-2">
            <textarea value={value.notes || ""} onChange={(e) => set({ notes: e.target.value })} className="zy-input min-h-[70px]" />
          </Field>
        </div>
        <div className="p-4 border-t border-[#eee] flex justify-end gap-2 bg-[#FAFBFF]">
          <button onClick={onCancel} className="px-3 py-2 text-[13px] text-[#666] hover:text-black">Cancel</button>
          <button onClick={onSave} className="zy-btn-primary text-[13px]" data-testid="sales-editor-save-btn">
            {value.id ? "Save changes" : "Add lead"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children, className = "" }) {
  return (
    <label className={`block ${className}`}>
      <span className="block text-[11.5px] uppercase font-bold text-[#888] mb-1">{label}</span>
      {children}
    </label>
  );
}

function StatPill({ label, value, icon: Icon, accent = "#1A4FFF" }) {
  return (
    <div className="bg-white border border-[#eee] rounded-xl p-3 sm:p-4">
      <div className="flex items-center gap-2 mb-1">
        <Icon size={13} style={{ color: accent }} />
        <span className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: accent }}>{label}</span>
      </div>
      <p className="mt-1 font-bold text-[18px] sm:text-[20px]" style={{ color: "#0A1628" }}>{value}</p>
    </div>
  );
}
