/**
 * Finance & Invoicing module — invoices, PDF, email send, payments.
 * Session C1 (2026-02) — jury-ready CRUD.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API, formatApiError } from "@/contexts/AuthContext";
import {
  ReceiptEuro, Plus, Trash2, Loader2, FileText, Mail, CheckCircle2,
  Download, Eye, Settings2, Clock, AlertCircle, Euro,
} from "lucide-react";

const STATUS_STYLES = {
  draft:   { bg: "#F4F6FB", fg: "#666",    label: "Draft" },
  sent:    { bg: "rgba(26,79,255,0.12)",  fg: "#1A4FFF", label: "Sent" },
  paid:    { bg: "rgba(34,197,94,0.12)",  fg: "#16a34a", label: "Paid" },
  overdue: { bg: "rgba(220,38,38,0.10)",  fg: "#dc2626", label: "Overdue" },
};

const CURRENCY_SYMBOL = { EUR: "€", USD: "$", GBP: "£" };
const sym = (c) => CURRENCY_SYMBOL[c] || c || "€";
const fmt = (v) => Number(v || 0).toLocaleString("nl-NL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const emptyItem = () => ({ description: "", quantity: 1, unit_price: 0, tax_rate: 21 });
const emptyForm = () => ({
  client_name: "", client_email: "", client_address: "",
  issue_date: new Date().toISOString().slice(0, 10),
  due_date: "", currency: "EUR",
  items: [emptyItem()],
  payment_terms: "", bank_details: "", notes: "",
});

export default function FinanceModule() {
  const [tab, setTab] = useState("invoices");
  return (
    <div className="space-y-6" data-testid="finance-module">
      <header>
        <h1 className="text-[26px] font-bold tracking-tight text-black flex items-center gap-2">
          <ReceiptEuro size={22} style={{ color: "#1A4FFF" }} /> Finance &amp; Invoicing
        </h1>
        <p className="text-[14px] text-[#666] mt-1">
          Create invoices, send them by email, track payments and export PDFs.
        </p>
      </header>
      <nav className="flex flex-wrap gap-1 border-b border-[#eee]">
        {[
          { id: "invoices", label: "Invoices", icon: FileText },
          { id: "settings", label: "Company & bank details", icon: Settings2 },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            data-testid={`finance-tab-${t.id}`}
            className={`px-4 py-2.5 text-[13.5px] font-medium border-b-2 flex items-center gap-2 transition-colors ${
              tab === t.id ? "border-[#1A4FFF] text-[#1A4FFF]" : "border-transparent text-[#666] hover:text-black"
            }`}
          >
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </nav>
      {tab === "invoices" ? <InvoicesPanel /> : <SettingsPanel />}
    </div>
  );
}

// -------- Invoices ---------------------------------------------------------
function InvoicesPanel() {
  const [rows, setRows] = useState([]);
  const [totals, setTotals] = useState({ total_eur: 0, paid_eur: 0, outstanding_eur: 0 });
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);   // full invoice being edited/created
  const [drawerId, setDrawerId] = useState(null); // id to inspect in the detail drawer

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/finance/invoices`, { withCredentials: true });
      setRows(data.invoices || []);
      setTotals(data.totals || {});
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to load invoices."); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const startNew = () => setEditing({ ...emptyForm(), id: null });

  const save = async () => {
    if (!editing.client_name) return toast.error("Client name is required.");
    if (!editing.items?.length) return toast.error("Add at least one line item.");
    for (const it of editing.items) {
      if (!it.description) return toast.error("Every line item needs a description.");
    }
    try {
      const payload = {
        client_name: editing.client_name,
        client_email: editing.client_email || null,
        client_address: editing.client_address,
        issue_date: editing.issue_date,
        due_date: editing.due_date || null,
        currency: editing.currency,
        items: editing.items.map((it) => ({
          description: it.description,
          quantity: parseFloat(it.quantity) || 0,
          unit_price: parseFloat(it.unit_price) || 0,
          tax_rate: parseFloat(it.tax_rate) || 0,
        })),
        payment_terms: editing.payment_terms,
        bank_details: editing.bank_details,
        notes: editing.notes,
      };
      if (editing.id) {
        await axios.put(`${API}/finance/invoices/${editing.id}`, payload, { withCredentials: true });
        toast.success("Invoice updated.");
      } else {
        await axios.post(`${API}/finance/invoices`, payload, { withCredentials: true });
        toast.success("Invoice created.");
      }
      setEditing(null);
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to save invoice."); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this invoice? Payments will also be removed.")) return;
    try {
      await axios.delete(`${API}/finance/invoices/${id}`, { withCredentials: true });
      toast.success("Invoice deleted.");
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to delete."); }
  };

  const openPdf = (id) => {
    window.open(`${API}/finance/invoices/${id}/pdf`, "_blank", "noopener,noreferrer");
  };

  const sendEmail = async (row) => {
    if (!row.client_email) return toast.error("Add a client email to send this invoice.");
    try {
      const { data } = await axios.post(
        `${API}/finance/invoices/${row.id}/send-email`, {}, { withCredentials: true },
      );
      toast.success(data.email_sent ? "Invoice emailed to client." : "Invoice queued (dev mode — email logged).");
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to send email."); }
  };

  const markPaid = async (id) => {
    if (!window.confirm("Mark this invoice as fully paid?")) return;
    try {
      await axios.post(`${API}/finance/invoices/${id}/mark-paid`, {}, { withCredentials: true });
      toast.success("Invoice marked as paid.");
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  return (
    <div className="space-y-5">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatPill label="Invoiced" value={`€${fmt(totals.total_eur)}`} icon={FileText} accent="#1A4FFF" />
        <StatPill label="Paid" value={`€${fmt(totals.paid_eur)}`} icon={CheckCircle2} accent="#16a34a" />
        <StatPill label="Outstanding" value={`€${fmt(totals.outstanding_eur)}`} icon={Clock} accent="#D97706" />
        <StatPill label="Overdue" value={totals.overdue_count || 0} icon={AlertCircle} accent="#dc2626" />
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-semibold">{rows.length} invoice{rows.length === 1 ? "" : "s"}</h2>
        <button onClick={startNew} className="zy-btn-primary flex items-center gap-1.5 text-[13px]" data-testid="finance-new-invoice-btn">
          <Plus size={14} /> New invoice
        </button>
      </div>

      {loading ? (
        <Loader2 className="animate-spin text-[#999]" />
      ) : rows.length === 0 ? (
        <div className="border border-dashed border-[#e5e7ee] rounded-xl p-10 text-center text-[#888]">
          No invoices yet. Click <b>New invoice</b> to create your first one.
        </div>
      ) : (
        <div className="border border-[#eee] rounded-xl overflow-hidden bg-white">
          <table className="w-full text-[13px]">
            <thead className="bg-[#F4F6FB] text-[#555]">
              <tr>
                <th className="text-left px-4 py-2.5">Number</th>
                <th className="text-left px-4 py-2.5">Client</th>
                <th className="text-left px-4 py-2.5">Issued</th>
                <th className="text-left px-4 py-2.5">Due</th>
                <th className="text-right px-4 py-2.5">Total</th>
                <th className="text-left px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 w-1" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const st = STATUS_STYLES[r.status] || STATUS_STYLES.draft;
                return (
                  <tr key={r.id} className="border-t border-[#eee]" data-testid={`finance-invoice-row-${r.id}`}>
                    <td className="px-4 py-2.5 font-mono text-[12.5px] font-semibold">{r.number}</td>
                    <td className="px-4 py-2.5 text-black font-medium">
                      {r.client_name}
                      <div className="text-[11.5px] text-[#888]">{r.client_email || "—"}</div>
                    </td>
                    <td className="px-4 py-2.5 text-[#555]">{r.issue_date}</td>
                    <td className="px-4 py-2.5 text-[#555]">{r.due_date || "—"}</td>
                    <td className="px-4 py-2.5 text-right font-semibold tabular-nums">{sym(r.currency)}{fmt(r.total)}</td>
                    <td className="px-4 py-2.5">
                      <span className="inline-flex items-center gap-1 text-[11px] uppercase font-bold px-2 py-0.5 rounded-full" style={{ background: st.bg, color: st.fg }}>
                        {st.label}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-right">
                      <button title="View" onClick={() => setDrawerId(r.id)} className="text-[#1A4FFF] mx-1" data-testid={`finance-view-${r.id}`}><Eye size={15} /></button>
                      <button title="PDF" onClick={() => openPdf(r.id)} className="text-[#0A1628] mx-1" data-testid={`finance-pdf-${r.id}`}><Download size={15} /></button>
                      <button title="Email" onClick={() => sendEmail(r)} className="text-[#1A4FFF] mx-1" data-testid={`finance-email-${r.id}`}><Mail size={15} /></button>
                      {r.status !== "paid" && (
                        <button title="Mark paid" onClick={() => markPaid(r.id)} className="text-[#16a34a] mx-1" data-testid={`finance-mark-paid-${r.id}`}><CheckCircle2 size={15} /></button>
                      )}
                      <button title="Delete" onClick={() => remove(r.id)} className="text-[#c00] mx-1" data-testid={`finance-del-${r.id}`}><Trash2 size={14} /></button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <InvoiceEditor
          value={editing}
          onChange={setEditing}
          onCancel={() => setEditing(null)}
          onSave={save}
        />
      )}

      {drawerId && (
        <InvoiceDetail id={drawerId} onClose={() => { setDrawerId(null); load(); }} />
      )}
    </div>
  );
}

// -------- Invoice editor (create / edit) -----------------------------------
function InvoiceEditor({ value, onChange, onCancel, onSave }) {
  const set = (patch) => onChange({ ...value, ...patch });
  const setItem = (i, patch) => {
    const items = [...value.items];
    items[i] = { ...items[i], ...patch };
    set({ items });
  };
  const addItem = () => set({ items: [...value.items, emptyItem()] });
  const removeItem = (i) => set({ items: value.items.filter((_, idx) => idx !== i) });

  const subtotal = value.items.reduce((s, it) => s + (parseFloat(it.quantity) || 0) * (parseFloat(it.unit_price) || 0), 0);
  const tax = value.items.reduce((s, it) => s + (parseFloat(it.quantity) || 0) * (parseFloat(it.unit_price) || 0) * ((parseFloat(it.tax_rate) || 0) / 100), 0);
  const total = subtotal + tax;

  return (
    <div className="fixed inset-0 bg-black/40 z-40 flex items-start justify-center overflow-y-auto p-4" data-testid="finance-editor-modal">
      <div className="bg-white rounded-2xl w-full max-w-3xl mt-8 mb-16 shadow-xl overflow-hidden">
        <div className="p-5 border-b border-[#eee] flex items-center justify-between">
          <h3 className="text-[16px] font-semibold">{value.id ? "Edit invoice" : "New invoice"}</h3>
          <button onClick={onCancel} className="text-[#666] hover:text-black">✕</button>
        </div>
        <div className="p-5 space-y-5 max-h-[70vh] overflow-y-auto">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Client name*">
              <input value={value.client_name} onChange={(e) => set({ client_name: e.target.value })} className="zy-input" data-testid="finance-editor-client-name" />
            </Field>
            <Field label="Client email">
              <input type="email" value={value.client_email || ""} onChange={(e) => set({ client_email: e.target.value })} className="zy-input" data-testid="finance-editor-client-email" />
            </Field>
            <Field label="Issue date*">
              <input type="date" value={value.issue_date} onChange={(e) => set({ issue_date: e.target.value })} className="zy-input" data-testid="finance-editor-issue-date" />
            </Field>
            <Field label="Due date">
              <input type="date" value={value.due_date || ""} onChange={(e) => set({ due_date: e.target.value })} className="zy-input" data-testid="finance-editor-due-date" />
            </Field>
            <Field label="Currency">
              <select value={value.currency} onChange={(e) => set({ currency: e.target.value })} className="zy-input" data-testid="finance-editor-currency">
                <option value="EUR">EUR (€)</option>
                <option value="USD">USD ($)</option>
                <option value="GBP">GBP (£)</option>
              </select>
            </Field>
            <Field label="Client address" className="sm:col-span-2">
              <textarea value={value.client_address || ""} onChange={(e) => set({ client_address: e.target.value })} className="zy-input min-h-[60px]" />
            </Field>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-[13.5px] font-semibold">Line items</h4>
              <button onClick={addItem} className="text-[12.5px] text-[#1A4FFF] hover:underline flex items-center gap-1" data-testid="finance-editor-add-item">
                <Plus size={13} /> Add line
              </button>
            </div>
            <div className="border border-[#eee] rounded-lg overflow-hidden">
              <table className="w-full text-[12.5px]">
                <thead className="bg-[#F4F6FB] text-[#555]">
                  <tr>
                    <th className="text-left px-3 py-2">Description</th>
                    <th className="text-right px-3 py-2 w-[70px]">Qty</th>
                    <th className="text-right px-3 py-2 w-[110px]">Unit price</th>
                    <th className="text-right px-3 py-2 w-[80px]">Tax %</th>
                    <th className="text-right px-3 py-2 w-[110px]">Total</th>
                    <th className="w-8" />
                  </tr>
                </thead>
                <tbody>
                  {value.items.map((it, i) => {
                    const line = (parseFloat(it.quantity) || 0) * (parseFloat(it.unit_price) || 0) * (1 + (parseFloat(it.tax_rate) || 0) / 100);
                    return (
                      <tr key={i} className="border-t border-[#eee]">
                        <td className="px-2 py-1"><input value={it.description} onChange={(e) => setItem(i, { description: e.target.value })} className="w-full px-2 py-1.5 border border-transparent focus:border-[#1A4FFF] rounded outline-none" data-testid={`finance-editor-item-desc-${i}`} /></td>
                        <td className="px-2 py-1"><input type="number" step="0.01" value={it.quantity} onChange={(e) => setItem(i, { quantity: e.target.value })} className="w-full px-2 py-1.5 text-right border border-transparent focus:border-[#1A4FFF] rounded outline-none" data-testid={`finance-editor-item-qty-${i}`} /></td>
                        <td className="px-2 py-1"><input type="number" step="0.01" value={it.unit_price} onChange={(e) => setItem(i, { unit_price: e.target.value })} className="w-full px-2 py-1.5 text-right border border-transparent focus:border-[#1A4FFF] rounded outline-none" data-testid={`finance-editor-item-price-${i}`} /></td>
                        <td className="px-2 py-1"><input type="number" step="0.1" value={it.tax_rate} onChange={(e) => setItem(i, { tax_rate: e.target.value })} className="w-full px-2 py-1.5 text-right border border-transparent focus:border-[#1A4FFF] rounded outline-none" /></td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{sym(value.currency)}{fmt(line)}</td>
                        <td className="text-center">
                          {value.items.length > 1 && (
                            <button onClick={() => removeItem(i)} className="text-[#c00]"><Trash2 size={13} /></button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Payment terms" className="sm:col-span-2">
              <textarea value={value.payment_terms || ""} onChange={(e) => set({ payment_terms: e.target.value })} placeholder="Payment due within 14 days of invoice date." className="zy-input min-h-[60px]" data-testid="finance-editor-payment-terms" />
            </Field>
            <Field label="Bank details" className="sm:col-span-2">
              <textarea value={value.bank_details || ""} onChange={(e) => set({ bank_details: e.target.value })} placeholder="IBAN NL01 BANK 1234 5678 90&#10;BIC BANKNL2A&#10;Account name: Your Company BV" className="zy-input min-h-[60px]" data-testid="finance-editor-bank-details" />
            </Field>
            <Field label="Notes" className="sm:col-span-2">
              <textarea value={value.notes || ""} onChange={(e) => set({ notes: e.target.value })} className="zy-input min-h-[50px]" />
            </Field>
          </div>

          <div className="flex justify-end">
            <div className="text-right text-[13px] space-y-1 min-w-[220px]">
              <div className="flex justify-between text-[#666]"><span>Subtotal</span><span className="tabular-nums">{sym(value.currency)}{fmt(subtotal)}</span></div>
              <div className="flex justify-between text-[#666]"><span>Tax</span><span className="tabular-nums">{sym(value.currency)}{fmt(tax)}</span></div>
              <div className="flex justify-between font-bold text-black border-t border-[#0A1628] pt-1 mt-1"><span>Total</span><span className="tabular-nums">{sym(value.currency)}{fmt(total)}</span></div>
            </div>
          </div>
        </div>
        <div className="p-4 border-t border-[#eee] flex justify-end gap-2 bg-[#FAFBFF]">
          <button onClick={onCancel} className="px-3 py-2 text-[13px] text-[#666] hover:text-black">Cancel</button>
          <button onClick={onSave} className="zy-btn-primary text-[13px]" data-testid="finance-editor-save-btn">
            {value.id ? "Save changes" : "Create invoice"}
          </button>
        </div>
      </div>
    </div>
  );
}

// -------- Invoice detail drawer + payment history -------------------------
function InvoiceDetail({ id, onClose }) {
  const [data, setData] = useState(null);
  const [pf, setPf] = useState({ amount: "", method: "bank_transfer", date: new Date().toISOString().slice(0, 10), notes: "" });

  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/finance/invoices/${id}`, { withCredentials: true });
      setData(data);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to load."); }
  };
  useEffect(() => { load(); }, [id]);

  const addPayment = async () => {
    if (!pf.amount || parseFloat(pf.amount) <= 0) return toast.error("Amount must be greater than 0.");
    try {
      await axios.post(`${API}/finance/invoices/${id}/payments`, {
        amount: parseFloat(pf.amount),
        method: pf.method,
        date: pf.date,
        notes: pf.notes,
      }, { withCredentials: true });
      setPf({ amount: "", method: "bank_transfer", date: new Date().toISOString().slice(0, 10), notes: "" });
      toast.success("Payment recorded.");
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  const removePayment = async (pid) => {
    if (!window.confirm("Delete this payment record?")) return;
    try {
      await axios.delete(`${API}/finance/payments/${pid}`, { withCredentials: true });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
  };

  if (!data) return null;
  const inv = data.invoice;
  const st = STATUS_STYLES[inv.status] || STATUS_STYLES.draft;
  const paidSum = (data.payments || []).reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);

  return (
    <div className="fixed inset-0 bg-black/40 z-40 flex justify-end" data-testid="finance-detail-drawer">
      <div className="bg-white w-full max-w-xl h-full overflow-y-auto shadow-xl">
        <div className="p-5 border-b border-[#eee] flex items-center justify-between">
          <div>
            <div className="text-[11.5px] uppercase text-[#888] font-bold">Invoice</div>
            <h3 className="text-[18px] font-bold">{inv.number}</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[11px] uppercase font-bold px-2 py-0.5 rounded-full" style={{ background: st.bg, color: st.fg }}>{st.label}</span>
            <button onClick={onClose} className="text-[#666] hover:text-black text-lg" data-testid="finance-detail-close">✕</button>
          </div>
        </div>
        <div className="p-5 space-y-5">
          <div className="grid grid-cols-2 gap-3 text-[13px]">
            <div><div className="text-[#888] text-[11.5px] uppercase font-bold">Client</div>{inv.client_name}<div className="text-[#666]">{inv.client_email || "—"}</div></div>
            <div><div className="text-[#888] text-[11.5px] uppercase font-bold">Total</div><span className="text-[18px] font-bold">{sym(inv.currency)}{fmt(inv.total)}</span></div>
            <div><div className="text-[#888] text-[11.5px] uppercase font-bold">Issued</div>{inv.issue_date}</div>
            <div><div className="text-[#888] text-[11.5px] uppercase font-bold">Due</div>{inv.due_date || "—"}</div>
          </div>

          <div>
            <div className="text-[#888] text-[11.5px] uppercase font-bold mb-1">Line items</div>
            <table className="w-full text-[12.5px] border border-[#eee] rounded-md overflow-hidden">
              <thead className="bg-[#F4F6FB] text-[#555]">
                <tr><th className="text-left px-3 py-1.5">Description</th><th className="text-right px-3 py-1.5">Qty</th><th className="text-right px-3 py-1.5">Price</th><th className="text-right px-3 py-1.5">Tax</th></tr>
              </thead>
              <tbody>
                {inv.items.map((it, i) => (
                  <tr key={i} className="border-t border-[#eee]">
                    <td className="px-3 py-1.5">{it.description}</td>
                    <td className="px-3 py-1.5 text-right">{it.quantity}</td>
                    <td className="px-3 py-1.5 text-right">{sym(inv.currency)}{fmt(it.unit_price)}</td>
                    <td className="px-3 py-1.5 text-right">{it.tax_rate}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <div className="text-[#888] text-[11.5px] uppercase font-bold mb-2">Payment history</div>
            {(data.payments || []).length === 0 ? (
              <div className="text-[#888] text-[12.5px] italic">No payments recorded yet.</div>
            ) : (
              <ul className="space-y-1.5">
                {data.payments.map((p) => (
                  <li key={p.id} className="flex items-center justify-between border border-[#eee] rounded-md px-3 py-2 text-[12.5px]" data-testid={`finance-payment-row-${p.id}`}>
                    <div>
                      <div className="font-semibold">{sym(inv.currency)}{fmt(p.amount)}</div>
                      <div className="text-[#888]">{p.date} · {p.method}{p.notes ? ` · ${p.notes}` : ""}</div>
                    </div>
                    <button onClick={() => removePayment(p.id)} className="text-[#c00]"><Trash2 size={13} /></button>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-2 text-[12.5px] text-[#666]">Total received: <b className="text-black">{sym(inv.currency)}{fmt(paidSum)}</b> of {sym(inv.currency)}{fmt(inv.total)}</div>
          </div>

          {inv.status !== "paid" && (
            <div className="border border-[#eee] rounded-lg p-3 bg-[#FAFBFF] space-y-2">
              <div className="text-[12.5px] font-semibold flex items-center gap-1"><Euro size={13} /> Record payment</div>
              <div className="grid grid-cols-2 gap-2">
                <input type="number" step="0.01" placeholder="Amount" value={pf.amount} onChange={(e) => setPf({ ...pf, amount: e.target.value })} className="zy-input" data-testid="finance-payment-amount" />
                <input type="date" value={pf.date} onChange={(e) => setPf({ ...pf, date: e.target.value })} className="zy-input" />
                <select value={pf.method} onChange={(e) => setPf({ ...pf, method: e.target.value })} className="zy-input">
                  <option value="bank_transfer">Bank transfer</option>
                  <option value="stripe">Stripe</option>
                  <option value="cash">Cash</option>
                  <option value="other">Other</option>
                </select>
                <input placeholder="Notes (optional)" value={pf.notes} onChange={(e) => setPf({ ...pf, notes: e.target.value })} className="zy-input" />
              </div>
              <button onClick={addPayment} className="zy-btn-primary text-[13px]" data-testid="finance-payment-save">Add payment</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// -------- Settings ---------------------------------------------------------
function SettingsPanel() {
  const [s, setS] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/finance/settings`, { withCredentials: true });
        setS(data.settings);
      } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed to load."); }
    })();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await axios.put(`${API}/finance/settings`, {
        company_name: s.company_name || "",
        company_address: s.company_address || "",
        company_email: s.company_email || "",
        company_vat: s.company_vat || "",
        logo_url: s.logo_url || "",
        default_payment_terms: s.default_payment_terms || "",
        default_bank_details: s.default_bank_details || "",
        invoice_prefix: s.invoice_prefix || "INV-",
        currency: s.currency || "EUR",
      }, { withCredentials: true });
      setS(data.settings);
      toast.success("Settings saved.");
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Failed."); }
    setSaving(false);
  };

  if (!s) return <Loader2 className="animate-spin text-[#999]" />;

  return (
    <div className="bg-white border border-[#eee] rounded-2xl p-5 space-y-4 max-w-2xl">
      <p className="text-[13px] text-[#666]">
        These company &amp; bank details appear on every invoice PDF and email. Update them once here.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="Company name">
          <input value={s.company_name || ""} onChange={(e) => setS({ ...s, company_name: e.target.value })} className="zy-input" data-testid="finance-settings-company-name" />
        </Field>
        <Field label="Company email">
          <input value={s.company_email || ""} onChange={(e) => setS({ ...s, company_email: e.target.value })} className="zy-input" />
        </Field>
        <Field label="VAT / Tax ID">
          <input value={s.company_vat || ""} onChange={(e) => setS({ ...s, company_vat: e.target.value })} className="zy-input" />
        </Field>
        <Field label="Invoice number prefix">
          <input value={s.invoice_prefix || ""} onChange={(e) => setS({ ...s, invoice_prefix: e.target.value })} className="zy-input" data-testid="finance-settings-prefix" />
        </Field>
        <Field label="Default currency">
          <select value={s.currency || "EUR"} onChange={(e) => setS({ ...s, currency: e.target.value })} className="zy-input">
            <option value="EUR">EUR</option><option value="USD">USD</option><option value="GBP">GBP</option>
          </select>
        </Field>
        <Field label="Company address" className="sm:col-span-2">
          <textarea value={s.company_address || ""} onChange={(e) => setS({ ...s, company_address: e.target.value })} className="zy-input min-h-[60px]" />
        </Field>
        <Field label="Default payment terms" className="sm:col-span-2">
          <textarea value={s.default_payment_terms || ""} onChange={(e) => setS({ ...s, default_payment_terms: e.target.value })} className="zy-input min-h-[60px]" data-testid="finance-settings-terms" />
        </Field>
        <Field label="Default bank details" className="sm:col-span-2">
          <textarea value={s.default_bank_details || ""} onChange={(e) => setS({ ...s, default_bank_details: e.target.value })} placeholder="IBAN, BIC, Account name…" className="zy-input min-h-[60px]" data-testid="finance-settings-bank" />
        </Field>
      </div>
      <div className="flex justify-end">
        <button onClick={save} disabled={saving} className="zy-btn-primary text-[13px]" data-testid="finance-settings-save">
          {saving ? "Saving…" : "Save settings"}
        </button>
      </div>
    </div>
  );
}

// -------- shared -----------------------------------------------------------
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
