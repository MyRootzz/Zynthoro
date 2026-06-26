import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { API, formatApiError } from "@/contexts/AuthContext";
import { Flag, Users, MessageCircle, Database, Beaker, Mail, Send, Loader2, CheckCircle2, Download } from "lucide-react";
import StripeMetricsCard from "@/components/dashboard/StripeMetricsCard";
import { downloadCsv, todayStamp } from "@/lib/csvExport";

export default function BuilderModePanel() {
  const [stats, setStats] = useState(null);
  const [flags, setFlags] = useState(null);
  const [signups, setSignups] = useState([]);
  const [voice, setVoice] = useState(null);

  const loadAll = async () => {
    try {
      const [a, b, c, d] = await Promise.all([
        axios.get(`${API}/founder/stats`),
        axios.get(`${API}/founder/feature-flags`),
        axios.get(`${API}/founder/presale-signups`),
        axios.get(`${API}/founder/voice-tryouts`),
      ]);
      setStats(a.data);
      setFlags(b.data);
      setSignups(c.data.signups || []);
      setVoice(d.data);
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

      <StripeMetricsCard />

      <DigestCard />

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
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h3 className="text-[13.5px] font-semibold">Presale signups · {signups.length}</h3>
          <button
            onClick={() => downloadCsv(
              `zynthoro_presale_${todayStamp()}.csv`,
              signups,
              [
                { key: "name",          label: "Name" },
                { key: "email",         label: "Email" },
                { key: "company",       label: "Company", value: (r) => r.company || "" },
                { key: "plan_interest", label: "Plan interest", value: (r) => r.plan_interest || "" },
                { key: "created_at",    label: "Created at" },
              ],
            )}
            disabled={signups.length === 0}
            data-testid="presale-export-csv"
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-[#eee] text-[12px] font-semibold text-[#555] hover:border-[#1A4FFF] hover:text-[#1A4FFF] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download size={12} /> Export CSV
          </button>
        </div>
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

      <VoiceLeadsPanel voice={voice} />
    </div>
  );
}

function VoiceLeadsPanel({ voice }) {
  if (!voice) return null;
  const leads = voice.leads || [];
  const named = leads.filter((l) => l.email).slice(0, 10);
  const allWithEmail = leads.filter((l) => l.email);
  return (
    <div className="bg-white rounded-lg border border-[#eee] p-4 mt-6" data-testid="voice-leads-panel">
      <div className="flex flex-wrap items-end justify-between gap-2 mb-3">
        <h3 className="text-[13.5px] font-semibold">
          Voice tryout leads · {voice.with_email_count}
          <span className="ml-2 text-[11.5px] text-[#888] font-normal">
            ({voice.anonymous_count} anonymous tryouts not shown)
          </span>
        </h3>
        <div className="flex items-center gap-3">
          <p className="text-[11.5px] text-[#888]">Last 10 with email · golden product-research signal</p>
          <button
            onClick={() => downloadCsv(
              `zynthoro_voice_leads_${todayStamp()}.csv`,
              allWithEmail,
              [
                { key: "email",      label: "Email" },
                { key: "transcript", label: "Transcript", value: (r) => r.transcript || "" },
                { key: "language",   label: "Language", value: (r) => r.language || "" },
                { key: "user_agent", label: "User agent", value: (r) => r.user_agent || "" },
                { key: "ip",         label: "IP", value: (r) => r.ip || "" },
                { key: "created_at", label: "Created at" },
              ],
            )}
            disabled={allWithEmail.length === 0}
            data-testid="voice-leads-export-csv"
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-[#eee] text-[12px] font-semibold text-[#555] hover:border-[#1A4FFF] hover:text-[#1A4FFF] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download size={12} /> Export CSV
          </button>
        </div>
      </div>
      {named.length === 0 ? (
        <p className="text-[12.5px] text-[#999]">No voice tryout leads with email yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead className="text-[#666]">
              <tr>
                <th className="text-left py-1.5 pr-4 w-[28%]">Email</th>
                <th className="text-left py-1.5 pr-4">Transcript</th>
                <th className="text-left py-1.5 pr-4 w-[10%]">Lang</th>
                <th className="text-left py-1.5 w-[18%]">When</th>
              </tr>
            </thead>
            <tbody>
              {named.map((l) => (
                <tr key={l.id} className="border-t border-[#f2f2f2] align-top">
                  <td className="py-1.5 pr-4 font-medium text-black">{l.email}</td>
                  <td className="py-1.5 pr-4 text-[#555] italic">
                    “{(l.transcript || "").slice(0, 140) || "(no transcript)"}{(l.transcript || "").length > 140 ? "…" : ""}”
                  </td>
                  <td className="py-1.5 pr-4 text-[#888] uppercase text-[11px]">{l.language || "—"}</td>
                  <td className="py-1.5 text-[#888]">{new Date(l.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
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

function DigestCard() {
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [lastSent, setLastSent] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/founder/digest/preview`);
        setPreview(data);
      } catch (e) {
        toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't load digest preview.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const send = async () => {
    setSending(true);
    try {
      const { data } = await axios.post(`${API}/founder/digest/send?force=true`);
      if (data?.sent) {
        setLastSent(new Date());
        toast.success(`Digest sent to ${data.to}.`);
      } else {
        toast.info("Digest already sent today (forced override).");
      }
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't send digest.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="bg-white rounded-lg border border-[#eee] p-4 mb-6" data-testid="digest-card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <span className="inline-flex items-center justify-center w-9 h-9 rounded-md shrink-0" style={{ background: "rgba(212,175,55,0.16)" }}>
            <Mail size={15} style={{ color: "#8a6e1d" }} />
          </span>
          <div>
            <h3 className="text-[13.5px] font-semibold">Daily pipeline digest</h3>
            <p className="text-[12px] text-[#666] mt-0.5 max-w-md">
              Auto-sent to <span className="font-medium text-black">info@zynthoro.ai</span> every day at 07:00 UTC. Use the button to fire a test send right now.
            </p>
          </div>
        </div>
        <button
          onClick={send}
          disabled={sending}
          data-testid="digest-send-now"
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-[12.5px] font-semibold text-white disabled:opacity-60"
          style={{ background: "#1A4FFF" }}
        >
          {sending ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
          {sending ? "Sending…" : "Send test now"}
        </button>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-[12px]">
        <Tile label="Presale (24h)" value={loading ? "—" : preview?.presale_count ?? 0} />
        <Tile label="Voice leads (24h)" value={loading ? "—" : preview?.voice_lead_count ?? 0} />
        <Tile label="Anon. tryouts (24h)" value={loading ? "—" : preview?.voice_anonymous_count ?? 0} />
      </div>

      {lastSent && (
        <p className="mt-3 text-[12px] text-green-700 flex items-center gap-1.5" data-testid="digest-last-sent">
          <CheckCircle2 size={13} /> Test digest sent at {lastSent.toLocaleTimeString()}.
        </p>
      )}
    </div>
  );
}

function Tile({ label, value }) {
  return (
    <div className="rounded-md p-2.5" style={{ background: "#FAFAFB", border: "1px solid #eee" }}>
      <p className="text-[10.5px] uppercase tracking-wider text-[#888] font-semibold">{label}</p>
      <p className="text-[18px] font-bold mt-0.5" style={{ color: "#0A1628" }}>{value}</p>
    </div>
  );
}
