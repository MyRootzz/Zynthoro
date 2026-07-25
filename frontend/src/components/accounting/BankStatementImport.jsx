/**
 * Bank statement CSV import wizard.
 *
 * Three steps:
 *   1. Upload — pick a CSV file, POST /api/accounting/csv/preview
 *      to detect columns and preview 20 rows.
 *   2. Map — user confirms/edits the column mapping (date, description,
 *      amount, currency) and optional bank hint. POST /ingest → server
 *      parses every row, AI-classifies each into a chart-of-accounts
 *      code, and stages them.
 *   3. Review — table of staged transactions; user can edit counterpart
 *      code (dropdown), reject, or confirm each. "Post all" bulk-confirms.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API, formatApiError } from "@/contexts/AuthContext";
import {
  Upload, FileSpreadsheet, Check, X, Loader2, ChevronRight, Sparkles,
  ArrowRight, AlertCircle,
} from "lucide-react";

const fmt = (n) =>
  Number(n || 0).toLocaleString("nl-NL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const CONFIDENCE_STYLE = (c) => {
  if (c >= 0.8) return { bg: "#D1FAE514", color: "#047857", label: "High" };
  if (c >= 0.5) return { bg: "#FEF3C714", color: "#B45309", label: "Med" };
  return { bg: "#FEE2E214", color: "#B91C1C", label: "Low" };
};

export default function BankStatementImport({ accounts }) {
  const [step, setStep] = useState("upload"); // upload | map | review
  const [csvText, setCsvText] = useState("");
  const [fileName, setFileName] = useState("");
  const [headers, setHeaders] = useState([]);
  const [sample, setSample] = useState([]);
  const [colMap, setColMap] = useState({ date: "", description: "", amount: "", currency: "" });
  const [sourceBank, setSourceBank] = useState("");
  const [staged, setStaged] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [confirmingId, setConfirmingId] = useState(null);

  const pendingCount = useMemo(
    () => staged.filter((t) => t.status === "pending").length,
    [staged]
  );

  const reloadStaged = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/accounting/csv/staged?status=pending`);
      setStaged(data.transactions || []);
    } catch {
      /* noop */
    }
  }, []);

  useEffect(() => {
    // On mount, check if there are already pending transactions to resume.
    reloadStaged().then(() => {
      // don't jump automatically — user must go through the wizard once.
    });
  }, [reloadStaged]);

  // Step 1 — file upload → preview
  const onFile = async (file) => {
    if (!file) return;
    setFileName(file.name);
    setLoading(true);
    try {
      const text = await file.text();
      setCsvText(text);
      const { data } = await axios.post(`${API}/accounting/csv/preview`, { csv_text: text });
      setHeaders(data.headers || []);
      setSample(data.sample_rows || []);
      setColMap({
        date: data.suggested_map?.date || "",
        description: data.suggested_map?.description || "",
        amount: data.suggested_map?.amount || "",
        currency: data.suggested_map?.currency || "",
      });
      setStep("map");
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't parse this CSV.");
    }
    setLoading(false);
  };

  // Step 2 — confirm mapping → ingest
  const ingest = async () => {
    if (!colMap.date || !colMap.description || !colMap.amount) {
      toast.error("Please map the Date, Description and Amount columns.");
      return;
    }
    setIngesting(true);
    try {
      const { data } = await axios.post(`${API}/accounting/csv/ingest`, {
        csv_text: csvText,
        column_map: colMap,
        source_bank: sourceBank || null,
      });
      toast.success(`Ingested ${data.ingested} row(s). Skipped ${data.skipped}. AI classifying…`);
      await reloadStaged();
      setStep("review");
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Ingest failed.");
    }
    setIngesting(false);
  };

  // Step 3 — patch / reject / confirm
  const patchCode = async (tid, code) => {
    try {
      const { data } = await axios.post(`${API}/accounting/csv/staged/${tid}`, {
        counterpart_code: code,
      });
      setStaged((prev) => prev.map((t) => (t.id === tid ? data : t)));
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Update failed.");
    }
  };

  const reject = async (tid) => {
    try {
      await axios.post(`${API}/accounting/csv/staged/${tid}/reject`);
      setStaged((prev) => prev.filter((t) => t.id !== tid));
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Reject failed.");
    }
  };

  const confirmOne = async (tid) => {
    setConfirmingId(tid);
    try {
      await axios.post(`${API}/accounting/csv/staged/${tid}/confirm`);
      setStaged((prev) => prev.filter((t) => t.id !== tid));
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Confirm failed.");
    }
    setConfirmingId(null);
  };

  const confirmAll = async () => {
    if (!pendingCount) return;
    if (!window.confirm(`Post ${pendingCount} transactions to the journal?`)) return;
    setIngesting(true);
    let ok = 0;
    let fail = 0;
    for (const t of staged.filter((x) => x.status === "pending")) {
      try {
        await axios.post(`${API}/accounting/csv/staged/${t.id}/confirm`);
        ok += 1;
      } catch {
        fail += 1;
      }
    }
    if (ok) toast.success(`Posted ${ok} journal entries.`);
    if (fail) toast.error(`${fail} failed to post.`);
    await reloadStaged();
    setIngesting(false);
  };

  const startOver = () => {
    setStep("upload");
    setCsvText("");
    setFileName("");
    setHeaders([]);
    setSample([]);
    setColMap({ date: "", description: "", amount: "", currency: "" });
    setSourceBank("");
  };

  return (
    <div className="space-y-5" data-testid="bank-csv-import">
      {/* Wizard stepper */}
      <Stepper current={step} pendingCount={pendingCount} />

      {step === "upload" && (
        <UploadStep
          onFile={onFile}
          loading={loading}
          pendingCount={pendingCount}
          onResume={() => setStep("review")}
        />
      )}

      {step === "map" && (
        <MapStep
          fileName={fileName}
          headers={headers}
          sample={sample}
          colMap={colMap}
          setColMap={setColMap}
          sourceBank={sourceBank}
          setSourceBank={setSourceBank}
          onBack={() => setStep("upload")}
          onNext={ingest}
          ingesting={ingesting}
        />
      )}

      {step === "review" && (
        <ReviewStep
          staged={staged}
          accounts={accounts}
          onPatchCode={patchCode}
          onReject={reject}
          onConfirm={confirmOne}
          onConfirmAll={confirmAll}
          onStartOver={startOver}
          confirmingId={confirmingId}
          busy={ingesting}
        />
      )}
    </div>
  );
}

// ---- Stepper ---------------------------------------------------------------
function Stepper({ current, pendingCount }) {
  const steps = [
    { id: "upload", label: "Upload CSV" },
    { id: "map", label: "Map columns" },
    { id: "review", label: `Review${pendingCount ? ` (${pendingCount})` : ""}` },
  ];
  const idx = steps.findIndex((s) => s.id === current);
  return (
    <ol className="flex items-center gap-2 text-[12.5px]" data-testid="bank-csv-stepper">
      {steps.map((s, i) => {
        const active = i === idx;
        const done = i < idx;
        return (
          <li key={s.id} className="flex items-center gap-2">
            <span
              className={`inline-flex items-center justify-center rounded-full font-semibold ${
                active
                  ? "bg-[#1A4FFF] text-white"
                  : done
                  ? "bg-[#1A4FFF]/15 text-[#1A4FFF]"
                  : "bg-[#0A16281A] text-[#0A1628]/60"
              }`}
              style={{ width: 22, height: 22 }}
            >
              {done ? <Check size={13} /> : i + 1}
            </span>
            <span className={active ? "font-semibold text-[#0A1628]" : "text-[#0A1628]/60"}>
              {s.label}
            </span>
            {i < steps.length - 1 && <ChevronRight size={13} className="text-[#0A1628]/25" />}
          </li>
        );
      })}
    </ol>
  );
}

// ---- Step 1 — Upload -------------------------------------------------------
function UploadStep({ onFile, loading, pendingCount, onResume }) {
  return (
    <div className="space-y-4">
      {pendingCount > 0 && (
        <div
          data-testid="bank-csv-resume-banner"
          className="rounded-xl border border-[#1A4FFF]/25 bg-[#1A4FFF]/[0.05] px-4 py-3 flex items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2.5 text-[13px] text-[#0A1628]">
            <AlertCircle size={16} className="text-[#1A4FFF] shrink-0" />
            <span>
              You have <b>{pendingCount}</b> staged transaction(s) waiting for review.
            </span>
          </div>
          <button
            type="button"
            onClick={onResume}
            data-testid="bank-csv-resume-btn"
            className="inline-flex items-center gap-1.5 rounded-full bg-[#1A4FFF] text-white px-3.5 py-1.5 text-[12.5px] font-semibold hover:opacity-90"
          >
            Resume review <ArrowRight size={13} />
          </button>
        </div>
      )}

      <label
        htmlFor="bank-csv-file"
        className="block rounded-2xl border-2 border-dashed border-[#0A16281A] hover:border-[#1A4FFF]/40 hover:bg-[#1A4FFF]/[0.03] transition-colors cursor-pointer p-10 text-center"
        data-testid="bank-csv-dropzone"
      >
        <div className="mx-auto mb-4 w-14 h-14 rounded-full flex items-center justify-center bg-[#1A4FFF]/[0.08]">
          <Upload size={22} className="text-[#1A4FFF]" />
        </div>
        <p className="text-[15px] font-semibold text-[#0A1628]">Upload a bank statement CSV</p>
        <p className="text-[13px] text-[#0A1628]/60 mt-1.5 max-w-md mx-auto">
          Any European or US bank export (ING, Rabobank, Bunq, Revolut, Wise, N26, …). Comma, semicolon or tab delimited — we auto-detect.
        </p>
        <input
          id="bank-csv-file"
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => onFile(e.target.files?.[0])}
          disabled={loading}
          data-testid="bank-csv-file-input"
        />
        <p className="mt-4 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-[#1A4FFF]">
          {loading ? (
            <>
              <Loader2 size={13} className="animate-spin" /> Parsing…
            </>
          ) : (
            <>
              <FileSpreadsheet size={13} /> Choose a CSV file
            </>
          )}
        </p>
      </label>
    </div>
  );
}

// ---- Step 2 — Map columns --------------------------------------------------
function MapStep({ fileName, headers, sample, colMap, setColMap, sourceBank, setSourceBank, onBack, onNext, ingesting }) {
  const setField = (k, v) => setColMap((prev) => ({ ...prev, [k]: v }));
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-[12.5px] text-[#0A1628]/70">
        <FileSpreadsheet size={14} /> {fileName || "CSV"}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MapField label="Date column *" value={colMap.date} onChange={(v) => setField("date", v)} headers={headers} testId="bank-csv-map-date" />
        <MapField label="Description column *" value={colMap.description} onChange={(v) => setField("description", v)} headers={headers} testId="bank-csv-map-desc" />
        <MapField label="Amount column *" value={colMap.amount} onChange={(v) => setField("amount", v)} headers={headers} testId="bank-csv-map-amount" />
        <MapField label="Currency column (optional)" value={colMap.currency} onChange={(v) => setField("currency", v)} headers={headers} testId="bank-csv-map-currency" />
      </div>

      <div className="max-w-sm">
        <label className="block text-[12.5px] font-semibold text-[#0A1628] mb-1">Source bank (optional)</label>
        <input
          type="text"
          placeholder="e.g. ING, Bunq, Revolut"
          value={sourceBank}
          onChange={(e) => setSourceBank(e.target.value)}
          className="w-full text-[13px] px-3 py-2 border border-[#0A162814] rounded-md"
          data-testid="bank-csv-source-bank"
        />
      </div>

      <div className="rounded-xl border border-[#0A162814] overflow-hidden">
        <div className="bg-[#F7F8FA] px-4 py-2 text-[12px] font-semibold uppercase tracking-wider text-[#0A1628]/60">
          Preview — first {sample.length} row(s)
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-[12.5px]">
            <thead>
              <tr className="border-b border-[#0A162814]">
                {headers.map((h) => (
                  <th key={h} className="px-3 py-2 text-left font-semibold text-[#0A1628]/70 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sample.map((row, i) => (
                <tr key={i} className="border-b border-[#0A162808] last:border-b-0">
                  {headers.map((h) => (
                    <td key={h} className="px-3 py-1.5 text-[#0A1628]/85 whitespace-nowrap">
                      {row[h]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          className="text-[13px] text-[#0A1628]/60 hover:text-[#0A1628]"
          data-testid="bank-csv-map-back"
        >
          ← Back
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={ingesting || !colMap.date || !colMap.description || !colMap.amount}
          data-testid="bank-csv-map-next"
          className="zy-btn-primary text-[13.5px] inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          {ingesting ? (
            <>
              <Loader2 size={14} className="animate-spin" /> Parsing & AI-classifying…
            </>
          ) : (
            <>
              <Sparkles size={14} /> Ingest & classify
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function MapField({ label, value, onChange, headers, testId }) {
  return (
    <div>
      <label className="block text-[12.5px] font-semibold text-[#0A1628] mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full text-[13px] px-3 py-2 border border-[#0A162814] rounded-md bg-white"
        data-testid={testId}
      >
        <option value="">— Select column —</option>
        {headers.map((h) => (
          <option key={h} value={h}>
            {h}
          </option>
        ))}
      </select>
    </div>
  );
}

// ---- Step 3 — Review -------------------------------------------------------
function ReviewStep({ staged, accounts, onPatchCode, onReject, onConfirm, onConfirmAll, onStartOver, confirmingId, busy }) {
  if (staged.length === 0) {
    return (
      <div className="text-center py-16" data-testid="bank-csv-review-empty">
        <div className="mx-auto mb-4 w-14 h-14 rounded-full flex items-center justify-center bg-[#D1FAE580]">
          <Check size={22} className="text-[#047857]" />
        </div>
        <p className="text-[15px] font-semibold text-[#0A1628]">All caught up.</p>
        <p className="text-[13px] text-[#0A1628]/60 mt-1.5">
          No pending bank transactions to review.
        </p>
        <button
          type="button"
          onClick={onStartOver}
          data-testid="bank-csv-review-import-more"
          className="mt-6 inline-flex items-center gap-1.5 rounded-full border border-[#0A16281A] px-4 py-2 text-[13px] font-semibold hover:bg-[#F7F8FA]"
        >
          <Upload size={13} /> Import another statement
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-semibold text-[#0A1628]">
            {staged.length} transaction{staged.length === 1 ? "" : "s"} pending review
          </h3>
          <p className="text-[12.5px] text-[#0A1628]/60 mt-0.5">
            Change the counterpart account if the AI got it wrong, then post to the journal.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onStartOver}
            className="rounded-full border border-[#0A16281A] px-3 py-1.5 text-[12.5px] font-semibold hover:bg-[#F7F8FA]"
            data-testid="bank-csv-review-restart"
          >
            Start over
          </button>
          <button
            type="button"
            onClick={onConfirmAll}
            disabled={busy}
            className="zy-btn-primary text-[13px] inline-flex items-center gap-1.5 disabled:opacity-50"
            data-testid="bank-csv-review-confirm-all"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            Post all to journal
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-[#0A162814] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-[13px]">
            <thead className="bg-[#F7F8FA] text-[#0A1628]/60">
              <tr>
                <th className="px-3 py-2.5 text-left font-semibold uppercase text-[11px] tracking-wider">Date</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase text-[11px] tracking-wider">Description</th>
                <th className="px-3 py-2.5 text-right font-semibold uppercase text-[11px] tracking-wider">Amount</th>
                <th className="px-3 py-2.5 text-left font-semibold uppercase text-[11px] tracking-wider">AI category</th>
                <th className="px-3 py-2.5 text-right font-semibold uppercase text-[11px] tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {staged.map((t) => {
                const conf = t.proposed_journal?.confidence ?? 0;
                const style = CONFIDENCE_STYLE(conf);
                const isConfirming = confirmingId === t.id;
                const amt = t.parsed.amount;
                return (
                  <tr
                    key={t.id}
                    className="border-t border-[#0A162808]"
                    data-testid={`bank-csv-tx-${t.id}`}
                  >
                    <td className="px-3 py-2 whitespace-nowrap text-[#0A1628]/85">{t.parsed.date}</td>
                    <td className="px-3 py-2 max-w-xs">
                      <div className="truncate text-[#0A1628]">{t.parsed.description || "—"}</div>
                      {t.proposed_journal?.rationale && (
                        <div className="text-[11.5px] text-[#0A1628]/50 truncate">{t.proposed_journal.rationale}</div>
                      )}
                    </td>
                    <td
                      className={`px-3 py-2 text-right font-semibold whitespace-nowrap ${
                        amt >= 0 ? "text-[#047857]" : "text-[#B91C1C]"
                      }`}
                    >
                      {amt >= 0 ? "+" : ""}€{fmt(amt)}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <select
                          value={t.proposed_journal?.counterpart_code || ""}
                          onChange={(e) => onPatchCode(t.id, e.target.value)}
                          className="text-[12.5px] px-2 py-1 border border-[#0A162814] rounded-md bg-white"
                          data-testid={`bank-csv-tx-${t.id}-code`}
                        >
                          {accounts.map((a) => (
                            <option key={a.id} value={a.code}>
                              {a.code} · {a.name}
                            </option>
                          ))}
                        </select>
                        <span
                          className="inline-flex items-center rounded-full px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wider"
                          style={{ background: style.bg, color: style.color }}
                          title={`Confidence ${(conf * 100).toFixed(0)}%`}
                        >
                          {style.label}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => onReject(t.id)}
                        title="Reject / skip"
                        className="p-1.5 rounded-md text-[#B91C1C]/70 hover:text-[#B91C1C] hover:bg-[#FEE2E280]"
                        data-testid={`bank-csv-tx-${t.id}-reject`}
                      >
                        <X size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => onConfirm(t.id)}
                        disabled={isConfirming}
                        title="Post to journal"
                        className="ml-1 p-1.5 rounded-md text-[#047857]/80 hover:text-[#047857] hover:bg-[#D1FAE580] disabled:opacity-40"
                        data-testid={`bank-csv-tx-${t.id}-confirm`}
                      >
                        {isConfirming ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
