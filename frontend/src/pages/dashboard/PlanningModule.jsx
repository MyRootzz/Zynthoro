/**
 * Planning module — sprints (workspace-wide) with tasks from any project.
 * Session C2 (2026-02) — jury-ready CRUD.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API, formatApiError } from "@/contexts/AuthContext";
import {
  CalendarClock, Plus, Trash2, Loader2, Target,
  CheckCircle2, Play, Edit3, Clock, Trophy,
} from "lucide-react";

const SPRINT_STATUS = {
  planned:   { label: "Planned",   bg: "#F4F6FB",              fg: "#666" },
  active:    { label: "Active",    bg: "rgba(26,79,255,0.12)", fg: "#1A4FFF" },
  completed: { label: "Completed", bg: "rgba(34,197,94,0.12)", fg: "#16a34a" },
};

const emptySprint = () => ({
  name: "", goal: "", start_date: "", end_date: "",
  status: "planned", capacity_hours: "",
});

export default function PlanningModule() {
  const [sprints, setSprints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/planning/sprints`, { withCredentials: true });
      setSprints(data.sprints || []);
      if (!selectedId && data.sprints?.length) setSelectedId(data.sprints[0].id);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
    setLoading(false);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const save = async () => {
    if (!editing.name || !editing.start_date || !editing.end_date) return toast.error("Name and dates are required.");
    try {
      const payload = {
        ...editing,
        capacity_hours: editing.capacity_hours ? parseFloat(editing.capacity_hours) : null,
      };
      if (editing.id) {
        await axios.put(`${API}/planning/sprints/${editing.id}`, payload, { withCredentials: true });
        toast.success("Sprint updated.");
      } else {
        const { data } = await axios.post(`${API}/planning/sprints`, payload, { withCredentials: true });
        toast.success("Sprint created.");
        setSelectedId(data.id);
      }
      setEditing(null);
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this sprint? Tasks will be un-linked but not deleted.")) return;
    try {
      await axios.delete(`${API}/planning/sprints/${id}`, { withCredentials: true });
      toast.success("Sprint deleted.");
      if (selectedId === id) setSelectedId(null);
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const activeCount = sprints.filter((s) => s.status === "active").length;
  const totalTasks = sprints.reduce((s, x) => s + (x.summary?.task_count || 0), 0);
  const totalDone = sprints.reduce((s, x) => s + (x.summary?.done || 0), 0);

  return (
    <div className="space-y-6" data-testid="planning-module">
      <header>
        <h1 className="text-[26px] font-bold tracking-tight text-black flex items-center gap-2">
          <CalendarClock size={22} style={{ color: "#1A4FFF" }} /> Planning
        </h1>
        <p className="text-[14px] text-[#666] mt-1">
          Organise work in sprints — pull tasks in from any project.
        </p>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatPill label="Sprints" value={sprints.length} icon={CalendarClock} accent="#1A4FFF" />
        <StatPill label="Active" value={activeCount} icon={Play} accent="#16a34a" />
        <StatPill label="Total tasks" value={totalTasks} icon={Target} accent="#D97706" />
        <StatPill label="Completed" value={totalDone} icon={Trophy} accent="#1A4FFF" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-4">
        {/* Sprint list */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-[13px] uppercase font-bold text-[#888] tracking-wider">Sprints</h2>
            <button onClick={() => setEditing({ ...emptySprint(), id: null })} className="zy-btn-primary text-[11.5px] px-2.5 py-1" data-testid="planning-new-sprint-btn">
              <Plus size={12} /> New
            </button>
          </div>
          {loading ? <Loader2 className="animate-spin text-[#999]" /> : sprints.length === 0 ? (
            <div className="border border-dashed border-[#e5e7ee] rounded-lg p-6 text-center text-[#888] text-[12.5px]">
              No sprints yet.
            </div>
          ) : sprints.map((s) => {
            const st = SPRINT_STATUS[s.status] || SPRINT_STATUS.planned;
            const isSel = selectedId === s.id;
            return (
              <button
                key={s.id}
                onClick={() => setSelectedId(s.id)}
                data-testid={`planning-sprint-row-${s.id}`}
                className={`w-full text-left border rounded-lg p-3 transition-all ${
                  isSel ? "border-[#1A4FFF] bg-[#F6F9FF] shadow-sm" : "border-[#eee] bg-white hover:border-[#ccc]"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="font-semibold text-[13px] truncate">{s.name}</div>
                  <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded-full shrink-0" style={{ background: st.bg, color: st.fg }}>{st.label}</span>
                </div>
                <div className="text-[11px] text-[#888] mt-0.5 flex items-center gap-1">
                  <Clock size={10} /> {s.start_date} → {s.end_date}
                </div>
                <div className="mt-1.5">
                  <div className="flex items-center justify-between text-[10.5px] text-[#666] mb-0.5">
                    <span>{s.summary?.done || 0} / {s.summary?.task_count || 0} tasks</span>
                    <span className="font-semibold tabular-nums">{s.summary?.progress || 0}%</span>
                  </div>
                  <div className="h-1 rounded-full bg-[#eee] overflow-hidden">
                    <div className="h-full rounded-full bg-[#16a34a]" style={{ width: `${s.summary?.progress || 0}%` }} />
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Selected sprint board */}
        <div>
          {selectedId ? (
            <SprintBoard key={selectedId} sprintId={selectedId} onChange={load} onEdit={(s) => setEditing({ ...s, capacity_hours: s.capacity_hours ?? "" })} onDelete={remove} />
          ) : (
            <div className="border border-dashed border-[#e5e7ee] rounded-xl p-10 text-center text-[#888]">
              Select a sprint to see its tasks.
            </div>
          )}
        </div>
      </div>

      {editing && (
        <SprintEditor value={editing} onChange={setEditing} onCancel={() => setEditing(null)} onSave={save} />
      )}
    </div>
  );
}

// -------- Selected sprint board -------------------------------------------
function SprintBoard({ sprintId, onChange, onEdit, onDelete }) {
  const [data, setData] = useState(null);
  const [available, setAvailable] = useState([]);
  const [picker, setPicker] = useState(false);

  const load = async () => {
    try {
      const [s, a] = await Promise.all([
        axios.get(`${API}/planning/sprints/${sprintId}`, { withCredentials: true }),
        axios.get(`${API}/planning/available-tasks`, { withCredentials: true }),
      ]);
      setData(s.data);
      setAvailable(a.data.tasks || []);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [sprintId]);

  const addTask = async (task_id) => {
    try {
      await axios.post(`${API}/planning/sprints/${sprintId}/tasks`, { task_id }, { withCredentials: true });
      setPicker(false);
      await load();
      onChange();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const removeTask = async (tid) => {
    try {
      await axios.delete(`${API}/planning/sprints/${sprintId}/tasks/${tid}`, { withCredentials: true });
      await load();
      onChange();
    } catch (e) { toast.error("Failed."); }
  };

  const changeTaskStatus = async (tid, status) => {
    try {
      await axios.put(`${API}/projects/tasks/${tid}/status`, { status }, { withCredentials: true });
      await load();
      onChange();
    } catch (e) { toast.error("Failed."); }
  };

  if (!data) return <Loader2 className="animate-spin text-[#999]" />;
  const s = data.sprint;
  const st = SPRINT_STATUS[s.status] || SPRINT_STATUS.planned;

  return (
    <div className="bg-white border border-[#eee] rounded-xl p-5 space-y-5" data-testid={`planning-sprint-board-${sprintId}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-[18px] font-bold truncate">{s.name}</h3>
            <span className="text-[11px] uppercase font-bold px-2 py-0.5 rounded-full" style={{ background: st.bg, color: st.fg }}>{st.label}</span>
          </div>
          <div className="text-[12.5px] text-[#666] mt-0.5">{s.goal || "No goal set"}</div>
          <div className="text-[11.5px] text-[#888] mt-0.5 flex items-center gap-1"><Clock size={11} /> {s.start_date} → {s.end_date}</div>
        </div>
        <div className="flex gap-1">
          <button onClick={() => onEdit(s)} className="text-[#1A4FFF] hover:opacity-70 p-1.5" data-testid="planning-sprint-edit-btn"><Edit3 size={14} /></button>
          <button onClick={() => onDelete(sprintId)} className="text-[#c00] hover:opacity-70 p-1.5"><Trash2 size={14} /></button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center text-[12px]">
        <div className="bg-[#F4F6FB] rounded-lg p-2"><div className="font-bold text-[16px]">{s.summary?.todo || 0}</div><div className="text-[#888]">To do</div></div>
        <div className="bg-[rgba(217,119,6,0.10)] rounded-lg p-2"><div className="font-bold text-[16px] text-[#D97706]">{s.summary?.in_progress || 0}</div><div className="text-[#666]">Doing</div></div>
        <div className="bg-[rgba(34,197,94,0.10)] rounded-lg p-2"><div className="font-bold text-[16px] text-[#16a34a]">{s.summary?.done || 0}</div><div className="text-[#666]">Done</div></div>
      </div>

      <div>
        <div className="flex items-center justify-between text-[12px] mb-1">
          <span className="text-[#666]">Burndown · {s.summary?.done || 0} of {s.summary?.task_count || 0} tasks</span>
          <span className="font-semibold tabular-nums">{s.summary?.progress || 0}%</span>
        </div>
        <div className="h-2 rounded-full bg-[#eee] overflow-hidden">
          <div className="h-full rounded-full bg-[#16a34a] transition-all" style={{ width: `${s.summary?.progress || 0}%` }} />
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="text-[11.5px] uppercase font-bold text-[#888]">Tasks in this sprint ({data.tasks.length})</div>
          <button onClick={() => setPicker(true)} className="zy-btn-outline text-[11.5px] px-2.5 py-1" data-testid="planning-add-task-btn"><Plus size={12} /> Add task</button>
        </div>
        <div className="space-y-1.5">
          {data.tasks.length === 0 ? (
            <div className="text-[#888] text-[12.5px] italic">No tasks yet. Click <b>Add task</b> to pull in tasks from your projects.</div>
          ) : data.tasks.map((t) => (
            <div key={t.id} className="flex items-center gap-2 border border-[#eee] rounded-md px-3 py-2" data-testid={`planning-sprint-task-${t.id}`}>
              <button onClick={() => changeTaskStatus(t.id, t.status === "done" ? "todo" : "done")}>
                <CheckCircle2 size={17} style={{ color: t.status === "done" ? "#16a34a" : "#ccc" }} />
              </button>
              <div className="flex-1 min-w-0">
                <div className={`text-[13px] font-medium truncate ${t.status === "done" ? "line-through text-[#999]" : ""}`}>{t.title}</div>
                {t.project_name && (
                  <div className="text-[11px] text-[#888] flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: t.project_color || "#1A4FFF" }} />
                    {t.project_name}
                  </div>
                )}
              </div>
              <select value={t.status} onChange={(e) => changeTaskStatus(t.id, e.target.value)} className="text-[11px] px-1.5 py-1 border border-[#eee] rounded">
                <option value="todo">To do</option>
                <option value="in_progress">Doing</option>
                <option value="done">Done</option>
              </select>
              <button onClick={() => removeTask(t.id)} className="text-[#888] hover:text-[#c00]" title="Remove from sprint"><Trash2 size={13} /></button>
            </div>
          ))}
        </div>
      </div>

      {picker && (
        <TaskPicker tasks={available} onPick={addTask} onClose={() => setPicker(false)} />
      )}
    </div>
  );
}

function TaskPicker({ tasks, onPick, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-40 flex items-start justify-center overflow-y-auto p-4" data-testid="planning-task-picker">
      <div className="bg-white rounded-2xl w-full max-w-lg mt-16 shadow-xl overflow-hidden">
        <div className="p-4 border-b border-[#eee] flex items-center justify-between">
          <h3 className="text-[15px] font-semibold">Add task to sprint</h3>
          <button onClick={onClose} className="text-[#666] hover:text-black">✕</button>
        </div>
        <div className="p-4 max-h-[60vh] overflow-y-auto">
          {tasks.length === 0 ? (
            <p className="text-[13px] text-[#888] text-center py-8">
              No un-sprinted tasks available. Create tasks under a project first.
            </p>
          ) : (
            <ul className="space-y-1">
              {tasks.map((t) => (
                <li key={t.id}>
                  <button onClick={() => onPick(t.id)} data-testid={`planning-picker-task-${t.id}`} className="w-full text-left border border-[#eee] rounded-md px-3 py-2 hover:border-[#1A4FFF] hover:bg-[#F6F9FF] transition-colors">
                    <div className="text-[13px] font-medium">{t.title}</div>
                    {t.project_name && <div className="text-[11px] text-[#888]">{t.project_name}</div>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

// -------- Sprint editor ----------------------------------------------------
function SprintEditor({ value, onChange, onCancel, onSave }) {
  const set = (patch) => onChange({ ...value, ...patch });
  return (
    <div className="fixed inset-0 bg-black/40 z-40 flex items-start justify-center overflow-y-auto p-4" data-testid="planning-editor-modal">
      <div className="bg-white rounded-2xl w-full max-w-lg mt-16 shadow-xl overflow-hidden">
        <div className="p-5 border-b border-[#eee] flex items-center justify-between">
          <h3 className="text-[16px] font-semibold">{value.id ? "Edit sprint" : "New sprint"}</h3>
          <button onClick={onCancel} className="text-[#666] hover:text-black">✕</button>
        </div>
        <div className="p-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Sprint name*" className="sm:col-span-2">
            <input value={value.name} onChange={(e) => set({ name: e.target.value })} className="zy-input" data-testid="planning-editor-name" />
          </Field>
          <Field label="Goal" className="sm:col-span-2">
            <textarea value={value.goal || ""} onChange={(e) => set({ goal: e.target.value })} className="zy-input min-h-[60px]" placeholder="e.g. Ship the invoice PDF export by Friday." />
          </Field>
          <Field label="Start date*">
            <input type="date" value={value.start_date || ""} onChange={(e) => set({ start_date: e.target.value })} className="zy-input" data-testid="planning-editor-start" />
          </Field>
          <Field label="End date*">
            <input type="date" value={value.end_date || ""} onChange={(e) => set({ end_date: e.target.value })} className="zy-input" data-testid="planning-editor-end" />
          </Field>
          <Field label="Status">
            <select value={value.status} onChange={(e) => set({ status: e.target.value })} className="zy-input">
              {Object.entries(SPRINT_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </Field>
          <Field label="Capacity (hours)">
            <input type="number" step="1" value={value.capacity_hours || ""} onChange={(e) => set({ capacity_hours: e.target.value })} className="zy-input" placeholder="Optional" />
          </Field>
        </div>
        <div className="p-4 border-t border-[#eee] flex justify-end gap-2 bg-[#FAFBFF]">
          <button onClick={onCancel} className="px-3 py-2 text-[13px] text-[#666] hover:text-black">Cancel</button>
          <button onClick={onSave} className="zy-btn-primary text-[13px]" data-testid="planning-editor-save-btn">
            {value.id ? "Save changes" : "Create sprint"}
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
