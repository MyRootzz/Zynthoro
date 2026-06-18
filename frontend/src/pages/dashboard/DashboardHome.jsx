import { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { API, useAuth } from "@/contexts/AuthContext";
import {
  Wallet, ReceiptEuro, KanbanSquare, Users, FilePlus, UserPlus, FolderPlus, Send,
  Sparkles, ArrowRight,
} from "lucide-react";

const KPIS = [
  { key: "monthly_revenue", label: "Monthly Revenue", icon: Wallet, prefix: "€" },
  { key: "open_invoices", label: "Open Invoices", icon: ReceiptEuro },
  { key: "active_projects", label: "Active Projects", icon: KanbanSquare },
  { key: "team_members", label: "Team Members", icon: Users },
];

const QUICK = [
  { label: "New Invoice", icon: FilePlus, to: "/dashboard/finance" },
  { label: "New Client", icon: UserPlus, to: "/dashboard/sales" },
  { label: "New Project", icon: FolderPlus, to: "/dashboard/projects" },
  { label: "Invite Team Member", icon: Send, to: "/dashboard/team" },
];

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/dashboard/summary`);
        setData(data);
      } catch {
        setData({ kpis: { monthly_revenue: 0, open_invoices: 0, active_projects: 0, team_members: 1 }, ai_suggestions: [], recent_activity: [] });
      }
    })();
  }, []);

  return (
    <div className="space-y-8" data-testid="dashboard">
      {/* KPI cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {KPIS.map((k) => (
          <div key={k.key} className="bg-white border border-[#eee] rounded-xl p-5" data-testid={`kpi-${k.key}`}>
            <div className="flex items-center justify-between">
              <span className="zy-domain-icon" style={{ width: 36, height: 36, marginBottom: 0 }}>
                <k.icon size={16} />
              </span>
              <span className="text-[11px] uppercase tracking-wider text-[#999] font-semibold">{k.label}</span>
            </div>
            <p className="mt-4 text-[26px] font-bold tracking-tight text-black">
              {k.prefix || ""}{(data?.kpis?.[k.key] ?? 0).toLocaleString("en-US")}
            </p>
          </div>
        ))}
      </section>

      {/* Quick actions */}
      <section>
        <h2 className="text-[15px] font-semibold mb-3">Quick actions</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {QUICK.map((q) => (
            <Link
              key={q.label}
              to={q.to}
              className="bg-white border border-[#eee] rounded-xl p-4 hover:border-[#1A4FFF] transition-all"
              data-testid={`quick-${q.label.toLowerCase().replace(/\s+/g, "-")}`}
            >
              <span className="zy-domain-icon" style={{ width: 36, height: 36, marginBottom: 12 }}>
                <q.icon size={16} />
              </span>
              <p className="text-[13.5px] font-semibold">{q.label}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* AI Suggestions */}
      <section className="bg-white border border-[#eee] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles size={16} style={{ color: "#1A4FFF" }} />
          <h2 className="text-[14.5px] font-semibold">Zynthoro Assist suggests:</h2>
        </div>
        <ul className="space-y-2.5">
          {(data?.ai_suggestions || []).map((s, i) => (
            <li key={i} className="flex items-start gap-2 text-[13.5px] text-[#333]">
              <ArrowRight size={14} className="mt-1 shrink-0" style={{ color: "#1A4FFF" }} />
              <span>{s}</span>
            </li>
          ))}
          {!data?.ai_suggestions?.length && (
            <li className="text-[13px] text-[#999]">Loading suggestions…</li>
          )}
        </ul>
      </section>

      {/* Recent activity */}
      <section className="bg-white border border-[#eee] rounded-xl p-6">
        <h2 className="text-[14.5px] font-semibold mb-2">Recent activity</h2>
        {(data?.recent_activity || []).length === 0 ? (
          <p className="text-[13.5px] text-[#888]">
            Your activity will appear here. Start by creating your first invoice or project.
          </p>
        ) : (
          <ul>{/* TODO render */}</ul>
        )}
      </section>
    </div>
  );
}
