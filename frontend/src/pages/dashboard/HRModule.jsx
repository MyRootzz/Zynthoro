/**
 * HR module — Employees / Contracts / Leave Requests.
 * Session B (2026-07-21) — jury-ready CRUD.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API, formatApiError } from "@/contexts/AuthContext";
import { Users, FileText, CalendarDays, Plus, Trash2, CheckCircle2, XCircle, Loader2 } from "lucide-react";

const TABS = [
  { id: "employees",  label: "Employees",       icon: Users },
  { id: "contracts",  label: "Contracts",       icon: FileText },
  { id: "leave",      label: "Leave requests",  icon: CalendarDays },
];

export default function HRModule() {
  const [tab, setTab] = useState("employees");
  return (
    <div className="space-y-6" data-testid="hr-module">
      <header>
        <h1 className="text-[26px] font-bold tracking-tight text-black">HR & Personnel</h1>
        <p className="text-[14px] text-[#666] mt-1">Manage your team, contracts, and leave requests.</p>
      </header>
      <nav className="flex flex-wrap gap-1 border-b border-[#eee]">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            data-testid={`hr-tab-${t.id}`}
            className={`px-4 py-2.5 text-[13.5px] font-medium border-b-2 flex items-center gap-2 transition-colors ${
              tab === t.id ? "border-[#1A4FFF] text-[#1A4FFF]" : "border-transparent text-[#666] hover:text-black"
            }`}
          >
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </nav>
      <div>
        {tab === "employees" && <EmployeesPanel />}
        {tab === "contracts" && <ContractsPanel />}
        {tab === "leave" && <LeavePanel />}
      </div>
    </div>
  );
}

// -------- Employees ---------------------------------------------------------
function EmployeesPanel() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", job_title: "", department: "", employment_type: "full_time", start_date: "", salary_eur: "" });

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/hr/employees`, { withCredentials: true });
      setRows(data.employees || []);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to load employees."); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.first_name || !form.last_name) return toast.error("First and last name are required.");
    try {
      const payload = { ...form, salary_eur: form.salary_eur ? parseFloat(form.salary_eur) : null };
      await axios.post(`${API}/hr/employees`, payload, { withCredentials: true });
      toast.success("Employee added.");
      setShowForm(false);
      setForm({ first_name: "", last_name: "", email: "", job_title: "", department: "", employment_type: "full_time", start_date: "", salary_eur: "" });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to add employee."); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this employee? All linked contracts and leave requests will be removed.")) return;
    try {
      await axios.delete(`${API}/hr/employees/${id}`, { withCredentials: true });
      toast.success("Employee deleted.");
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to delete."); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold">{rows.length} employee{rows.length === 1 ? "" : "s"}</h2>
        <button onClick={() => setShowForm(!showForm)} className="zy-btn-primary flex items-center gap-1.5 text-[13px]" data-testid="hr-emp-add-btn">
          <Plus size={14} /> Add employee
        </button>
      </div>
      {showForm && (
        <div className="border border-[#eee] rounded-xl p-4 bg-white grid grid-cols-1 sm:grid-cols-2 gap-3">
          {["first_name","last_name","email","job_title","department","start_date","salary_eur"].map((k) => (
            <input key={k} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              placeholder={k.replace("_", " ")}
              type={k === "start_date" ? "date" : k === "salary_eur" ? "number" : "text"}
              className="text-[13px] px-3 py-2 border border-[#eee] rounded-md focus:border-[#1A4FFF] outline-none"
              data-testid={`hr-emp-input-${k}`} />
          ))}
          <select value={form.employment_type} onChange={(e) => setForm({ ...form, employment_type: e.target.value })}
            className="text-[13px] px-3 py-2 border border-[#eee] rounded-md focus:border-[#1A4FFF] outline-none" data-testid="hr-emp-input-type">
            <option value="full_time">Full time</option>
            <option value="part_time">Part time</option>
            <option value="contractor">Contractor</option>
            <option value="intern">Intern</option>
          </select>
          <div className="col-span-full flex gap-2 justify-end mt-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-2 text-[13px] text-[#666] hover:text-black">Cancel</button>
            <button onClick={create} className="zy-btn-primary text-[13px]" data-testid="hr-emp-save-btn">Save employee</button>
          </div>
        </div>
      )}
      {loading ? <Loader2 className="animate-spin text-[#999]" /> : rows.length === 0 ? (
        <div className="border border-dashed border-[#e5e7ee] rounded-xl p-10 text-center text-[#888]">
          No employees yet. Click "Add employee" to get started.
        </div>
      ) : (
        <div className="border border-[#eee] rounded-xl overflow-hidden">
          <table className="w-full text-[13px]">
            <thead className="bg-[#F4F6FB] text-[#555]">
              <tr>
                <th className="text-left px-4 py-2.5">Name</th>
                <th className="text-left px-4 py-2.5">Job title</th>
                <th className="text-left px-4 py-2.5">Department</th>
                <th className="text-left px-4 py-2.5">Type</th>
                <th className="text-right px-4 py-2.5">Salary (€)</th>
                <th className="text-right px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.id} className="border-t border-[#eee]" data-testid={`hr-emp-row-${e.id}`}>
                  <td className="px-4 py-2.5 font-medium text-[#111]">{e.first_name} {e.last_name}<div className="text-[11.5px] text-[#888]">{e.email || "—"}</div></td>
                  <td className="px-4 py-2.5 text-[#555]">{e.job_title || "—"}</td>
                  <td className="px-4 py-2.5 text-[#555]">{e.department || "—"}</td>
                  <td className="px-4 py-2.5 text-[#555]">{(e.employment_type || "—").replace("_", " ")}</td>
                  <td className="px-4 py-2.5 text-right text-[#555]">{e.salary_eur != null ? Number(e.salary_eur).toLocaleString("nl-NL", { minimumFractionDigits: 0 }) : "—"}</td>
                  <td className="px-4 py-2.5 text-right"><span className="text-[11px] uppercase font-bold px-2 py-0.5 rounded-full bg-[#E8FFE9] text-[#0F7A2A]">{e.status || "active"}</span></td>
                  <td className="px-4 py-2.5 text-right">
                    <button onClick={() => remove(e.id)} className="text-[#c00] hover:opacity-80" data-testid={`hr-emp-del-${e.id}`}><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// -------- Contracts --------------------------------------------------------
function ContractsPanel() {
  const [rows, setRows] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ employee_id: "", contract_type: "permanent", start_date: "", end_date: "", hours_per_week: 40, salary_eur: "", notes: "" });

  const load = async () => {
    try {
      const [c, e] = await Promise.all([
        axios.get(`${API}/hr/contracts`, { withCredentials: true }),
        axios.get(`${API}/hr/employees`, { withCredentials: true }),
      ]);
      setRows(c.data.contracts || []);
      setEmployees(e.data.employees || []);
    } catch (err) { toast.error(formatApiError(err?.response?.data?.detail) || "Failed to load contracts."); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.employee_id || !form.start_date) return toast.error("Employee and start date are required.");
    try {
      await axios.post(`${API}/hr/contracts`, {
        ...form,
        hours_per_week: parseFloat(form.hours_per_week) || 40,
        salary_eur: form.salary_eur ? parseFloat(form.salary_eur) : null,
      }, { withCredentials: true });
      toast.success("Contract added.");
      setShowForm(false);
      setForm({ employee_id: "", contract_type: "permanent", start_date: "", end_date: "", hours_per_week: 40, salary_eur: "", notes: "" });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to add contract."); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this contract?")) return;
    try { await axios.delete(`${API}/hr/contracts/${id}`, { withCredentials: true }); load(); } catch { /* noop */ }
  };

  const empName = (id) => {
    const e = employees.find((x) => x.id === id);
    return e ? `${e.first_name} ${e.last_name}` : "—";
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold">{rows.length} contract{rows.length === 1 ? "" : "s"}</h2>
        <button onClick={() => setShowForm(!showForm)} className="zy-btn-primary flex items-center gap-1.5 text-[13px]" data-testid="hr-contract-add-btn">
          <Plus size={14} /> New contract
        </button>
      </div>
      {showForm && (
        <div className="border border-[#eee] rounded-xl p-4 bg-white grid grid-cols-1 sm:grid-cols-2 gap-3">
          <select value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })}
            className="text-[13px] px-3 py-2 border border-[#eee] rounded-md" data-testid="hr-contract-emp">
            <option value="">Select employee…</option>
            {employees.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
          </select>
          <select value={form.contract_type} onChange={(e) => setForm({ ...form, contract_type: e.target.value })}
            className="text-[13px] px-3 py-2 border border-[#eee] rounded-md">
            <option value="permanent">Permanent</option>
            <option value="fixed_term">Fixed term</option>
            <option value="freelance">Freelance</option>
            <option value="internship">Internship</option>
          </select>
          <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="text-[13px] px-3 py-2 border border-[#eee] rounded-md" data-testid="hr-contract-start" />
          <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className="text-[13px] px-3 py-2 border border-[#eee] rounded-md" placeholder="End date (optional)" />
          <input type="number" value={form.hours_per_week} onChange={(e) => setForm({ ...form, hours_per_week: e.target.value })} className="text-[13px] px-3 py-2 border border-[#eee] rounded-md" placeholder="Hours/week" />
          <input type="number" value={form.salary_eur} onChange={(e) => setForm({ ...form, salary_eur: e.target.value })} className="text-[13px] px-3 py-2 border border-[#eee] rounded-md" placeholder="Salary (€)" />
          <div className="col-span-full flex gap-2 justify-end">
            <button onClick={() => setShowForm(false)} className="px-3 py-2 text-[13px] text-[#666]">Cancel</button>
            <button onClick={create} className="zy-btn-primary text-[13px]" data-testid="hr-contract-save">Save contract</button>
          </div>
        </div>
      )}
      {rows.length === 0 ? (
        <div className="border border-dashed border-[#e5e7ee] rounded-xl p-10 text-center text-[#888]">No contracts yet.</div>
      ) : (
        <div className="border border-[#eee] rounded-xl overflow-hidden">
          <table className="w-full text-[13px]">
            <thead className="bg-[#F4F6FB] text-[#555]">
              <tr><th className="text-left px-4 py-2.5">Employee</th><th className="text-left px-4 py-2.5">Type</th><th className="text-left px-4 py-2.5">Start</th><th className="text-left px-4 py-2.5">End</th><th className="text-right px-4 py-2.5">Hrs/wk</th><th className="text-right px-4 py-2.5">Salary</th><th /></tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className="border-t border-[#eee]" data-testid={`hr-contract-row-${c.id}`}>
                  <td className="px-4 py-2.5 font-medium">{empName(c.employee_id)}</td>
                  <td className="px-4 py-2.5 text-[#555]">{c.contract_type.replace("_", " ")}</td>
                  <td className="px-4 py-2.5 text-[#555]">{c.start_date}</td>
                  <td className="px-4 py-2.5 text-[#555]">{c.end_date || "—"}</td>
                  <td className="px-4 py-2.5 text-right text-[#555]">{c.hours_per_week}</td>
                  <td className="px-4 py-2.5 text-right text-[#555]">{c.salary_eur ? `€${Number(c.salary_eur).toLocaleString("nl-NL")}` : "—"}</td>
                  <td className="px-4 py-2.5 text-right"><button onClick={() => remove(c.id)} className="text-[#c00]"><Trash2 size={14} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// -------- Leave requests ---------------------------------------------------
function LeavePanel() {
  const [rows, setRows] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ employee_id: "", kind: "holiday", start_date: "", end_date: "", reason: "" });

  const load = async () => {
    try {
      const [l, e] = await Promise.all([
        axios.get(`${API}/hr/leave-requests`, { withCredentials: true }),
        axios.get(`${API}/hr/employees`, { withCredentials: true }),
      ]);
      setRows(l.data.leave_requests || []);
      setEmployees(e.data.employees || []);
    } catch (err) { toast.error("Failed to load leave requests."); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.employee_id || !form.start_date || !form.end_date) return toast.error("Employee, start and end dates are required.");
    try {
      await axios.post(`${API}/hr/leave-requests`, form, { withCredentials: true });
      toast.success("Leave request submitted.");
      setShowForm(false);
      setForm({ employee_id: "", kind: "holiday", start_date: "", end_date: "", reason: "" });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const decide = async (id, status) => {
    try {
      await axios.put(`${API}/hr/leave-requests/${id}/decide`, { status }, { withCredentials: true });
      toast.success(`Leave ${status}.`);
      load();
    } catch (e) { toast.error("Failed to decide."); }
  };

  const empName = (id) => {
    const e = employees.find((x) => x.id === id);
    return e ? `${e.first_name} ${e.last_name}` : "—";
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold">{rows.length} request{rows.length === 1 ? "" : "s"}</h2>
        <button onClick={() => setShowForm(!showForm)} className="zy-btn-primary flex items-center gap-1.5 text-[13px]" data-testid="hr-leave-add-btn"><Plus size={14} /> New request</button>
      </div>
      {showForm && (
        <div className="border border-[#eee] rounded-xl p-4 bg-white grid grid-cols-1 sm:grid-cols-2 gap-3">
          <select value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} className="text-[13px] px-3 py-2 border border-[#eee] rounded-md" data-testid="hr-leave-emp">
            <option value="">Select employee…</option>
            {employees.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
          </select>
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className="text-[13px] px-3 py-2 border border-[#eee] rounded-md">
            {["holiday","sick","parental","unpaid","other"].map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="text-[13px] px-3 py-2 border border-[#eee] rounded-md" />
          <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className="text-[13px] px-3 py-2 border border-[#eee] rounded-md" />
          <textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="Reason (optional)" className="col-span-full text-[13px] px-3 py-2 border border-[#eee] rounded-md min-h-[70px]" />
          <div className="col-span-full flex gap-2 justify-end">
            <button onClick={() => setShowForm(false)} className="px-3 py-2 text-[13px] text-[#666]">Cancel</button>
            <button onClick={create} className="zy-btn-primary text-[13px]" data-testid="hr-leave-save">Submit</button>
          </div>
        </div>
      )}
      {rows.length === 0 ? (
        <div className="border border-dashed border-[#e5e7ee] rounded-xl p-10 text-center text-[#888]">No leave requests yet.</div>
      ) : (
        <div className="border border-[#eee] rounded-xl overflow-hidden">
          <table className="w-full text-[13px]">
            <thead className="bg-[#F4F6FB] text-[#555]">
              <tr><th className="text-left px-4 py-2.5">Employee</th><th className="text-left px-4 py-2.5">Kind</th><th className="text-left px-4 py-2.5">Dates</th><th className="text-right px-4 py-2.5">Days</th><th className="text-right px-4 py-2.5">Status</th><th className="px-4 py-2.5" /></tr>
            </thead>
            <tbody>
              {rows.map((l) => (
                <tr key={l.id} className="border-t border-[#eee]" data-testid={`hr-leave-row-${l.id}`}>
                  <td className="px-4 py-2.5 font-medium">{empName(l.employee_id)}</td>
                  <td className="px-4 py-2.5 text-[#555]">{l.kind}</td>
                  <td className="px-4 py-2.5 text-[#555]">{l.start_date} → {l.end_date}</td>
                  <td className="px-4 py-2.5 text-right text-[#555]">{l.days}</td>
                  <td className="px-4 py-2.5 text-right">
                    <span className={`text-[11px] uppercase font-bold px-2 py-0.5 rounded-full ${
                      l.status === "approved" ? "bg-[#E8FFE9] text-[#0F7A2A]" :
                      l.status === "rejected" ? "bg-[#FFE8E8] text-[#a10404]" :
                      "bg-[#FFF6D6] text-[#8a6e1d]"
                    }`}>{l.status}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right whitespace-nowrap">
                    {l.status === "pending" && (
                      <>
                        <button onClick={() => decide(l.id, "approved")} className="text-[#0F7A2A] mr-2" data-testid={`hr-leave-approve-${l.id}`}><CheckCircle2 size={15} /></button>
                        <button onClick={() => decide(l.id, "rejected")} className="text-[#a10404]" data-testid={`hr-leave-reject-${l.id}`}><XCircle size={15} /></button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
