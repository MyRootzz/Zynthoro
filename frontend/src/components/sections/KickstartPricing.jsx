import { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { ArrowRight, Check, Infinity as InfinityIcon, Zap, Sparkles } from "lucide-react";
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

const TOPUP_HIGHLIGHTS = {
  compleet: [
    "Onbeperkte AI credits",
    "Onbeperkt Social posts",
    "Document upload & voice input",
    "Extra workspace",
  ],
  ai_social_week: [
    "30 AI credits · 7 dagen",
    "Social posts top-up",
    "Zyntha, Thoro, Zyona",
  ],
  ai_social_month: [
    "150 AI credits · 30 dagen",
    "Social posts top-up",
    "Zyntha, Thoro, Zyona",
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
  const compleet = plans.find((p) => p.tier_key === "compleet");
  const week = plans.find((p) => p.tier_key === "ai_social_week");
  const month = plans.find((p) => p.tier_key === "ai_social_month");

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

        {/* Compleet + top-ups */}
        <div className="mt-20">
          <p className="zy-eyebrow">Add-ons · Maandelijks & top-ups</p>
          <h3 className="text-[24px] font-bold tracking-tight mt-3">Meer AI nodig? Combineer een top-up of ga onbeperkt.</h3>
        </div>

        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Compleet */}
          {compleet && (
            <div
              className="rounded-2xl p-7 text-white flex flex-col"
              style={{ background: "linear-gradient(135deg, #0A1628 0%, #1A4FFF 130%)" }}
              data-testid="compleet-card"
            >
              <div className="flex items-center gap-2">
                <InfinityIcon size={16} />
                <p className="text-[13px] font-semibold uppercase tracking-wider">Compleet</p>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-[36px] font-bold tracking-tight">€{compleet.amount_eur}</span>
                <span className="text-[13.5px] opacity-80">/maand</span>
              </div>
              <p className="text-[13px] opacity-80 mt-1">Zelf-verlengend · opzegbaar</p>

              <ul className="mt-6 space-y-2.5 flex-1">
                {(TOPUP_HIGHLIGHTS.compleet || []).map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13.5px]">
                    <Check size={14} className="mt-1 shrink-0" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>

              <Link
                to="/subscribe/compleet"
                data-testid="compleet-cta"
                className="mt-8 w-full inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-[13.5px] font-semibold bg-white text-[#0A1628] hover:bg-[#F5F8FF]"
              >
                Start Compleet <ArrowRight size={14} />
              </Link>
            </div>
          )}

          {week && (
            <div className="bg-white border border-[#eee] rounded-2xl p-7 flex flex-col" data-testid="week-card">
              <div className="flex items-center gap-2 text-[#1A4FFF]">
                <Zap size={16} />
                <p className="text-[13px] font-semibold uppercase tracking-wider">1 week</p>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-[36px] font-bold tracking-tight">€{week.amount_eur}</span>
                <span className="text-[13.5px] text-[#666]">eenmalig</span>
              </div>
              <p className="text-[13px] text-[#666] mt-1">{week.tagline}</p>
              <ul className="mt-6 space-y-2.5 flex-1">
                {(TOPUP_HIGHLIGHTS.ai_social_week || []).map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13.5px] text-[#333]">
                    <Check size={14} className="mt-1 shrink-0" style={{ color: "#1A4FFF" }} />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Link
                to="/subscribe/ai_social_week"
                data-testid="week-cta"
                className="zy-btn-outline mt-8 w-full justify-center"
              >
                Kies 1 week <ArrowRight size={14} />
              </Link>
            </div>
          )}

          {month && (
            <div className="bg-white border border-[#eee] rounded-2xl p-7 flex flex-col" data-testid="month-card">
              <div className="flex items-center gap-2 text-[#1A4FFF]">
                <Sparkles size={16} />
                <p className="text-[13px] font-semibold uppercase tracking-wider">1 maand</p>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-[36px] font-bold tracking-tight">€{month.amount_eur}</span>
                <span className="text-[13.5px] text-[#666]">eenmalig</span>
              </div>
              <p className="text-[13px] text-[#666] mt-1">{month.tagline}</p>
              <ul className="mt-6 space-y-2.5 flex-1">
                {(TOPUP_HIGHLIGHTS.ai_social_month || []).map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13.5px] text-[#333]">
                    <Check size={14} className="mt-1 shrink-0" style={{ color: "#1A4FFF" }} />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Link
                to="/subscribe/ai_social_month"
                data-testid="month-cta"
                className="zy-btn-outline mt-8 w-full justify-center"
              >
                Kies 1 maand <ArrowRight size={14} />
              </Link>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
