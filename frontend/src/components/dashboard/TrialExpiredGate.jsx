import { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { CheckCircle2, Clock, LogOut, ArrowRight, ShieldCheck } from "lucide-react";
import { API, useAuth } from "@/contexts/AuthContext";

const TIER_TESTIMONIALS = {
  kickstart_1: "AI assistants + Planning + Time Tracking + Communication",
  kickstart_2: "Everything in K1 + Finance + Sales + AI photo/video",
  kickstart_3: "Everything in K2 + Accounting + Projects + Marketing",
};

// Full-page hard-block shown to trial users whose 24h clock has expired.
// Renders instead of the entire dashboard — user cannot continue until
// they upgrade or log out.
export default function TrialExpiredGate() {
  const { user, logout } = useAuth();
  const [plans, setPlans] = useState([]);

  useEffect(() => {
    axios
      .get(`${API}/tier/catalog`)
      .then(({ data }) => setPlans(data.plans || []))
      .catch(() => setPlans([]));
  }, []);

  const kick = plans.filter((p) => (p.tier_key || "").startsWith("kickstart_"));

  return (
    <div
      data-testid="trial-expired-gate"
      className="min-h-screen bg-gradient-to-br from-[#0A1628] via-[#0A1628] to-[#1A4FFF]/40 text-white"
    >
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-14 sm:py-20">
        <div className="flex items-center justify-between mb-10">
          <div className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-md flex items-center justify-center text-[13px] font-bold"
              style={{ background: "var(--zy-gold)", color: "#0A1628" }}
            >
              Z
            </div>
            <span className="font-bold tracking-wider">ZYNTHORO</span>
          </div>
          <button
            type="button"
            onClick={logout}
            data-testid="trial-expired-logout"
            className="inline-flex items-center gap-1.5 text-[13px] text-white/70 hover:text-white transition-colors"
          >
            <LogOut size={14} />
            Log out
          </button>
        </div>

        <div className="mb-10">
          <p
            className="uppercase tracking-[0.18em] text-[12px] mb-3"
            style={{ color: "var(--zy-gold)" }}
          >
            <Clock size={12} className="inline mr-1 -mt-0.5" /> Trial expired
          </p>
          <h1 className="text-3xl sm:text-5xl font-bold tracking-tight leading-[1.1]">
            Your 24-hour free trial has ended.
            <br />
            <span className="text-white/75">Pick a Kickstart tier to keep going.</span>
          </h1>
          <p className="mt-5 text-white/70 text-[15.5px] max-w-2xl leading-relaxed">
            Hi {user?.first_name || "there"} — the trial gave you a taste of the four AI assistants. To unlock the full Zynthoro platform (Finance, Sales, Projects, HR, Accounting, and more), grab a lifetime Kickstart license below. Pay once, use forever.
          </p>
        </div>

        {/* Tier picker */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {kick.length === 0 ? (
            <div className="col-span-full text-white/60 text-[14px]">
              Loading plans…
            </div>
          ) : (
            kick.map((p) => (
              <Link
                key={p.tier_key}
                to={`/subscribe/${p.tier_key}`}
                data-testid={`trial-expired-tier-${p.tier_key}`}
                className={`group relative rounded-2xl p-6 flex flex-col transition-all bg-white/[0.06] hover:bg-white/[0.1] backdrop-blur border ${
                  p.tier_key === "kickstart_3"
                    ? "border-[var(--zy-gold)]/50"
                    : "border-white/10 hover:border-white/25"
                }`}
              >
                {p.tier_key === "kickstart_3" && (
                  <span
                    className="absolute -top-2.5 left-5 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider"
                    style={{ background: "var(--zy-gold)", color: "#0A1628" }}
                  >
                    Most popular
                  </span>
                )}
                <p className="text-[11px] font-semibold uppercase tracking-wider text-white/50">
                  {p.label}
                </p>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-[32px] font-bold tracking-tight text-white">
                    €{p.amount_eur}
                  </span>
                  <span className="text-[12px] text-white/50">one-time</span>
                </div>
                <p className="mt-3 text-[13px] text-white/70 leading-relaxed">
                  {TIER_TESTIMONIALS[p.tier_key] || p.description}
                </p>
                <div className="mt-auto pt-5 inline-flex items-center gap-1.5 text-[13px] font-semibold text-[var(--zy-gold)]">
                  Choose {p.label}
                  <ArrowRight
                    size={13}
                    className="transition-transform duration-300 group-hover:translate-x-1"
                  />
                </div>
              </Link>
            ))
          )}
        </div>

        {/* Trust bar */}
        <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-2 text-[12.5px] text-white/50">
          <span className="inline-flex items-center gap-1.5">
            <CheckCircle2 size={13} /> Lifetime access — pay once
          </span>
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck size={13} /> EU-hosted · GDPR-native
          </span>
          <span className="inline-flex items-center gap-1.5">
            <CheckCircle2 size={13} /> Cancel anytime
          </span>
        </div>

        <p className="mt-8 text-[12.5px] text-white/45">
          Prefer a monthly subscription instead?{" "}
          <a
            href="/#pricing"
            className="text-white/70 underline hover:text-white"
          >
            See Starter / Enterprise plans
          </a>
          .
        </p>
      </div>
    </div>
  );
}
