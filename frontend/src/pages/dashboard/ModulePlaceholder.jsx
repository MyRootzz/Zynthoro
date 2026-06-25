import { useEffect, useState } from "react";
import axios from "axios";
import { useParams } from "react-router-dom";
import { Construction, Briefcase, FileText, Calendar, TrendingUp, AlertCircle, CheckCircle2, Clock } from "lucide-react";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";

const TITLES = {
  planning: "Planning & Organisation",
  "time-tracking": "Time Tracking",
  sales: "Sales",
  finance: "Finance & Invoicing",
  accounting: "Accounting",
  projects: "Projects",
  hr: "HR & Personnel",
  operations: "Operations",
  marketing: "Marketing & Content",
  communication: "Communication & Collaboration",
  compliance: "Compliance & Security",
  settings: "Settings",
};

const STATUS_STYLES = {
  "On track":  { bg: "rgba(34,197,94,0.12)",  fg: "#16a34a", icon: CheckCircle2 },
  "Completed": { bg: "rgba(26,79,255,0.12)",  fg: "#1A4FFF", icon: CheckCircle2 },
  "At risk":   { bg: "rgba(217,119,6,0.12)",  fg: "#D97706", icon: AlertCircle },
  "Paid":      { bg: "rgba(34,197,94,0.12)",  fg: "#16a34a", icon: CheckCircle2 },
  "Sent":      { bg: "rgba(26,79,255,0.12)",  fg: "#1A4FFF", icon: Clock },
  "Draft":     { bg: "#F4F6FB",               fg: "#666",    icon: FileText },
  "Overdue":   { bg: "rgba(220,38,38,0.10)",  fg: "#dc2626", icon: AlertCircle },
};

function StatusBadge({ status }) {
  const cfg = STATUS_STYLES[status] || STATUS_STYLES.Draft;
  const Icon = cfg.icon;
  return (
    <span
      className="inline-flex items-center gap-1 text-[11.5px] font-semibold px-2 py-0.5 rounded-full"
      style={{ background: cfg.bg, color: cfg.fg }}
    >
      <Icon size={11} /> {status}
    </span>
  );
}

export default function ModulePlaceholder() {
  const { slug } = useParams();
  const { user } = useAuth();
  const title = TITLES[slug] || "Module";

  // Demo accounts get real data on Projects and Finance routes
  if (user?.is_demo && slug === "projects") return <DemoProjects />;
  if (user?.is_demo && slug === "finance") return <DemoInvoices />;

  return (
    <div className="max-w-2xl">
      <p className="zy-eyebrow mb-3">Module</p>
      <h1 className="text-[24px] sm:text-[28px] font-bold tracking-tight">{title}</h1>
      <div className="mt-8 bg-white border border-[#eee] rounded-xl p-6 sm:p-8 text-center">
        <span className="zy-domain-icon mx-auto" style={{ width: 48, height: 48 }}>
          <Construction size={20} />
        </span>
        <p className="mt-4 text-[14px] text-[#555]">This module is part of the upcoming launch — June 30, 2026.</p>
      </div>
    </div>
  );
}

function DemoProjects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/demo/projects`);
        setProjects(data.projects || []);
      } catch (e) {
        formatApiError(e?.response?.data?.detail);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const onTrack = projects.filter((p) => p.status === "On track").length;
  const done   = projects.filter((p) => p.status === "Completed").length;
  const atRisk = projects.filter((p) => p.status === "At risk").length;

  return (
    <div data-testid="demo-projects-page" className="max-w-5xl">
      <p className="zy-eyebrow mb-2">Demo workspace · Projects</p>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <h1 className="text-[24px] sm:text-[28px] font-bold tracking-tight flex items-center gap-2">
          <Briefcase size={22} style={{ color: "#1A4FFF" }} />
          Projects
        </h1>
        <p className="text-[12.5px] text-[#666]">{projects.length} projects · sample data for demo purposes</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
        <StatPill label="Total" value={projects.length} icon={Briefcase} accent="#1A4FFF" />
        <StatPill label="On track" value={onTrack} icon={TrendingUp} accent="#16a34a" />
        <StatPill label="At risk" value={atRisk} icon={AlertCircle} accent="#D97706" />
        <StatPill label="Completed" value={done} icon={CheckCircle2} accent="#1A4FFF" />
      </div>

      <div className="mt-6 bg-white border border-[#eee] rounded-2xl overflow-hidden">
        {loading ? (
          <p className="p-6 text-[13.5px] text-[#888]">Loading demo projects…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13.5px]" data-testid="demo-projects-table">
              <thead className="bg-[#FAFAFB] text-[#777] text-[11.5px] uppercase tracking-wider">
                <tr>
                  <th className="text-left py-3 px-4">Project</th>
                  <th className="text-left py-3 px-4">Domain</th>
                  <th className="text-left py-3 px-4 hidden sm:table-cell">Owner</th>
                  <th className="text-left py-3 px-4">Status</th>
                  <th className="text-left py-3 px-4 hidden md:table-cell">Progress</th>
                  <th className="text-left py-3 px-4 hidden md:table-cell">Due</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p, i) => (
                  <tr key={p.id} className={i % 2 ? "bg-[#FAFAFB]" : ""}>
                    <td className="py-3 px-4 font-semibold text-black">{p.name}</td>
                    <td className="py-3 px-4 text-[#555]">{p.domain}</td>
                    <td className="py-3 px-4 hidden sm:table-cell text-[#555]">{p.owner}</td>
                    <td className="py-3 px-4"><StatusBadge status={p.status} /></td>
                    <td className="py-3 px-4 hidden md:table-cell">
                      <div className="flex items-center gap-2 w-[140px]">
                        <div className="flex-1 h-1.5 rounded-full bg-[#eee] overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${p.progress}%`, background: "#1A4FFF" }} />
                        </div>
                        <span className="text-[11.5px] text-[#666] tabular-nums">{p.progress}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 hidden md:table-cell">
                      <span className="inline-flex items-center gap-1 text-[#555]">
                        <Calendar size={11} /> {p.due}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function DemoInvoices() {
  const [invoices, setInvoices] = useState([]);
  const [totals, setTotals] = useState({ total_eur: 0, paid_eur: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/demo/invoices`);
        setInvoices(data.invoices || []);
        setTotals({ total_eur: data.total_eur || 0, paid_eur: data.paid_eur || 0 });
      } catch (e) {
        formatApiError(e?.response?.data?.detail);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div data-testid="demo-invoices-page" className="max-w-5xl">
      <p className="zy-eyebrow mb-2">Demo workspace · Finance</p>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <h1 className="text-[24px] sm:text-[28px] font-bold tracking-tight flex items-center gap-2">
          <FileText size={22} style={{ color: "#1A4FFF" }} />
          Finance &amp; Invoicing
        </h1>
        <p className="text-[12.5px] text-[#666]">{invoices.length} invoices · sample data for demo purposes</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-6">
        <StatPill label="Invoiced" value={`€${totals.total_eur.toLocaleString("en-IE")}`} icon={FileText} accent="#1A4FFF" big />
        <StatPill label="Paid" value={`€${totals.paid_eur.toLocaleString("en-IE")}`} icon={CheckCircle2} accent="#16a34a" big />
        <StatPill label="Outstanding" value={`€${(totals.total_eur - totals.paid_eur).toLocaleString("en-IE")}`} icon={Clock} accent="#D97706" big />
      </div>

      <div className="mt-6 bg-white border border-[#eee] rounded-2xl overflow-hidden">
        {loading ? (
          <p className="p-6 text-[13.5px] text-[#888]">Loading demo invoices…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13.5px]" data-testid="demo-invoices-table">
              <thead className="bg-[#FAFAFB] text-[#777] text-[11.5px] uppercase tracking-wider">
                <tr>
                  <th className="text-left py-3 px-4">Number</th>
                  <th className="text-left py-3 px-4">Client</th>
                  <th className="text-right py-3 px-4">Amount</th>
                  <th className="text-left py-3 px-4 hidden sm:table-cell">Issued</th>
                  <th className="text-left py-3 px-4 hidden sm:table-cell">Due</th>
                  <th className="text-left py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv, i) => (
                  <tr key={inv.id} className={i % 2 ? "bg-[#FAFAFB]" : ""}>
                    <td className="py-3 px-4 font-mono text-[12.5px] font-semibold">{inv.number}</td>
                    <td className="py-3 px-4 text-black font-medium">{inv.client}</td>
                    <td className="py-3 px-4 text-right font-semibold tabular-nums">€{inv.amount_eur.toLocaleString("en-IE")}</td>
                    <td className="py-3 px-4 hidden sm:table-cell text-[#555]">{inv.issued}</td>
                    <td className="py-3 px-4 hidden sm:table-cell text-[#555]">{inv.due}</td>
                    <td className="py-3 px-4"><StatusBadge status={inv.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatPill({ label, value, icon: Icon, accent = "#1A4FFF", big = false }) {
  return (
    <div className="bg-white border border-[#eee] rounded-xl p-3 sm:p-4">
      <div className="flex items-center gap-2 mb-1">
        <Icon size={13} style={{ color: accent }} />
        <span className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: accent }}>{label}</span>
      </div>
      <p className={`mt-1 font-bold ${big ? "text-[18px] sm:text-[20px]" : "text-[20px]"}`} style={{ color: "#0A1628" }}>
        {value}
      </p>
    </div>
  );
}
