import { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { ZyLogo } from "@/components/ZyLogo";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import {
  Building2, FileText, UserPlus, FolderPlus, Boxes, Sparkles,
  ArrowRight, ArrowLeft, Check, Rocket,
} from "lucide-react";

const FIRST_ACTIONS = [
  { id: "invoice", label: "Create an invoice", icon: FileText },
  { id: "client", label: "Add a client", icon: UserPlus },
  { id: "project", label: "Start a project", icon: FolderPlus },
  { id: "team", label: "Invite a team member", icon: UserPlus },
  { id: "inventory", label: "Add inventory", icon: Boxes },
  { id: "ai", label: "Use AI assistant", icon: Sparkles },
];

export default function Onboarding() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    company_name: user?.company || "",
    country: "",
    industry: "",
    employees: "",
    website: "",
    first_action: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const total = 6;
  const progress = (step / total) * 100;

  const next = () => setStep((s) => Math.min(total, s + 1));
  const prev = () => setStep((s) => Math.max(1, s - 1));
  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const finish = async () => {
    setSubmitting(true);
    try {
      await axios.post(`${API}/onboarding/complete`, form);
      await refresh();
      toast.success("Workspace ready!");
      navigate("/dashboard");
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Could not finish onboarding.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-white flex flex-col">
      <header className="px-6 sm:px-10 py-6 flex items-center justify-between border-b border-[#eee]">
        <div style={{ background: "#0A1628", padding: "8px 14px", borderRadius: 8 }}>
          <ZyLogo size={18} />
        </div>
        <p className="text-[12.5px] text-[#666]">
          Step {step} of {total}
        </p>
      </header>

      <div className="h-1 bg-[#eee]">
        <div className="h-full transition-all" style={{ width: `${progress}%`, background: "#1A4FFF" }} />
      </div>

      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-[560px]" data-testid={`onboarding-step-${step}`}>
          {step === 1 && (
            <div className="text-center">
              <div className="zy-domain-icon mx-auto" style={{ width: 56, height: 56 }}>
                <Rocket size={24} />
              </div>
              <h1 className="text-[32px] font-bold tracking-tight mt-5">
                Welcome to Zynthoro{user?.first_name ? `, ${user.first_name}` : ""} —<br />
                let&apos;s set up your workspace.
              </h1>
              <p className="text-[15px] text-[#555] mt-4 max-w-md mx-auto">
                In about two minutes we&apos;ll personalise Zynthoro to fit your business.
              </p>
              <button onClick={next} className="zy-btn-primary mt-8" data-testid="onb-start">
                Start setup <ArrowRight size={16} />
              </button>
            </div>
          )}

          {step === 2 && (
            <div>
              <p className="zy-eyebrow mb-3">Company settings</p>
              <h2 className="text-[26px] font-bold tracking-tight">Tell us about your business</h2>
              <div className="mt-7 space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="cn" className="text-[13px] font-medium">Company name</Label>
                  <Input id="cn" data-testid="onb-company" value={form.company_name} onChange={(e) => update("company_name", e.target.value)} />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-[13px] font-medium">Country</Label>
                    <Select value={form.country} onValueChange={(v) => update("country", v)}>
                      <SelectTrigger data-testid="onb-country"><SelectValue placeholder="Select country" /></SelectTrigger>
                      <SelectContent>
                        {["Netherlands","Belgium","Germany","France","Spain","Italy","United Kingdom","Ireland","Sweden","Other"].map((c) => (
                          <SelectItem key={c} value={c}>{c}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[13px] font-medium">Industry</Label>
                    <Select value={form.industry} onValueChange={(v) => update("industry", v)}>
                      <SelectTrigger data-testid="onb-industry"><SelectValue placeholder="Select industry" /></SelectTrigger>
                      <SelectContent>
                        {["Marketing & Agency","E-commerce","SaaS / Tech","Consulting","Creative & Design","Hospitality","Manufacturing","Healthcare","Education","Other"].map((c) => (
                          <SelectItem key={c} value={c}>{c}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-[13px] font-medium">Employees</Label>
                    <Select value={form.employees} onValueChange={(v) => update("employees", v)}>
                      <SelectTrigger data-testid="onb-employees"><SelectValue placeholder="Team size" /></SelectTrigger>
                      <SelectContent>
                        {["1","2-5","6-15","16-50","50+"].map((e) => (
                          <SelectItem key={e} value={e}>{e}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="ws" className="text-[13px] font-medium">Website (optional)</Label>
                    <Input id="ws" data-testid="onb-website" value={form.website} onChange={(e) => update("website", e.target.value)} placeholder="https://" />
                  </div>
                </div>
              </div>
              <Nav onPrev={prev} onNext={next} disabled={!form.company_name} />
            </div>
          )}

          {step === 3 && (
            <div>
              <p className="zy-eyebrow mb-3">First steps</p>
              <h2 className="text-[26px] font-bold tracking-tight">What would you like to do first?</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-6">
                {FIRST_ACTIONS.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => update("first_action", a.id)}
                    data-testid={`onb-first-${a.id}`}
                    className={`p-4 rounded-lg border text-left transition-all flex items-start gap-3 ${
                      form.first_action === a.id ? "border-[#1A4FFF] shadow-[0_8px_24px_-16px_rgba(26,79,255,0.45)]" : "border-[#eee] hover:border-[#bcd]"
                    }`}
                  >
                    <span className="zy-domain-icon shrink-0" style={{ width: 36, height: 36, marginBottom: 0 }}>
                      <a.icon size={18} />
                    </span>
                    <span className="text-[14.5px] font-medium">{a.label}</span>
                    {form.first_action === a.id && <Check className="ml-auto" size={18} style={{ color: "#1A4FFF" }} />}
                  </button>
                ))}
              </div>
              <Nav onPrev={prev} onNext={next} />
            </div>
          )}

          {step === 4 && (
            <div className="text-center">
              <div className="zy-domain-icon mx-auto" style={{ width: 56, height: 56 }}>
                <Sparkles size={24} />
              </div>
              <h2 className="text-[26px] font-bold tracking-tight mt-5">Meet Zynthoro Assist</h2>
              <p className="text-[15px] text-[#555] mt-3 max-w-md mx-auto">
                Zynthoro Assist is your AI guide — always available in the bottom right corner.
              </p>
              <div className="mt-7 flex flex-col sm:flex-row gap-3 justify-center">
                <button onClick={next} className="zy-btn-primary" data-testid="onb-guide-me">
                  Guide me
                </button>
                <button onClick={next} className="zy-btn-outline" data-testid="onb-explore">
                  I&apos;ll explore myself
                </button>
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="text-center">
              <div className="mx-auto w-14 h-14 rounded-full flex items-center justify-center" style={{ background: "rgba(212,175,55,0.16)", color: "#8a6e1d" }}>
                <Check size={28} />
              </div>
              <h2 className="text-[28px] font-bold tracking-tight mt-5">Your workspace is ready!</h2>
              <p className="text-[15px] text-[#555] mt-3 max-w-md mx-auto">
                You&apos;re on the <b>{user?.subscription_plan || "Presale"}</b> plan. All 12 domains are available from your sidebar.
              </p>
              <Nav onPrev={prev} onNext={next} nextLabel="Go to dashboard" />
            </div>
          )}

          {step === 6 && (
            <div className="text-center">
              <Building2 size={28} style={{ color: "#1A4FFF" }} className="mx-auto" />
              <h2 className="text-[24px] font-bold mt-4">One moment…</h2>
              <p className="text-[14px] text-[#555] mt-2">Saving your workspace.</p>
              <button onClick={finish} disabled={submitting} className="zy-btn-primary mt-6 disabled:opacity-70" data-testid="onb-finish">
                {submitting ? "Finishing…" : "Open my dashboard"}
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function Nav({ onPrev, onNext, disabled, nextLabel = "Continue" }) {
  return (
    <div className="mt-8 flex items-center justify-between">
      <button onClick={onPrev} className="text-[14px] font-medium text-[#555] hover:text-[#1A4FFF] inline-flex items-center gap-1.5">
        <ArrowLeft size={16} /> Back
      </button>
      <button onClick={onNext} disabled={disabled} className="zy-btn-primary disabled:opacity-50" data-testid="onb-next">
        {nextLabel} <ArrowRight size={16} />
      </button>
    </div>
  );
}
