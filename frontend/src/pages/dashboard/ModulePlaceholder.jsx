import { useEffect, useState } from "react";
import axios from "axios";
import { useParams, Link } from "react-router-dom";
import {
  Briefcase, FileText, Calendar, TrendingUp, AlertCircle, CheckCircle2, Clock,
  CalendarClock, Timer, ShoppingCart, ReceiptEuro, Calculator, KanbanSquare,
  Users, Workflow, Megaphone, MessagesSquare, ShieldCheck, Plus, ArrowRight, Sparkles,
} from "lucide-react";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";

const MODULES = {
  planning: {
    title: "Planning & Organisation",
    icon: CalendarClock,
    eyebrow: "Plan smarter with Zynthoro",
    desc: "Roadmaps, sprints and team planning — synced across every domain.",
    actions: [
      { label: "Create a new plan", icon: Plus, primary: true },
      { label: "Open weekly board", icon: KanbanSquare },
      { label: "Set a quarterly OKR", icon: TrendingUp },
    ],
    tiles: ["Sprint board", "Quarterly OKRs", "Resource calendar", "Capacity planning"],
  },
  "time-tracking": {
    title: "Time Tracking",
    icon: Timer,
    eyebrow: "Every billable minute, captured",
    desc: "Smart timers, automatic timesheets and AI-suggested entries.",
    actions: [
      { label: "Start a timer", icon: Plus, primary: true },
      { label: "Add manual entry", icon: Clock },
      { label: "Export timesheet", icon: FileText },
    ],
    tiles: ["Live timers", "Weekly timesheets", "Project allocation", "Billable summary"],
  },
  sales: {
    title: "Sales",
    icon: ShoppingCart,
    eyebrow: "Pipeline + AI lead scoring",
    desc: "Track leads, deals and close-rates with Zyona’s growth intelligence.",
    actions: [
      { label: "Add a new lead", icon: Plus, primary: true },
      { label: "Open pipeline", icon: TrendingUp },
      { label: "Score with Zyona", icon: Sparkles },
    ],
    tiles: ["Pipeline board", "Deal forecasts", "Quote builder", "Win/loss insights"],
  },
  finance: {
    title: "Finance & Invoicing",
    icon: ReceiptEuro,
    eyebrow: "Invoices, cashflow & taxes",
    desc: "Send invoices, reconcile payments and forecast cashflow in one place.",
    actions: [
      { label: "Create an invoice", icon: Plus, primary: true },
      { label: "Record a payment", icon: CheckCircle2 },
      { label: "Cashflow forecast", icon: TrendingUp },
    ],
    tiles: ["Invoices", "Payments", "Cashflow", "VAT & taxes"],
  },
  accounting: {
    title: "Accounting",
    icon: Calculator,
    eyebrow: "Books that close themselves",
    desc: "Double-entry ledger, journal entries and AI reconciliations.",
    actions: [
      { label: "New journal entry", icon: Plus, primary: true },
      { label: "Open trial balance", icon: FileText },
      { label: "Reconcile bank feed", icon: CheckCircle2 },
    ],
    tiles: ["Chart of accounts", "Trial balance", "P&L", "Balance sheet"],
  },
  projects: {
    title: "Projects",
    icon: KanbanSquare,
    eyebrow: "Deliver on time, every time",
    desc: "Boards, Gantt views, milestones and resource allocation.",
    actions: [
      { label: "Create a project", icon: Plus, primary: true },
      { label: "Open Gantt view", icon: Calendar },
      { label: "Add a milestone", icon: CheckCircle2 },
    ],
    tiles: ["Boards", "Gantt", "Milestones", "Workload"],
  },
  hr: {
    title: "HR & Personnel",
    icon: Users,
    eyebrow: "People operations, automated",
    desc: "Hiring, contracts, leave and payroll-ready exports.",
    actions: [
      { label: "Invite a teammate", icon: Plus, primary: true, to: "/dashboard/team" },
      { label: "Open org chart", icon: Users },
      { label: "Manage leave requests", icon: Calendar },
    ],
    tiles: ["Org chart", "Contracts", "Leave & PTO", "Payroll exports"],
  },
  operations: {
    title: "Operations",
    icon: Workflow,
    eyebrow: "Automate the busywork",
    desc: "Workflows, approvals and AI-orchestrated SOPs across domains.",
    actions: [
      { label: "Create a workflow", icon: Plus, primary: true },
      { label: "Set an approval rule", icon: CheckCircle2 },
      { label: "Browse templates", icon: Sparkles },
    ],
    tiles: ["Workflows", "Approvals", "SOP library", "Audit trail"],
  },
  marketing: {
    title: "Marketing & Content",
    icon: Megaphone,
    eyebrow: "Powered by Zyntha",
    desc: "Social media, content calendar, photo & video studios — all unified.",
    actions: [
      { label: "Open Social Studio", icon: ArrowRight, primary: true, to: "/dashboard/marketing" },
    ],
    tiles: ["Social compose", "Calendar", "Photo studio", "Video studio"],
  },
  communication: {
    title: "Communication & Collaboration",
    icon: MessagesSquare,
    eyebrow: "Talk less, ship more",
    desc: "Internal chat, shared inbox and AI-summarised threads.",
    actions: [
      { label: "Start a channel", icon: Plus, primary: true },
      { label: "Open shared inbox", icon: MessagesSquare },
      { label: "Summarise a thread", icon: Sparkles },
    ],
    tiles: ["Channels", "Shared inbox", "Threads", "Mentions"],
  },
  compliance: {
    title: "Compliance & Security",
    icon: ShieldCheck,
    eyebrow: "GDPR, SOC 2 and beyond",
    desc: "Policies, audit logs, DPA evidence and SOC 2 controls — built-in.",
    actions: [
      { label: "Run a compliance check", icon: CheckCircle2, primary: true },
      { label: "View audit log", icon: FileText },
      { label: "Manage policies", icon: ShieldCheck },
    ],
    tiles: ["GDPR controls", "SOC 2 evidence", "Audit log", "Data residency"],
  },
  settings: {
    title: "Settings",
    icon: Workflow,
    eyebrow: "Workspace settings",
    desc: "Profile, billing, plans and integrations.",
    actions: [
      { label: "Open settings", icon: ArrowRight, primary: true, to: "/dashboard/settings" },
    ],
    tiles: ["Profile", "Billing", "Plans", "Integrations"],
  },
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
  const cfg = MODULES[slug] || {
    title: "Module",
    icon: Workflow,
    eyebrow: "Workspace module",
    desc: "Manage and configure this Zynthoro domain.",
    actions: [{ label: "Open settings", icon: ArrowRight, primary: true, to: "/dashboard/settings" }],
    tiles: ["Overview", "Activity", "Reports", "Settings"],
  };

  // Demo accounts get real data on Projects and Finance routes
  if (user?.is_demo && slug === "projects") return <DemoProjects />;
  if (user?.is_demo && slug === "finance") return <DemoInvoices />;

  const Icon = cfg.icon;
  return (
    <div className="max-w-5xl" data-testid={`module-${slug}-page`}>
      <p className="zy-eyebrow mb-2" style={{ color: "#1A4FFF" }}>{cfg.eyebrow}</p>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <h1 className="text-[24px] sm:text-[28px] font-bold tracking-tight flex items-center gap-2">
          <Icon size={22} style={{ color: "#1A4FFF" }} />
          {cfg.title}
        </h1>
        <p className="text-[12.5px] text-[#666] max-w-md">{cfg.desc}</p>
      </div>

      {/* Quick actions */}
      <section className="mt-6 bg-white border border-[#eee] rounded-2xl p-5 sm:p-6">
        <h2 className="text-[14px] font-semibold mb-4">Quick actions</h2>
        <div className="flex flex-wrap gap-2">
          {cfg.actions.map((a, i) => {
            const ActionIcon = a.icon;
            const className = a.primary ? "zy-btn-primary" : "zy-btn-outline";
            const inner = (
              <>
                <ActionIcon size={14} /> {a.label}
              </>
            );
            return a.to ? (
              <Link key={i} to={a.to} className={className} data-testid={`module-action-${i}`}>
                {inner}
              </Link>
            ) : (
              <button key={i} className={className} data-testid={`module-action-${i}`}>
                {inner}
              </button>
            );
          })}
        </div>
      </section>

      {/* Module tiles */}
      <section className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
        {cfg.tiles.map((t) => (
          <div
            key={t}
            className="bg-white border border-[#eee] rounded-xl p-4 hover:border-[#1A4FFF] transition-colors cursor-pointer"
            data-testid={`module-tile-${t.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
          >
            <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3" style={{ background: "#EAF0FF" }}>
              <Icon size={16} style={{ color: "#1A4FFF" }} />
            </div>
            <p className="text-[13.5px] font-semibold text-black">{t}</p>
            <p className="text-[11.5px] text-[#888] mt-0.5">Open module</p>
          </div>
        ))}
      </section>

      <div className="mt-6 bg-white border border-[#eee] rounded-xl p-4 flex items-start gap-3">
        <Sparkles size={16} style={{ color: "#1A4FFF" }} className="mt-0.5 shrink-0" />
        <p className="text-[13px] text-[#555]">
          <span className="font-semibold text-black">Tip:</span> ask{" "}
          <Link to="/dashboard/zyntha" className="text-[#1A4FFF] font-semibold hover:underline">Zynthoro Assist</Link>{" "}
          to set up this module for you — it can create your first records, configure templates and import existing data.
        </p>
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
