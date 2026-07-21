/**
 * Time Tracking module — live timer, manual entries, weekly timesheet, CSV.
 * Session C2 (2026-02) — jury-ready CRUD.
 */
import { useEffect, useRef, useState, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API, formatApiError } from "@/contexts/AuthContext";
import {
  Timer, Play, Square, Plus, Trash2, Loader2, Clock,
  Download, Euro, CalendarDays,
} from "lucide-react";

const DAY_LABEL = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function fmtSecs(s) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}
const fmtHours = (h) => Number(h || 0).toLocaleString("nl-NL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function TimeTrackingModule() {
  const [tab, setTab] = useState("timer");
  return (
    <div className="space-y-6" data-testid="timetracking-module">
      <header>
        <h1 className="text-[26px] font-bold tracking-tight text-black flex items-center gap-2">
          <Timer size={22} style={{ color: "#1A4FFF" }} /> Time Tracking
        </h1>
        <p className="text-[14px] text-[#666] mt-1">
          Start a live timer or log time manually. Export weekly timesheets to CSV.
        </p>
      </header>
      <nav className="flex flex-wrap gap-1 border-b border-[#eee]">
        {[
          { id: "timer",   label: "Timer & entries", icon: Timer },
          { id: "sheet",   label: "Weekly timesheet", icon: CalendarDays },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            data-testid={`tt-tab-${t.id}`}
            className={`px-4 py-2.5 text-[13.5px] font-medium border-b-2 flex items-center gap-2 transition-colors ${
              tab === t.id ? "border-[#1A4FFF] text-[#1A4FFF]" : "border-transparent text-[#666] hover:text-black"
            }`}
          >
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </nav>
      {tab === "timer" ? <TimerPanel /> : <TimesheetPanel />}
    </div>
  );
}

// -------- Timer + entries --------------------------------------------------
function TimerPanel() {
  const [timer, setTimer] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [entries, setEntries] = useState([]);
  const [totals, setTotals] = useState({ hours: 0, billable_hours: 0, count: 0 });
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [form, setForm] = useState({ project_id: "", task_id: "", notes: "", billable: true });
  const [manual, setManual] = useState({
    project_id: "", task_id: "",
    date: new Date().toISOString().slice(0, 10),
    hours: "", notes: "", billable: true,
  });
  const tickRef = useRef(null);

  const loadAll = async () => {
    try {
      const [t, e, p] = await Promise.all([
        axios.get(`${API}/time-tracking/timer`, { withCredentials: true }),
        axios.get(`${API}/time-tracking/entries`, { withCredentials: true }),
        axios.get(`${API}/projects`, { withCredentials: true }),
      ]);
      setTimer(t.data.timer);
      setElapsed(t.data.timer?.elapsed_seconds || 0);
      setEntries(e.data.entries || []);
      setTotals(e.data.totals || { hours: 0, billable_hours: 0, count: 0 });
      setProjects(p.data.projects || []);
    } catch (err) { toast.error(formatApiError(err?.response?.data?.detail) || "Failed."); }
  };
  useEffect(() => { loadAll(); }, []);

  // Live-tick when a timer is running.
  useEffect(() => {
    if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null; }
    if (timer) {
      tickRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    }
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, [timer]);

  // When project selected in the timer form, load its tasks.
  useEffect(() => {
    (async () => {
      if (!form.project_id) { setTasks([]); return; }
      try {
        const { data } = await axios.get(`${API}/projects/${form.project_id}/tasks`, { withCredentials: true });
        setTasks(data.tasks || []);
      } catch { setTasks([]); }
    })();
  }, [form.project_id]);

  const start = async () => {
    try {
      const { data } = await axios.post(`${API}/time-tracking/timer/start`, form, { withCredentials: true });
      setTimer(data.timer);
      setElapsed(0);
      if (data.auto_committed) {
        toast.success(`Timer swapped. Committed ${fmtHours(data.auto_committed.hours)}h from previous timer.`);
      } else {
        toast.success("Timer started.");
      }
      loadAll();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const stop = async () => {
    try {
      const { data } = await axios.post(`${API}/time-tracking/timer/stop`, {}, { withCredentials: true });
      setTimer(null);
      setElapsed(0);
      toast.success(`Timer stopped. ${fmtHours(data.entry.hours)}h saved.`);
      loadAll();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const cancel = async () => {
    if (!window.confirm("Discard the running timer? Elapsed time will NOT be saved.")) return;
    try {
      await axios.delete(`${API}/time-tracking/timer`, { withCredentials: true });
      setTimer(null); setElapsed(0);
      toast.success("Timer discarded.");
    } catch (e) { toast.error("Failed."); }
  };

  const addManual = async () => {
    if (!manual.hours || parseFloat(manual.hours) <= 0) return toast.error("Hours must be > 0.");
    try {
      await axios.post(`${API}/time-tracking/entries`, {
        ...manual,
        project_id: manual.project_id || null,
        task_id: manual.task_id || null,
        hours: parseFloat(manual.hours),
      }, { withCredentials: true });
      setManual({ ...manual, hours: "", notes: "" });
      toast.success("Entry saved.");
      loadAll();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const removeEntry = async (eid) => {
    if (!window.confirm("Delete this time entry?")) return;
    try {
      await axios.delete(`${API}/time-tracking/entries/${eid}`, { withCredentials: true });
      loadAll();
    } catch (e) { toast.error("Failed."); }
  };

  const downloadCsv = () => {
    window.open(`${API}/time-tracking/entries/export.csv`, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="space-y-5">
      {/* Timer card */}
      <div
        className={`rounded-2xl p-5 border ${
          timer ? "border-[#16a34a] bg-[rgba(34,197,94,0.06)]" : "border-[#eee] bg-white"
        }`}
        data-testid="tt-timer-card"
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-white text-[22px] font-bold tabular-nums shrink-0"
              style={{ background: timer ? "#16a34a" : "#0A1628" }}
            >
              <Timer size={26} />
            </div>
            <div>
              <div className="text-[12px] uppercase font-bold text-[#888] tracking-wider">
                {timer ? "Running · " + (timer.project_name || "No project") : "Ready to start"}
              </div>
              <div className="text-[26px] font-bold tabular-nums" data-testid="tt-timer-elapsed">
                {fmtSecs(elapsed)}
              </div>
              {timer?.notes && <div className="text-[12px] text-[#666] mt-0.5">“{timer.notes}”</div>}
            </div>
          </div>
          <div className="flex gap-2">
            {timer ? (
              <>
                <button onClick={stop} className="zy-btn-primary flex items-center gap-1.5 text-[13px]" data-testid="tt-timer-stop-btn">
                  <Square size={14} /> Stop & save
                </button>
                <button onClick={cancel} className="zy-btn-outline text-[13px]">Discard</button>
              </>
            ) : (
              <button onClick={start} className="zy-btn-primary flex items-center gap-1.5 text-[13px]" data-testid="tt-timer-start-btn">
                <Play size={14} /> Start timer
              </button>
            )}
          </div>
        </div>
        {!timer && (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-4 gap-2">
            <select value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value, task_id: "" })} className="zy-input" data-testid="tt-timer-project">
              <option value="">Project (optional)</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <select value={form.task_id} onChange={(e) => setForm({ ...form, task_id: e.target.value })} className="zy-input" disabled={!form.project_id}>
              <option value="">Task (optional)</option>
              {tasks.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
            </select>
            <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="What are you working on?" className="zy-input sm:col-span-2" data-testid="tt-timer-notes" />
          </div>
        )}
      </div>

      {/* Stats + CSV */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatPill label="Entries" value={totals.count} icon={Clock} accent="#1A4FFF" />
        <StatPill label="Total hours" value={`${fmtHours(totals.hours)}h`} icon={CalendarDays} accent="#0A1628" />
        <StatPill label="Billable" value={`${fmtHours(totals.billable_hours)}h`} icon={Euro} accent="#16a34a" />
        <div className="bg-white border border-[#eee] rounded-xl p-3 sm:p-4 flex items-center justify-center">
          <button onClick={downloadCsv} className="zy-btn-outline text-[13px]" data-testid="tt-export-csv-btn">
            <Download size={13} /> Export CSV
          </button>
        </div>
      </div>

      {/* Add manual entry */}
      <div className="bg-white border border-[#eee] rounded-xl p-4">
        <div className="text-[12.5px] font-semibold mb-2 flex items-center gap-1"><Plus size={13} /> Add manual entry</div>
        <div className="grid grid-cols-2 sm:grid-cols-6 gap-2">
          <input type="date" value={manual.date} onChange={(e) => setManual({ ...manual, date: e.target.value })} className="zy-input" data-testid="tt-manual-date" />
          <input type="number" step="0.25" value={manual.hours} onChange={(e) => setManual({ ...manual, hours: e.target.value })} placeholder="Hours" className="zy-input" data-testid="tt-manual-hours" />
          <select value={manual.project_id} onChange={(e) => setManual({ ...manual, project_id: e.target.value, task_id: "" })} className="zy-input" data-testid="tt-manual-project">
            <option value="">Project (opt.)</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <input value={manual.notes} onChange={(e) => setManual({ ...manual, notes: e.target.value })} placeholder="Notes" className="zy-input sm:col-span-2" />
          <button onClick={addManual} className="zy-btn-primary text-[13px]" data-testid="tt-manual-save-btn"><Plus size={13} /> Add</button>
        </div>
      </div>

      {/* Entries table */}
      <div className="bg-white border border-[#eee] rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 bg-[#F4F6FB] text-[12px] uppercase font-bold text-[#555] flex items-center justify-between">
          <span>Recent entries · {entries.length}</span>
        </div>
        {entries.length === 0 ? (
          <div className="p-6 text-center text-[#888] text-[13px]">No entries yet.</div>
        ) : (
          <table className="w-full text-[13px]">
            <thead className="text-[#555]">
              <tr className="border-b border-[#eee]">
                <th className="text-left px-4 py-2">Date</th>
                <th className="text-left px-4 py-2">Project · Task</th>
                <th className="text-right px-4 py-2">Hours</th>
                <th className="text-left px-4 py-2">Notes</th>
                <th className="text-left px-4 py-2">Billable</th>
                <th className="w-1" />
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-t border-[#eee]" data-testid={`tt-entry-row-${e.id}`}>
                  <td className="px-4 py-2 text-[#555]">{e.date}</td>
                  <td className="px-4 py-2">
                    {e.project_name ? (
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ background: e.project_color || "#1A4FFF" }} />
                        <span className="font-medium">{e.project_name}</span>
                        {e.task_title && <span className="text-[#888]"> · {e.task_title}</span>}
                      </div>
                    ) : <span className="text-[#aaa]">—</span>}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums font-semibold">{fmtHours(e.hours)}h</td>
                  <td className="px-4 py-2 text-[#666]">{e.notes || "—"}</td>
                  <td className="px-4 py-2">
                    {e.billable ? (
                      <span className="text-[11px] uppercase font-bold px-2 py-0.5 rounded-full bg-[rgba(34,197,94,0.12)] text-[#16a34a]">Billable</span>
                    ) : <span className="text-[#888] text-[11px]">Non-billable</span>}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => removeEntry(e.id)} className="text-[#c00]" data-testid={`tt-entry-del-${e.id}`}><Trash2 size={13} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// -------- Weekly timesheet -------------------------------------------------
function TimesheetPanel() {
  const [weekOf, setWeekOf] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);

  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/time-tracking/timesheet?week_of=${weekOf}`, { withCredentials: true });
      setData(data);
    } catch (e) { toast.error("Failed to load timesheet."); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [weekOf]);

  const shift = (delta) => {
    const d = new Date(weekOf);
    d.setDate(d.getDate() + delta);
    setWeekOf(d.toISOString().slice(0, 10));
  };

  const daysHeader = useMemo(() => {
    if (!data) return [];
    return data.days.map((iso, i) => ({
      iso, label: `${DAY_LABEL[i]} ${iso.slice(8)}`,
    }));
  }, [data]);

  if (!data) return <Loader2 className="animate-spin text-[#999]" />;

  return (
    <div className="space-y-4" data-testid="tt-timesheet">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button onClick={() => shift(-7)} className="zy-btn-outline text-[12px] px-2.5 py-1">◀ Prev</button>
          <input type="date" value={weekOf} onChange={(e) => setWeekOf(e.target.value)} className="zy-input max-w-[160px]" data-testid="tt-timesheet-week" />
          <button onClick={() => shift(7)} className="zy-btn-outline text-[12px] px-2.5 py-1">Next ▶</button>
          <button onClick={() => setWeekOf(new Date().toISOString().slice(0, 10))} className="text-[12px] text-[#1A4FFF] hover:underline ml-2">This week</button>
        </div>
        <div className="text-[13px] text-[#555]">
          Week of <b>{data.week_of}</b> · grand total <b className="tabular-nums">{fmtHours(data.grand_total)}h</b>
        </div>
      </div>
      <div className="bg-white border border-[#eee] rounded-xl overflow-x-auto">
        <table className="w-full text-[12.5px]">
          <thead className="bg-[#F4F6FB] text-[#555]">
            <tr>
              <th className="text-left px-3 py-2">Project · Task</th>
              {daysHeader.map((d) => (
                <th key={d.iso} className="text-center px-2 py-2 whitespace-nowrap">{d.label}</th>
              ))}
              <th className="text-right px-3 py-2">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.length === 0 ? (
              <tr><td colSpan={9} className="text-center text-[#888] py-8">No time logged this week.</td></tr>
            ) : data.rows.map((r, i) => (
              <tr key={i} className="border-t border-[#eee]">
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: r.project_color }} />
                    <span className="font-semibold">{r.project_name}</span>
                    {r.task_title && <span className="text-[#666]"> · {r.task_title}</span>}
                  </div>
                </td>
                {data.days.map((d) => (
                  <td key={d} className="text-center px-2 py-2 tabular-nums text-[#555]">
                    {r.days[d] ? fmtHours(r.days[d]) : <span className="text-[#ccc]">·</span>}
                  </td>
                ))}
                <td className="text-right px-3 py-2 font-bold tabular-nums">{fmtHours(r.total)}</td>
              </tr>
            ))}
          </tbody>
          {data.rows.length > 0 && (
            <tfoot>
              <tr className="border-t-2 border-[#0A1628] bg-[#FAFBFF] font-semibold">
                <td className="px-3 py-2">Daily total</td>
                {data.days.map((d) => (
                  <td key={d} className="text-center px-2 py-2 tabular-nums">{data.day_totals[d] ? fmtHours(data.day_totals[d]) : "·"}</td>
                ))}
                <td className="text-right px-3 py-2 tabular-nums">{fmtHours(data.grand_total)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
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
