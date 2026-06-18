import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { API, formatApiError } from "@/contexts/AuthContext";
import { Flag, Users, MessageCircle, Database, Beaker } from "lucide-react";

export default function BuilderModePanel() {
  const [stats, setStats] = useState(null);
  const [flags, setFlags] = useState(null);
  const [signups, setSignups] = useState([]);

  const loadAll = async () => {
    try {
      const [a, b, c] = await Promise.all([
        axios.get(`${API}/founder/stats`),
        axios.get(`${API}/founder/feature-flags`),
        axios.get(`${API}/founder/presale-signups`),
      ]);
      setStats(a.data);
      setFlags(b.data);
      setSignups(c.data.signups || []);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Could not load builder data.");
    }
  };

  useEffect(() => { loadAll(); }, []);

  const updateFlag = async (k, v) => {
    setFlags((f) => ({ ...f, [k]: v }));
    try {
      await axios.patch(`${API}/founder/feature-flags`, { [k]: v });
      toast.success("Flag updated.");
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Could not update flag.");
      loadAll();
    }
  };

  return (
    <div className="mt-10 rounded-2xl border-2 border-dashed p-6" style={{ borderColor: "#D4AF37", background: "#FFFCEC" }} data-testid="builder-panel">
      <div className="flex items-center gap-2 mb-5">
        <Beaker size={16} style={{ color: "#8a6e1d" }} />
        <h2 className="text-[15px] font-bold tracking-tight" style={{ color: "#5a4a0e" }}>
          Builder Mode · Founder Only
        </h2>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard icon={Users} label="Users" value={stats?.user_count} />
        <StatCard icon={Flag} label="Presale signups" value={stats?.presale_count} />
        <StatCard icon={MessageCircle} label="AI messages" value={stats?.ai_messages} />
        <StatCard icon={Database} label="Team members" value={stats?.team_members} />
      </div>

      {flags && (
        <div className="bg-white rounded-lg border border-[#eee] p-4 mb-6">
          <h3 className="text-[13.5px] font-semibold mb-3">Feature flags</h3>
          <div className="space-y-3">
            {[
              ["ai_assistants_enabled", "AI assistants"],
              ["presale_open", "Presale open"],
              ["beta_modules_enabled", "Beta modules"],
              ["stripe_enabled", "Stripe checkout"],
            ].map(([k, label]) => (
              <div key={k} className="flex items-center justify-between">
                <Label className="text-[13px]">{label}</Label>
                <Switch checked={!!flags[k]} onCheckedChange={(v) => updateFlag(k, v)} data-testid={`flag-${k}`} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg border border-[#eee] p-4">
        <h3 className="text-[13.5px] font-semibold mb-3">Presale signups · {signups.length}</h3>
        {signups.length === 0 ? (
          <p className="text-[12.5px] text-[#999]">No signups yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead className="text-[#666]">
                <tr>
                  <th className="text-left py-1.5 pr-4">Name</th>
                  <th className="text-left py-1.5 pr-4">Email</th>
                  <th className="text-left py-1.5 pr-4">Company</th>
                  <th className="text-left py-1.5 pr-4">Plan</th>
                  <th className="text-left py-1.5">When</th>
                </tr>
              </thead>
              <tbody>
                {signups.slice(0, 20).map((s) => (
                  <tr key={s.id} className="border-t border-[#f2f2f2]">
                    <td className="py-1.5 pr-4">{s.name}</td>
                    <td className="py-1.5 pr-4">{s.email}</td>
                    <td className="py-1.5 pr-4">{s.company || "—"}</td>
                    <td className="py-1.5 pr-4">{s.plan_interest || "—"}</td>
                    <td className="py-1.5 text-[#888]">{new Date(s.created_at).toLocaleString()}</td>
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

function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="bg-white border border-[#eee] rounded-lg p-3">
      <div className="flex items-center gap-2 text-[#888]">
        <Icon size={14} />
        <span className="text-[11px] uppercase tracking-wider font-semibold">{label}</span>
      </div>
      <p className="mt-1.5 text-[20px] font-bold">{value ?? "—"}</p>
    </div>
  );
}
