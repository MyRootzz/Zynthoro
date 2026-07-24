import { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { ArrowRight, Check } from "lucide-react";
import { API } from "@/contexts/AuthContext";

const KICKSTART_HIGHLIGHTS = {
  kickstart_1: [
    "AI Assistants · 50 credits/month",
    "Planning & Time Tracking",
    "Communication module",
    "Canva Studio",
  ],
  kickstart_2: [
    "Everything in K1 · 150 credits/month",
    "Finance & Invoicing",
    "Sales module",
    "AI photo/video suite",
  ],
  kickstart_3: [
    "Everything in K2 · 300 credits/month",
    "Accounting & Operations",
    "Project management",
    "Marketing & Content",
  ],
};

export default function KickstartPricing() {
  const [plans, setPlans] = useState([]);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/tier/catalog`);
        setPlans(data.plans);
      } catch {
        setPlans([]);
      }
    })();
  }, []);

  const kick = plans.filter((p) => p.tier_key.startsWith("kickstart_"));

  return (
    <section id="kickstart" className="py-24 border-t border-[#eee]" data-testid="kickstart-section">
      <div className="zy-container">
        {/* Header */}
        <div className="max-w-3xl">
          <p className="zy-eyebrow">Kickstart · Lifetime</p>
          <h2 className="zy-h2 mt-3">
            Pay once. Use Zynthoro forever.
          </h2>
          <p className="text-[15.5px] text-[#555] mt-4 leading-relaxed max-w-2xl">
            Our lifetime deals give you access to a growing AI-ERP for a fraction of the monthly price.
            Right of withdrawal legally excluded after immediate activation.
          </p>
        </div>

        {/* Kickstart 3 cards */}
        <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-5">
          {kick.map((p) => (
            <div
              key={p.tier_key}
              className="relative bg-white border rounded-2xl p-7 flex flex-col transition-all hover:border-[#1A4FFF]"
              style={{
                borderColor: p.tier_key === "kickstart_3" ? "#1A4FFF" : "#eee",
                boxShadow: p.tier_key === "kickstart_3" ? "0 20px 60px -30px rgba(26,79,255,0.35)" : "none",
              }}
              data-testid={`kickstart-card-${p.tier_key}`}
            >
              {p.tier_key === "kickstart_3" && (
                <span
                  className="absolute -top-3 left-6 px-3 py-1 rounded-full text-[11px] font-semibold uppercase tracking-wider"
                  style={{ background: "#1A4FFF", color: "white" }}
                >
                  Most popular
                </span>
              )}
              <p className="text-[13px] font-semibold uppercase tracking-wider text-[#666]">{p.label}</p>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-[38px] font-bold tracking-tight">€{p.amount_eur}</span>
                <span className="text-[13.5px] text-[#666]">one-time</span>
              </div>
              <p className="text-[13px] text-[#666] mt-1">{p.tagline}</p>

              <ul className="mt-6 space-y-2.5 flex-1">
                {(KICKSTART_HIGHLIGHTS[p.tier_key] || []).map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13.5px] text-[#333]">
                    <Check size={14} className="mt-1 shrink-0" style={{ color: "#1A4FFF" }} />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>

              <Link
                to={`/subscribe/${p.tier_key}`}
                data-testid={`kickstart-cta-${p.tier_key}`}
                className={p.tier_key === "kickstart_3" ? "zy-btn-primary mt-8 w-full justify-center" : "zy-btn-outline mt-8 w-full justify-center"}
              >
                Choose {p.label} <ArrowRight size={14} />
              </Link>
            </div>
          ))}
        </div>

        <p className="mt-6 text-[12px] text-[#888]">
          Kickstart plans are lifetime licenses. Kickstart 3 will never match a full Starter subscription (€499/month) — for full functionality choose{" "}
          <a href="#pricing" className="underline">Starter or higher</a>.
        </p>
      </div>
    </section>
  );
}
