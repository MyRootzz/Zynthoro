/**
 * Projects module — projects list, project detail, tasks, milestones.
 * Session C2 (2026-02) — jury-ready CRUD.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { API, formatApiError } from "@/contexts/AuthContext";
import {
  KanbanSquare, Plus, Trash2, Loader2, Briefcase, CheckCircle2,
  AlertCircle, TrendingUp, Edit3, Calendar, Target, Clock, Flag, Receipt, Euro,
} from "lucide-react";

const STATUS = {
  planning:  { label: "Planning",  bg: "#F4F6FB",              fg: "#666" },
  on_track:  { label: "On track",  bg: "rgba(34,197,94,0.12)", fg: "#16a34a" },
  at_risk:   { label: "At risk",   bg: "rgba(217,119,6,0.12)", fg: "#D97706" },
  on_hold:   { label: "On hold",   bg: "rgba(148,163,184,0.15)", fg: "#64748b" },
  completed: { label: "Completed", bg: "rgba(26,79,255,0.12)", fg: "#1A4FFF" },
};
const TASK_STATUS = {
  todo:        { label: "To do", bg: "#F4F6FB",              fg: "#666" },
  in_progress: { label: "Doing", bg: "rgba(217,119,6,0.12)", fg: "#D97706" },
  done:        { label: "Done",  bg: "rgba(34,197,94,0.12)", fg: "#16a34a" },
};

const emptyProject = () => ({
  name: "", description: "", status: "planning", domain: "",
  owner: "", start_date: "", end_date: "", progress: 0, color: "#1A4FFF",
});

export default function ProjectsModule() {
  const [rows, setRows] = useState([]);
  const [totals, setTotals] = useState({ total: 0, on_track: 0, at_risk: 0, completed: 0 });
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [detailId, setDetailId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/projects`, { withCredentials: true });
      setRows(data.projects || []);
      setTotals(data.totals || {});
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to load."); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!editing.name) return toast.error("Project name is required.");
    try {
      const payload = { ...editing, progress: parseInt(editing.progress || 0, 10) };
      if (editing.id) {
        await axios.put(`${API}/projects/${editing.id}`, payload, { withCredentials: true });
        toast.success("Project updated.");
      } else {
        await axios.post(`${API}/projects`, payload, { withCredentials: true });
        toast.success("Project created.");
      }
      setEditing(null);
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this project? Tasks, milestones and time entries will also be removed.")) return;
    try {
      await axios.delete(`${API}/projects/${id}`, { withCredentials: true });
      toast.success("Project deleted.");
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  return (
    <div className="space-y-6" data-testid="projects-module">
      <header>
        <h1 className="text-[26px] font-bold tracking-tight text-black flex items-center gap-2">
          <KanbanSquare size={22} style={{ color: "#1A4FFF" }} /> Projects
        </h1>
        <p className="text-[14px] text-[#666] mt-1">
          Track your projects with tasks, milestones and progress.
        </p>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatPill label="Total" value={totals.total} icon={Briefcase} accent="#1A4FFF" />
        <StatPill label="On track" value={totals.on_track} icon={TrendingUp} accent="#16a34a" />
        <StatPill label="At risk" value={totals.at_risk} icon={AlertCircle} accent="#D97706" />
        <StatPill label="Completed" value={totals.completed} icon={CheckCircle2} accent="#1A4FFF" />
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold">{rows.length} project{rows.length === 1 ? "" : "s"}</h2>
        <button onClick={() => setEditing({ ...emptyProject(), id: null })} className="zy-btn-primary flex items-center gap-1.5 text-[13px]" data-testid="projects-new-btn">
          <Plus size={14} /> New project
        </button>
      </div>

      {loading ? <Loader2 className="animate-spin text-[#999]" /> : rows.length === 0 ? (
        <div className="border border-dashed border-[#e5e7ee] rounded-xl p-10 text-center text-[#888]">
          No projects yet. Click <b>New project</b> to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {rows.map((p) => {
            const st = STATUS[p.status] || STATUS.planning;
            const c = p.task_counts || { todo: 0, in_progress: 0, done: 0, total: 0 };
            return (
              <div key={p.id} className="bg-white border border-[#eee] rounded-xl p-4 flex flex-col gap-3 hover:shadow-md transition-shadow" data-testid={`projects-card-${p.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <button onClick={() => setDetailId(p.id)} className="text-left min-w-0 flex-1" data-testid={`projects-open-${p.id}`}>
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: p.color || "#1A4FFF" }} />
                      <span className="font-semibold text-black truncate">{p.name}</span>
                    </div>
                    <div className="text-[12px] text-[#888] mt-0.5 truncate">{p.domain || "—"}</div>
                  </button>
                  <div className="flex gap-1 shrink-0">
                    <button onClick={() => setEditing({ ...p })} className="text-[#1A4FFF] hover:opacity-70" data-testid={`projects-edit-${p.id}`}><Edit3 size={13} /></button>
                    <button onClick={() => remove(p.id)} className="text-[#c00] hover:opacity-70" data-testid={`projects-del-${p.id}`}><Trash2 size={13} /></button>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-[11.5px]">
                  <span className="uppercase font-bold px-2 py-0.5 rounded-full" style={{ background: st.bg, color: st.fg }}>{st.label}</span>
                  {p.end_date && <span className="text-[#888] flex items-center gap-1"><Calendar size={10} /> {p.end_date}</span>}
                </div>
                <div>
                  <div className="flex items-center justify-between text-[11.5px] mb-1">
                    <span className="text-[#666]">Progress</span>
                    <span className="tabular-nums font-semibold">{p.progress || 0}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[#eee] overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{ width: `${p.progress || 0}%`, background: p.color || "#1A4FFF" }} />
                  </div>
                </div>
                <div className="flex items-center gap-3 text-[11.5px] text-[#666]">
                  <span className="flex items-center gap-1"><Target size={11} /> {c.total} task{c.total === 1 ? "" : "s"}</span>
                  <span className="text-[#16a34a] font-semibold">{c.done} done</span>
                  {c.in_progress > 0 && <span className="text-[#D97706] font-semibold">{c.in_progress} doing</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {editing && (
        <ProjectEditor value={editing} onChange={setEditing} onCancel={() => setEditing(null)} onSave={save} />
      )}

      {detailId && (
        <ProjectDetail id={detailId} onClose={() => { setDetailId(null); load(); }} />
      )}
    </div>
  );
}

// -------- Project editor ---------------------------------------------------
function ProjectEditor({ value, onChange, onCancel, onSave }) {
  const set = (patch) => onChange({ ...value, ...patch });
  return (
    <div className="fixed inset-0 bg-black/40 z-40 flex items-start justify-center overflow-y-auto p-4" data-testid="projects-editor-modal">
      <div className="bg-white rounded-2xl w-full max-w-lg mt-16 shadow-xl overflow-hidden">
        <div className="p-5 border-b border-[#eee] flex items-center justify-between">
          <h3 className="text-[16px] font-semibold">{value.id ? "Edit project" : "New project"}</h3>
          <button onClick={onCancel} className="text-[#666] hover:text-black">✕</button>
        </div>
        <div className="p-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Project name*" className="sm:col-span-2">
            <input value={value.name} onChange={(e) => set({ name: e.target.value })} className="zy-input" data-testid="projects-editor-name" />
          </Field>
          <Field label="Domain">
            <input value={value.domain || ""} onChange={(e) => set({ domain: e.target.value })} placeholder="Sales, Marketing, Ops…" className="zy-input" />
          </Field>
          <Field label="Owner">
            <input value={value.owner || ""} onChange={(e) => set({ owner: e.target.value })} className="zy-input" />
          </Field>
          <Field label="Status">
            <select value={value.status} onChange={(e) => set({ status: e.target.value })} className="zy-input" data-testid="projects-editor-status">
              {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </Field>
          <Field label="Colour">
            <input type="color" value={value.color || "#1A4FFF"} onChange={(e) => set({ color: e.target.value })} className="w-full h-[36px] p-1 border border-[#eee] rounded-md cursor-pointer" />
          </Field>
          <Field label="Start date">
            <input type="date" value={value.start_date || ""} onChange={(e) => set({ start_date: e.target.value })} className="zy-input" />
          </Field>
          <Field label="End date">
            <input type="date" value={value.end_date || ""} onChange={(e) => set({ end_date: e.target.value })} className="zy-input" />
          </Field>
          <Field label="Description" className="sm:col-span-2">
            <textarea value={value.description || ""} onChange={(e) => set({ description: e.target.value })} className="zy-input min-h-[80px]" />
          </Field>
        </div>
        <div className="p-4 border-t border-[#eee] flex justify-end gap-2 bg-[#FAFBFF]">
          <button onClick={onCancel} className="px-3 py-2 text-[13px] text-[#666] hover:text-black">Cancel</button>
          <button onClick={onSave} className="zy-btn-primary text-[13px]" data-testid="projects-editor-save-btn">
            {value.id ? "Save changes" : "Create project"}
          </button>
        </div>
      </div>
    </div>
  );
}

// -------- Project detail drawer (tasks + milestones) -----------------------
function ProjectDetail({ id, onClose }) {
  const [data, setData] = useState(null);
  const [taskDraft, setTaskDraft] = useState({ title: "", status: "todo", priority: "medium", assignee: "", due_date: "" });
  const [msDraft, setMsDraft] = useState({ title: "", due_date: "" });
  const [billable, setBillable] = useState(null);
  const [billingOpen, setBillingOpen] = useState(false);

  const loadBillable = async () => {
    try {
      const { data } = await axios.get(`${API}/projects/${id}/billable-summary`, { withCredentials: true });
      setBillable(data);
    } catch { setBillable(null); }
  };

  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/projects/${id}`, { withCredentials: true });
      setData(data);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
    loadBillable();
  };
  useEffect(() => { load(); }, [id]);

  const addTask = async () => {
    if (!taskDraft.title) return toast.error("Task title is required.");
    try {
      await axios.post(`${API}/projects/tasks`, { ...taskDraft, project_id: id }, { withCredentials: true });
      setTaskDraft({ title: "", status: "todo", priority: "medium", assignee: "", due_date: "" });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };
  const changeTaskStatus = async (tid, status) => {
    try {
      await axios.put(`${API}/projects/tasks/${tid}/status`, { status }, { withCredentials: true });
      load();
    } catch (e) { toast.error("Failed."); }
  };
  const removeTask = async (tid) => {
    try { await axios.delete(`${API}/projects/tasks/${tid}`, { withCredentials: true }); load(); } catch { /* noop */ }
  };

  const addMs = async () => {
    if (!msDraft.title) return toast.error("Milestone title is required.");
    try {
      await axios.post(`${API}/projects/milestones`, { ...msDraft, project_id: id }, { withCredentials: true });
      setMsDraft({ title: "", due_date: "" });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };
  const toggleMs = async (mid) => {
    try { await axios.put(`${API}/projects/milestones/${mid}/toggle`, {}, { withCredentials: true }); load(); } catch { /* noop */ }
  };
  const removeMs = async (mid) => {
    try { await axios.delete(`${API}/projects/milestones/${mid}`, { withCredentials: true }); load(); } catch { /* noop */ }
  };

  if (!data) return null;
  const p = data.project;
  const st = STATUS[p.status] || STATUS.planning;

  return (
    <div className="fixed inset-0 bg-black/40 z-40 flex justify-end" data-testid="projects-detail-drawer">
      <div className="bg-white w-full max-w-2xl h-full overflow-y-auto shadow-xl">
        <div className="p-5 border-b border-[#eee] flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-3 h-3 rounded-full shrink-0" style={{ background: p.color || "#1A4FFF" }} />
            <div className="min-w-0">
              <h3 className="text-[18px] font-bold truncate">{p.name}</h3>
              <div className="text-[11.5px] text-[#888]">{p.domain || "—"} · {p.owner || "No owner"}</div>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-[11px] uppercase font-bold px-2 py-0.5 rounded-full" style={{ background: st.bg, color: st.fg }}>{st.label}</span>
            <button onClick={onClose} className="text-[#666] hover:text-black text-lg" data-testid="projects-detail-close">✕</button>
          </div>
        </div>
        <div className="p-5 space-y-6">
          {p.description && <p className="text-[13px] text-[#555]">{p.description}</p>}

          {/* Billable hours → invoice draft */}
          {billable && billable.unbilled_hours > 0 && (
            <div className="border border-[#16a34a] bg-[rgba(34,197,94,0.06)] rounded-xl p-4 flex flex-wrap items-center justify-between gap-3" data-testid="projects-bill-hours-card">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#16a34a] text-white flex items-center justify-center shrink-0">
                  <Euro size={18} />
                </div>
                <div>
                  <div className="text-[13px] font-semibold text-[#0A1628]">
                    {billable.unbilled_hours}h of unbilled billable time
                  </div>
                  <div className="text-[11.5px] text-[#555]">
                    Across {billable.unbilled_lines.length} task{billable.unbilled_lines.length === 1 ? "" : "s"} · {billable.unbilled_entry_count} entries
                  </div>
                </div>
              </div>
              <button
                onClick={() => setBillingOpen(true)}
                className="zy-btn-primary text-[13px]"
                data-testid="projects-bill-hours-btn"
              >
                <Receipt size={13} /> Bill hours → invoice draft
              </button>
            </div>
          )}
          <div>
            <div className="flex items-center justify-between text-[12.5px] mb-1">
              <span className="text-[#666]">Progress · {data.tasks.filter((t) => t.status === "done").length} of {data.tasks.length} tasks done</span>
              <span className="font-semibold tabular-nums">{p.progress}%</span>
            </div>
            <div className="h-2 rounded-full bg-[#eee] overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${p.progress}%`, background: p.color || "#1A4FFF" }} />
            </div>
          </div>

          {/* Tasks */}
          <section>
            <div className="text-[11.5px] uppercase font-bold text-[#888] mb-2 flex items-center gap-1"><Target size={11} /> Tasks</div>
            <div className="space-y-1.5">
              {data.tasks.length === 0 ? (
                <div className="text-[#888] text-[12.5px] italic">No tasks yet.</div>
              ) : data.tasks.map((t) => {
                const ts = TASK_STATUS[t.status] || TASK_STATUS.todo;
                return (
                  <div key={t.id} className="flex items-center gap-2 border border-[#eee] rounded-md px-3 py-2" data-testid={`projects-task-row-${t.id}`}>
                    <button onClick={() => changeTaskStatus(t.id, t.status === "done" ? "todo" : "done")} className="shrink-0" title={t.status === "done" ? "Reopen" : "Mark done"}>
                      <CheckCircle2 size={18} style={{ color: t.status === "done" ? "#16a34a" : "#ccc" }} />
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className={`text-[13px] font-medium truncate ${t.status === "done" ? "line-through text-[#999]" : ""}`}>{t.title}</div>
                      <div className="text-[11px] text-[#888] flex items-center gap-2">
                        {t.assignee && <span>{t.assignee}</span>}
                        {t.due_date && <span className="flex items-center gap-0.5"><Clock size={10} /> {t.due_date}</span>}
                        {t.priority === "high" && <span className="text-[#c00] font-bold">HIGH</span>}
                      </div>
                    </div>
                    <select value={t.status} onChange={(e) => changeTaskStatus(t.id, e.target.value)} className="text-[11px] px-1.5 py-1 border border-[#eee] rounded" data-testid={`projects-task-status-${t.id}`}>
                      {Object.entries(TASK_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                    </select>
                    <button onClick={() => removeTask(t.id)} className="text-[#c00]"><Trash2 size={13} /></button>
                  </div>
                );
              })}
            </div>
            <div className="mt-2 border border-dashed border-[#e5e7ee] rounded-md p-2 grid grid-cols-1 sm:grid-cols-5 gap-2">
              <input value={taskDraft.title} onChange={(e) => setTaskDraft({ ...taskDraft, title: e.target.value })} placeholder="New task title" className="zy-input sm:col-span-2" data-testid="projects-task-draft-title" />
              <input value={taskDraft.assignee} onChange={(e) => setTaskDraft({ ...taskDraft, assignee: e.target.value })} placeholder="Assignee" className="zy-input" />
              <input type="date" value={taskDraft.due_date} onChange={(e) => setTaskDraft({ ...taskDraft, due_date: e.target.value })} className="zy-input" />
              <button onClick={addTask} className="zy-btn-primary text-[12px]" data-testid="projects-task-add-btn"><Plus size={12} /> Add</button>
            </div>
          </section>

          {/* Milestones */}
          <section>
            <div className="text-[11.5px] uppercase font-bold text-[#888] mb-2 flex items-center gap-1"><Flag size={11} /> Milestones</div>
            <div className="space-y-1.5">
              {data.milestones.length === 0 ? (
                <div className="text-[#888] text-[12.5px] italic">No milestones yet.</div>
              ) : data.milestones.map((m) => (
                <div key={m.id} className="flex items-center gap-2 border border-[#eee] rounded-md px-3 py-2" data-testid={`projects-ms-row-${m.id}`}>
                  <button onClick={() => toggleMs(m.id)} className="shrink-0"><CheckCircle2 size={18} style={{ color: m.completed ? "#16a34a" : "#ccc" }} /></button>
                  <div className="flex-1">
                    <div className={`text-[13px] font-medium ${m.completed ? "line-through text-[#999]" : ""}`}>{m.title}</div>
                    {m.due_date && <div className="text-[11px] text-[#888]">Due {m.due_date}</div>}
                  </div>
                  <button onClick={() => removeMs(m.id)} className="text-[#c00]"><Trash2 size={13} /></button>
                </div>
              ))}
            </div>
            <div className="mt-2 border border-dashed border-[#e5e7ee] rounded-md p-2 grid grid-cols-1 sm:grid-cols-3 gap-2">
              <input value={msDraft.title} onChange={(e) => setMsDraft({ ...msDraft, title: e.target.value })} placeholder="Milestone title" className="zy-input" data-testid="projects-ms-draft-title" />
              <input type="date" value={msDraft.due_date} onChange={(e) => setMsDraft({ ...msDraft, due_date: e.target.value })} className="zy-input" />
              <button onClick={addMs} className="zy-btn-primary text-[12px]"><Plus size={12} /> Add milestone</button>
            </div>
          </section>
        </div>
      </div>
      {billingOpen && (
        <BillHoursModal
          projectId={id}
          billable={billable}
          onClose={() => setBillingOpen(false)}
          onDone={() => { setBillingOpen(false); load(); }}
        />
      )}
    </div>
  );
}

function BillHoursModal({ projectId, billable, onClose, onDone }) {
  const navigate = useNavigate();
  const [wonLeads, setWonLeads] = useState([]);
  const [form, setForm] = useState({ lead_id: "", hourly_rate: 150, currency: "EUR", due_in_days: 14, tax_rate: 21 });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/sales/leads?stage=won`, { withCredentials: true });
        const leads = data.leads || [];
        setWonLeads(leads);
        if (leads.length && !form.lead_id) setForm((f) => ({ ...f, lead_id: leads[0].id }));
      } catch { /* noop */ }
    })();
    // Only run once on mount — no other deps we care about.
  }, []);

  const total = (billable?.unbilled_lines || []).reduce(
    (s, l) => s + l.hours * (parseFloat(form.hourly_rate) || 0),
    0,
  );
  const withTax = total * (1 + (parseFloat(form.tax_rate) || 0) / 100);

  const create = async () => {
    if (!form.lead_id) return toast.error("Pick a client (won lead).");
    if (!form.hourly_rate || parseFloat(form.hourly_rate) <= 0) return toast.error("Hourly rate must be > 0.");
    setBusy(true);
    try {
      const { data } = await axios.post(
        `${API}/projects/${projectId}/invoice-billable-time`,
        {
          lead_id: form.lead_id,
          hourly_rate: parseFloat(form.hourly_rate),
          currency: form.currency,
          due_in_days: parseInt(form.due_in_days, 10),
          tax_rate: parseFloat(form.tax_rate),
        },
        { withCredentials: true },
      );
      toast.success(
        `Draft invoice ${data.invoice.number} created for ${data.hours_billed}h. Opening Finance…`,
        { action: { label: "View", onClick: () => navigate("/dashboard/finance") } },
      );
      onDone();
      setTimeout(() => navigate("/dashboard/finance"), 300);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Failed to create invoice.");
    }
    setBusy(false);
  };

  const sym = { EUR: "€", USD: "$", GBP: "£" }[form.currency] || "€";

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center overflow-y-auto p-4" data-testid="projects-bill-hours-modal">
      <div className="bg-white rounded-2xl w-full max-w-xl mt-16 shadow-xl overflow-hidden">
        <div className="p-5 border-b border-[#eee] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Receipt size={17} style={{ color: "#16a34a" }} />
            <h3 className="text-[16px] font-semibold">Bill hours → draft invoice</h3>
          </div>
          <button onClick={onClose} className="text-[#666] hover:text-black">✕</button>
        </div>
        <div className="p-5 space-y-4">
          {wonLeads.length === 0 ? (
            <div className="text-[13px] text-[#c00] bg-[rgba(220,38,38,0.06)] border border-[rgba(220,38,38,0.25)] rounded-md p-3">
              No won leads found. Move a Sales lead to <b>Won</b> first (Sales → Kanban), then come back here.
            </div>
          ) : (
            <>
              <Field label="Client (won lead)">
                <select value={form.lead_id} onChange={(e) => setForm({ ...form, lead_id: e.target.value })} className="zy-input" data-testid="projects-bill-hours-client">
                  {wonLeads.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}{l.company ? ` — ${l.company}` : ""}{l.email ? ` (${l.email})` : ""}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="grid grid-cols-3 gap-2">
                <Field label={`Hourly rate (${sym})`}>
                  <input type="number" step="0.01" value={form.hourly_rate} onChange={(e) => setForm({ ...form, hourly_rate: e.target.value })} className="zy-input" data-testid="projects-bill-hours-rate" />
                </Field>
                <Field label="Currency">
                  <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} className="zy-input">
                    <option value="EUR">EUR</option>
                    <option value="USD">USD</option>
                    <option value="GBP">GBP</option>
                  </select>
                </Field>
                <Field label="Tax %">
                  <input type="number" step="0.1" value={form.tax_rate} onChange={(e) => setForm({ ...form, tax_rate: e.target.value })} className="zy-input" />
                </Field>
                <Field label="Due in (days)" className="col-span-3">
                  <input type="number" step="1" min="0" value={form.due_in_days} onChange={(e) => setForm({ ...form, due_in_days: e.target.value })} className="zy-input max-w-[120px]" />
                </Field>
              </div>

              <div>
                <div className="text-[11.5px] uppercase font-bold text-[#888] mb-1">Line items preview</div>
                <div className="border border-[#eee] rounded-md overflow-hidden">
                  <table className="w-full text-[12.5px]">
                    <thead className="bg-[#F4F6FB] text-[#555]">
                      <tr>
                        <th className="text-left px-3 py-1.5">Task (line)</th>
                        <th className="text-right px-3 py-1.5">Hours</th>
                        <th className="text-right px-3 py-1.5">Line total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(billable?.unbilled_lines || []).map((l) => (
                        <tr key={l.task_id || "_no_task_"} className="border-t border-[#eee]" data-testid={`projects-bill-line-${l.task_id || "notask"}`}>
                          <td className="px-3 py-1.5">{l.task_title}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums">{l.hours}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums">{sym}{(l.hours * (parseFloat(form.hourly_rate) || 0)).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="bg-[#FAFBFF] border-t border-[#0A1628]">
                        <td className="px-3 py-1.5 font-semibold">Subtotal · {billable?.unbilled_hours || 0}h</td>
                        <td />
                        <td className="px-3 py-1.5 text-right font-semibold tabular-nums">{sym}{total.toFixed(2)}</td>
                      </tr>
                      <tr>
                        <td className="px-3 py-1.5 text-[#666]">Total incl. {form.tax_rate}% VAT</td>
                        <td />
                        <td className="px-3 py-1.5 text-right font-bold tabular-nums">{sym}{withTax.toFixed(2)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              <p className="text-[11.5px] text-[#888]">
                A draft invoice will be created in <b>Finance</b> and these time entries will be marked as
                invoiced. Deleting the invoice restores them.
              </p>
            </>
          )}
        </div>
        <div className="p-4 border-t border-[#eee] flex justify-end gap-2 bg-[#FAFBFF]">
          <button onClick={onClose} className="px-3 py-2 text-[13px] text-[#666] hover:text-black">Cancel</button>
          <button
            onClick={create}
            disabled={busy || wonLeads.length === 0}
            className="zy-btn-primary text-[13px] disabled:opacity-50"
            data-testid="projects-bill-hours-confirm-btn"
          >
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Receipt size={13} />}
            {busy ? "Creating…" : "Create draft invoice"}
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
      <p className="mt-1 font-bold text-[18px] sm:text-[20px]" style={{ color: "#0A1628" }}>{value ?? 0}</p>
    </div>
  );
}
