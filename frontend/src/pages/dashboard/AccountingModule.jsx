/**
 * Accounting module — Journal / Trial Balance / P&L.
 * Session B (2026-07-21) — double-entry bookkeeping.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API, formatApiError } from "@/contexts/AuthContext";
import { BookOpen, Scale, TrendingUp, Plus, Trash2, Loader2, Upload } from "lucide-react";
import BankStatementImport from "@/components/accounting/BankStatementImport";

const TABS = [
  { id: "journal", label: "Journal", icon: BookOpen },
  { id: "trial",   label: "Trial balance", icon: Scale },
  { id: "pnl",     label: "Profit & Loss", icon: TrendingUp },
  { id: "import",  label: "Import bank",  icon: Upload },
];

const fmt = (n) => Number(n || 0).toLocaleString("nl-NL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function AccountingModule() {
  const [tab, setTab] = useState("journal");
  const [accounts, setAccounts] = useState([]);
  useEffect(() => {
    axios.get(`${API}/accounting/accounts`, { withCredentials: true })
      .then((r) => setAccounts(r.data.accounts || []))
      .catch(() => { /* seeded automatically on first call */ });
  }, []);
  return (
    <div className="space-y-6" data-testid="accounting-module">
      <header>
        <h1 className="text-[26px] font-bold tracking-tight text-black">Accounting</h1>
        <p className="text-[14px] text-[#666] mt-1">Double-entry journal, trial balance, and profit &amp; loss for your workspace.</p>
      </header>
      <nav className="flex flex-wrap gap-1 border-b border-[#eee]">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`acc-tab-${t.id}`}
            className={`px-4 py-2.5 text-[13.5px] font-medium border-b-2 flex items-center gap-2 ${
              tab === t.id ? "border-[#1A4FFF] text-[#1A4FFF]" : "border-transparent text-[#666] hover:text-black"}`}>
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </nav>
      <div>
        {tab === "journal" && <JournalPanel accounts={accounts} />}
        {tab === "trial" && <TrialBalancePanel />}
        {tab === "pnl" && <PnLPanel />}
        {tab === "import" && <BankStatementImport accounts={accounts} />}
      </div>
    </div>
  );
}

function JournalPanel({ accounts }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState([
    { account_code: "", debit: "", credit: "" },
    { account_code: "", debit: "", credit: "" },
  ]);

  const load = async () => {
    setLoading(true);
    try { const { data } = await axios.get(`${API}/accounting/journal-entries`, { withCredentials: true }); setEntries(data.entries || []); }
    catch { toast.error("Failed to load journal."); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const totals = () => {
    const d = lines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0);
    const c = lines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);
    return { d, c, balanced: Math.round(d * 100) === Math.round(c * 100) && d > 0 };
  };

  const create = async () => {
    const t = totals();
    if (!t.balanced) return toast.error(`Entry doesn't balance (debit €${fmt(t.d)} vs credit €${fmt(t.c)}).`);
    if (!lines.every((l) => l.account_code && ((parseFloat(l.debit) || 0) > 0 || (parseFloat(l.credit) || 0) > 0))) {
      return toast.error("Every line needs an account and either debit or credit.");
    }
    try {
      await axios.post(`${API}/accounting/journal-entries`, {
        date: entryDate,
        description,
        lines: lines.map((l) => ({
          account_code: l.account_code,
          debit: parseFloat(l.debit) || 0,
          credit: parseFloat(l.credit) || 0,
        })),
      }, { withCredentials: true });
      toast.success("Journal entry posted.");
      setShowForm(false);
      setDescription("");
      setLines([{ account_code: "", debit: "", credit: "" }, { account_code: "", debit: "", credit: "" }]);
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to post."); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this journal entry?")) return;
    try { await axios.delete(`${API}/accounting/journal-entries/${id}`, { withCredentials: true }); load(); } catch { /* noop */ }
  };

  const t = totals();
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold">{entries.length} entr{entries.length === 1 ? "y" : "ies"}</h2>
        <button onClick={() => setShowForm(!showForm)} className="zy-btn-primary flex items-center gap-1.5 text-[13px]" data-testid="acc-journal-add-btn"><Plus size={14} /> New entry</button>
      </div>
      {showForm && (
        <div className="border border-[#eee] rounded-xl p-4 bg-white space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} className="text-[13px] px-3 py-2 border border-[#eee] rounded-md" data-testid="acc-journal-date" />
            <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description (optional)" className="text-[13px] px-3 py-2 border border-[#eee] rounded-md" data-testid="acc-journal-desc" />
          </div>
          <table className="w-full text-[13px]">
            <thead className="bg-[#F4F6FB] text-[#555]">
              <tr><th className="text-left px-2 py-1.5">Account</th><th className="text-right px-2 py-1.5">Debit</th><th className="text-right px-2 py-1.5">Credit</th></tr>
            </thead>
            <tbody>
              {lines.map((l, i) => (
                <tr key={i}>
                  <td className="px-2 py-1">
                    <select value={l.account_code} onChange={(e) => { const n = [...lines]; n[i].account_code = e.target.value; setLines(n); }} className="w-full text-[13px] px-2 py-1.5 border border-[#eee] rounded-md" data-testid={`acc-journal-line-${i}-acct`}>
                      <option value="">Select account…</option>
                      {accounts.map((a) => <option key={a.id} value={a.code}>{a.code} · {a.name}</option>)}
                    </select>
                  </td>
                  <td className="px-2 py-1"><input type="number" step="0.01" value={l.debit} onChange={(e) => { const n = [...lines]; n[i].debit = e.target.value; if (e.target.value) n[i].credit = ""; setLines(n); }} className="w-full text-right text-[13px] px-2 py-1.5 border border-[#eee] rounded-md" data-testid={`acc-journal-line-${i}-debit`} /></td>
                  <td className="px-2 py-1"><input type="number" step="0.01" value={l.credit} onChange={(e) => { const n = [...lines]; n[i].credit = e.target.value; if (e.target.value) n[i].debit = ""; setLines(n); }} className="w-full text-right text-[13px] px-2 py-1.5 border border-[#eee] rounded-md" data-testid={`acc-journal-line-${i}-credit`} /></td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-[#eee] font-semibold">
                <td className="px-2 py-1.5">Total</td>
                <td className="px-2 py-1.5 text-right">€{fmt(t.d)}</td>
                <td className="px-2 py-1.5 text-right">€{fmt(t.c)}</td>
              </tr>
            </tfoot>
          </table>
          <div className="flex justify-between items-center">
            <button onClick={() => setLines([...lines, { account_code: "", debit: "", credit: "" }])} className="text-[13px] text-[#1A4FFF]" data-testid="acc-journal-add-line">+ Add line</button>
            <span className={`text-[12px] font-semibold ${t.balanced ? "text-[#0F7A2A]" : "text-[#a10404]"}`} data-testid="acc-journal-balanced">
              {t.balanced ? "✓ Balanced" : "Not balanced"}
            </span>
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowForm(false)} className="px-3 py-2 text-[13px] text-[#666]">Cancel</button>
            <button onClick={create} disabled={!t.balanced} className="zy-btn-primary text-[13px] disabled:opacity-50" data-testid="acc-journal-save">Post entry</button>
          </div>
        </div>
      )}
      {loading ? <Loader2 className="animate-spin text-[#999]" /> : entries.length === 0 ? (
        <div className="border border-dashed border-[#e5e7ee] rounded-xl p-10 text-center text-[#888]">No entries yet. Click "New entry" to record your first transaction.</div>
      ) : (
        <div className="border border-[#eee] rounded-xl overflow-hidden">
          <table className="w-full text-[13px]">
            <thead className="bg-[#F4F6FB] text-[#555]"><tr><th className="text-left px-4 py-2.5">#</th><th className="text-left px-4 py-2.5">Date</th><th className="text-left px-4 py-2.5">Description</th><th className="text-right px-4 py-2.5">Debit</th><th className="text-right px-4 py-2.5">Credit</th><th /></tr></thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-t border-[#eee]" data-testid={`acc-journal-row-${e.id}`}>
                  <td className="px-4 py-2.5 text-[#888]">#{e.entry_no}</td>
                  <td className="px-4 py-2.5 text-[#555]">{e.date}</td>
                  <td className="px-4 py-2.5 text-[#111]">{e.description || "—"}<div className="text-[11.5px] text-[#888]">{e.lines.map((l) => `${l.account_code}`).join(" · ")}</div></td>
                  <td className="px-4 py-2.5 text-right text-[#555]">€{fmt(e.total_debit)}</td>
                  <td className="px-4 py-2.5 text-right text-[#555]">€{fmt(e.total_credit)}</td>
                  <td className="px-4 py-2.5 text-right"><button onClick={() => remove(e.id)} className="text-[#c00]"><Trash2 size={14} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TrialBalancePanel() {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/accounting/trial-balance`, { withCredentials: true }).then((r) => setData(r.data)); }, []);
  if (!data) return <Loader2 className="animate-spin text-[#999]" />;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold">Trial balance</h2>
        <span className={`text-[12px] font-bold px-2 py-1 rounded-full ${data.balanced ? "bg-[#E8FFE9] text-[#0F7A2A]" : "bg-[#FFE8E8] text-[#a10404]"}`}>
          {data.balanced ? "✓ Balanced" : "Not balanced"}
        </span>
      </div>
      <div className="border border-[#eee] rounded-xl overflow-hidden">
        <table className="w-full text-[13px]">
          <thead className="bg-[#F4F6FB] text-[#555]"><tr><th className="text-left px-4 py-2.5">Code</th><th className="text-left px-4 py-2.5">Account</th><th className="text-left px-4 py-2.5">Type</th><th className="text-right px-4 py-2.5">Debit</th><th className="text-right px-4 py-2.5">Credit</th></tr></thead>
          <tbody>
            {data.rows.filter((r) => r.debit || r.credit).map((r) => (
              <tr key={r.account_id} className="border-t border-[#eee]" data-testid={`acc-tb-row-${r.account_code}`}>
                <td className="px-4 py-2.5 text-[#888]">{r.account_code}</td>
                <td className="px-4 py-2.5 text-[#111]">{r.account_name}</td>
                <td className="px-4 py-2.5 text-[#666]">{r.account_type}</td>
                <td className="px-4 py-2.5 text-right text-[#555]">{r.debit ? `€${fmt(r.debit)}` : "—"}</td>
                <td className="px-4 py-2.5 text-right text-[#555]">{r.credit ? `€${fmt(r.credit)}` : "—"}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-[#F4F6FB] font-semibold">
            <tr className="border-t border-[#eee]"><td colSpan="3" className="px-4 py-2.5">Total</td><td className="px-4 py-2.5 text-right" data-testid="acc-tb-total-debit">€{fmt(data.total_debit)}</td><td className="px-4 py-2.5 text-right" data-testid="acc-tb-total-credit">€{fmt(data.total_credit)}</td></tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

function PnLPanel() {
  const [data, setData] = useState(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const load = async () => {
    const params = {};
    if (from) params.date_from = from;
    if (to) params.date_to = to;
    const { data } = await axios.get(`${API}/accounting/pnl`, { params, withCredentials: true });
    setData(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);
  if (!data) return <Loader2 className="animate-spin text-[#999]" />;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-[16px] font-semibold">Profit &amp; Loss</h2>
        <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="text-[13px] px-2.5 py-1.5 border border-[#eee] rounded-md" placeholder="from" />
        <span className="text-[#888] text-[13px]">→</span>
        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="text-[13px] px-2.5 py-1.5 border border-[#eee] rounded-md" />
        <button onClick={load} className="zy-btn-primary text-[13px]" data-testid="acc-pnl-refresh">Refresh</button>
      </div>
      <div className="border border-[#eee] rounded-xl overflow-hidden">
        <table className="w-full text-[13px]">
          <tbody>
            <tr className="bg-[#F4F6FB] font-semibold"><td className="px-4 py-2" colSpan="2">Revenue</td></tr>
            {data.revenue.length === 0 ? <tr><td className="px-4 py-2.5 text-[#888]" colSpan="2">No revenue in period.</td></tr> :
              data.revenue.map((r) => (
                <tr key={r.account_id} className="border-t border-[#eee]"><td className="px-4 py-2 text-[#111]">{r.account_code} · {r.account_name}</td><td className="px-4 py-2 text-right text-[#555]">€{fmt(r.amount)}</td></tr>
              ))}
            <tr className="border-t border-[#eee] font-semibold"><td className="px-4 py-2">Total revenue</td><td className="px-4 py-2 text-right text-[#0F7A2A]" data-testid="acc-pnl-total-revenue">€{fmt(data.total_revenue)}</td></tr>
            <tr className="bg-[#F4F6FB] font-semibold border-t border-[#eee]"><td className="px-4 py-2" colSpan="2">Expenses</td></tr>
            {data.expenses.length === 0 ? <tr><td className="px-4 py-2.5 text-[#888]" colSpan="2">No expenses in period.</td></tr> :
              data.expenses.map((r) => (
                <tr key={r.account_id} className="border-t border-[#eee]"><td className="px-4 py-2 text-[#111]">{r.account_code} · {r.account_name}</td><td className="px-4 py-2 text-right text-[#555]">€{fmt(r.amount)}</td></tr>
              ))}
            <tr className="border-t border-[#eee] font-semibold"><td className="px-4 py-2">Total expenses</td><td className="px-4 py-2 text-right text-[#a10404]" data-testid="acc-pnl-total-expenses">€{fmt(data.total_expenses)}</td></tr>
            <tr className="border-t-2 border-[#111] font-bold bg-[#F4F6FB]"><td className="px-4 py-3 text-[15px]">Net income</td><td className={`px-4 py-3 text-right text-[15px] ${data.net_income >= 0 ? "text-[#0F7A2A]" : "text-[#a10404]"}`} data-testid="acc-pnl-net">€{fmt(data.net_income)}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
