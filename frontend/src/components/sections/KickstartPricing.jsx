import { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { ArrowRight, Check } from "lucide-react";
import { API } from "@/contexts/AuthContext";

const KICKSTART_HIGHLIGHTS = {
  kickstart_1: [
    "AI Assistenten · 50 credits/mnd",
    "Planning & Time Tracking",
    "Communicatie module",
    "Canva Studio",
  ],
  kickstart_2: [
    "Alles uit K1 · 150 credits/mnd",
    "Finance & Facturatie",
    "Sales module",
    "AI foto/video suite",
  ],
  kickstart_3: [
    "Alles uit K2 · 300 credits/mnd",
    "Accounting & Operations",
    "Projectmanagement",
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
          <p className="zy-eyebrow">Kickstart · Levenslang</p>
          <h2 className="zy-h2 mt-3">
            Betaal één keer. Gebruik Zynthoro voor altijd.
          </h2>
          <p className="text-[15.5px] text-[#555] mt-4 leading-relaxed max-w-2xl">
            Onze lifetime deals geven je toegang tot een groeiende AI-ERP voor een fractie van de maandprijs.
            Herroepingsrecht wettelijk uitgesloten na directe activatie.
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
                  Populairste keuze
                </span>
              )}
              <p className="text-[13px] font-semibold uppercase tracking-wider text-[#666]">{p.label}</p>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-[38px] font-bold tracking-tight">€{p.amount_eur}</span>
                <span className="text-[13.5px] text-[#666]">eenmalig</span>
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
                Kies {p.label} <ArrowRight size={14} />
              </Link>
            </div>
          ))}
        </div>

        <p className="mt-6 text-[12px] text-[#888]">
          Kickstart plans zijn levenslange licenties. Kickstart 3 evenaart nooit een volledig Starter-abonnement (€499/maand) — voor volledige functionaliteit kies je{" "}
          <a href="#pricing" className="underline">Starter of hoger</a>.
        </p>
      </div>
    </section>
  );
}
