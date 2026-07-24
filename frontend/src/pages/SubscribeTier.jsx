import { useEffect, useState } from "react";
import axios from "axios";
import { Link, Navigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, ArrowLeft, Loader2, ShieldCheck, Check, Tag, X } from "lucide-react";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import { ZyLogo } from "@/components/ZyLogo";

const WAIVER_TEXT =
  "Ik ga akkoord met onmiddellijke uitvoering van de overeenkomst en doe uitdrukkelijk afstand van mijn recht op ontbinding binnen de wettelijke bedenktijd van 14 dagen (art. 6:230p BW).";

const BILLING_LABEL = {
  lifetime: "Eenmalig · levenslange toegang",
  monthly: "€ per maand · opzegbaar",
  one_time_week: "Eenmalig · 7 dagen geldig",
  one_time_month: "Eenmalig · 30 dagen geldig",
};

const FEATURE_MATRIX = {
  kickstart_1: [
    "AI Assistenten (Zyntha, Thoro, Zyona) — 50 credits/mnd",
    "Planning & Time Tracking (basis)",
    "Communicatie module (basis)",
    "Canva Studio",
    "1 workspace · 1 gebruiker",
  ],
  kickstart_2: [
    "Alles uit Kickstart 1 — 150 credits/mnd",
    "Finance & Facturatie (basis)",
    "Sales module (basis)",
    "AI foto/video suite",
    "1 workspace · 1 gebruiker",
  ],
  kickstart_3: [
    "Alles uit Kickstart 2 — 300 credits/mnd",
    "Volledige Time Tracking & Sales",
    "Boekhouding & Operations (basis)",
    "Projectmanagement (basis)",
    "Marketing & Content (basis)",
    "1 workspace · 2 gebruikers",
  ],
  compleet: [
    "Onbeperkte AI credits",
    "Onbeperkt Social posts",
    "Tools: aliassen, document upload, voice input",
    "Volledige Planning & Time Tracking",
    "Extra workspace",
    "Maandelijks opzegbaar",
  ],
  ai_social_week: [
    "30 AI credits — 7 dagen geldig",
    "Social posts top-up",
    "Zyntha, Thoro, Zyona toegang",
    "Geen extra Tools",
  ],
  ai_social_month: [
    "150 AI credits — 30 dagen geldig",
    "Social posts top-up",
    "Zyntha, Thoro, Zyona toegang",
    "Geen extra Tools",
  ],
};

export default function SubscribeTier() {
  const { tierKey } = useParams();
  const { user, loading } = useAuth();
  const [tier, setTier] = useState(null);
  const [tierError, setTierError] = useState(null);
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  // Promo code state
  const [promoInput, setPromoInput] = useState("");
  const [promoApplying, setPromoApplying] = useState(false);
  const [promo, setPromo] = useState(null);       // { code, discount_eur, discounted_total_eur, percent_off, amount_off_eur }
  const [promoError, setPromoError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/tier/catalog`);
        const found = data.plans.find((p) => p.tier_key === tierKey);
        if (!found) {
          setTierError("Onbekende tier.");
          return;
        }
        setTier(found);
      } catch {
        setTierError("Kon het aanbod niet laden. Probeer opnieuw.");
      }
    })();
  }, [tierKey]);

  if (loading || (!tier && !tierError)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <Loader2 className="animate-spin" style={{ color: "#1A4FFF" }} />
      </div>
    );
  }
  if (!user) {
    return <Navigate to={`/signup?return=${encodeURIComponent(`/subscribe/${tierKey}`)}`} replace />;
  }
  if (tierError) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-white gap-4 p-6 text-center">
        <p className="text-[15px] text-[#555]">{tierError}</p>
        <Link to="/" className="zy-btn-outline">Terug naar home</Link>
      </div>
    );
  }

  const startCheckout = async () => {
    if (!consent) {
      toast.error("Bevestig eerst de afstand van je herroepingsrecht.");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/checkout/tier/session`, {
        tier_key: tier.tier_key,
        origin_url: window.location.origin,
        consent_waiver: true,
        promo_code: promo ? promo.code : null,
      });
      window.location.href = data.url;
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Kon checkout niet starten.");
      setSubmitting(false);
    }
  };

  const applyPromo = async (overrideCode) => {
    const code = ((overrideCode ?? promoInput) || "").trim().toUpperCase();
    if (!code) return;
    setPromoApplying(true);
    setPromoError("");
    try {
      const { data } = await axios.post(`${API}/checkout/tier/validate-promo`, {
        tier_key: tier.tier_key,
        code,
      });
      setPromo({
        code: data.code,
        percent_off: data.percent_off,
        amount_off_eur: data.amount_off_eur,
        discount_eur: data.discount_eur,
        discounted_total_eur: data.discounted_total_eur,
      });
    } catch (e) {
      setPromo(null);
      setPromoError(formatApiError(e?.response?.data?.detail) || "Ongeldige promocode.");
    }
    setPromoApplying(false);
  };

  const applySuggestedPromo = (code) => {
    setPromoInput(code);
    setPromoError("");
    applyPromo(code);
  };

  const removePromo = () => {
    setPromo(null);
    setPromoInput("");
    setPromoError("");
  };

  const features = FEATURE_MATRIX[tier.tier_key] || [];

  return (
    <div className="min-h-screen flex flex-col bg-white" data-testid={`subscribe-tier-${tier.tier_key}`}>
      <header className="px-6 sm:px-10 py-6 border-b border-[#eee] flex items-center justify-between">
        <Link to="/" className="inline-flex items-center" style={{ background: "#0A1628", padding: "8px 14px", borderRadius: 8 }}>
          <ZyLogo size={18} />
        </Link>
        <Link to="/#kickstart" className="text-[13px] text-[#666] hover:text-[#1A4FFF] inline-flex items-center gap-1.5">
          <ArrowLeft size={14} /> Alle abonnementen
        </Link>
      </header>

      <main className="flex-1 flex items-start justify-center px-6 py-12 sm:py-16">
        <div className="w-full max-w-[620px]">
          <p className="zy-eyebrow mb-3">Subscribe · {tier.label}</p>

          <h1 className="text-[30px] sm:text-[34px] font-bold tracking-tight leading-tight">
            {tier.label}
          </h1>
          <p className="text-[16px] text-[#555] mt-3 leading-relaxed">{tier.description}</p>

          <div className="mt-8 p-6 rounded-2xl border border-[#eee] bg-white">
            <div className="flex items-baseline gap-2">
              <span className="text-[36px] font-bold tracking-tight">€{tier.amount_eur}</span>
              <span className="text-[15px] text-[#666]">
                {tier.billing === "monthly" ? "/maand" : ""}
              </span>
            </div>
            <p className="text-[13px] text-[#666] mt-1.5">{BILLING_LABEL[tier.billing]}</p>

            <ul className="mt-6 space-y-2.5">
              {features.map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-[14px] text-[#333]">
                  <Check size={15} className="mt-1 shrink-0" style={{ color: "#1A4FFF" }} />
                  <span>{f}</span>
                </li>
              ))}
            </ul>

            {/* Promo code ----------------------------------------------- */}
            <div className="mt-7">
              {!promo ? (
                <>
                  <label className="block text-[11.5px] uppercase font-bold text-[#888] tracking-wider mb-1.5">
                    Promotiecode (optioneel)
                  </label>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Tag size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#999] pointer-events-none" />
                      <input
                        value={promoInput}
                        onChange={(e) => { setPromoInput(e.target.value.toUpperCase()); setPromoError(""); }}
                        onKeyDown={(e) => e.key === "Enter" && applyPromo()}
                        placeholder="Bijv. PH2026"
                        maxLength={60}
                        className="w-full pl-9 pr-3 py-2.5 border border-[#e5e5e5] rounded-lg text-[14px] outline-none focus:border-[#1A4FFF] focus:ring-2 focus:ring-[#1A4FFF]/10 uppercase tracking-wider"
                        data-testid="promo-code-input"
                      />
                    </div>
                    <button
                      onClick={applyPromo}
                      disabled={!promoInput.trim() || promoApplying}
                      className="zy-btn-outline text-[13px] px-4 disabled:opacity-50"
                      data-testid="promo-code-apply-btn"
                    >
                      {promoApplying ? <Loader2 size={13} className="animate-spin" /> : "Toepassen"}
                    </button>
                  </div>
                  {promoError && (
                    <p className="mt-2 text-[12.5px]" style={{ color: "#c00" }} data-testid="promo-code-error">
                      {promoError}
                    </p>
                  )}

                  {/* Suggested promo hint — one-click apply. Currently
                      featured code for TAAFT reviewers / launch traffic. */}
                  <button
                    type="button"
                    onClick={() => applySuggestedPromo("TAAFT10")}
                    disabled={promoApplying}
                    className="mt-2.5 inline-flex items-center gap-1.5 text-[12.5px] text-[#1A4FFF] hover:underline disabled:opacity-50"
                    data-testid="promo-code-suggested-taaft10"
                    aria-label="Apply promo code TAAFT10"
                  >
                    <Tag size={11} />
                    <span>Try code:</span>
                    <span className="font-mono font-semibold tracking-wider">TAAFT10</span>
                  </button>
                </>
              ) : (
                <div
                  className="rounded-lg border p-3 flex items-start justify-between gap-3"
                  style={{ borderColor: "#16a34a", background: "rgba(34,197,94,0.06)" }}
                  data-testid="promo-code-applied"
                >
                  <div className="flex items-start gap-2">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0" style={{ background: "#16a34a", color: "#fff" }}>
                      <Check size={15} />
                    </div>
                    <div className="text-[12.5px]">
                      <div className="font-semibold text-[#0A1628]">
                        Code <span className="font-mono">{promo.code}</span> toegepast
                      </div>
                      <div className="text-[#555]">
                        {promo.percent_off ? `${promo.percent_off}% korting` :
                         promo.amount_off_eur ? `€${promo.amount_off_eur.toFixed(2)} korting` : "Korting toegepast"}
                        {" · "}
                        Nieuwe totaal: <b>€{promo.discounted_total_eur.toFixed(2)}</b>
                        {" "}
                        <span className="text-[#888] line-through">€{tier.amount_eur}</span>
                      </div>
                    </div>
                  </div>
                  <button onClick={removePromo} className="text-[#888] hover:text-[#c00]" data-testid="promo-code-remove-btn" aria-label="Verwijder promocode">
                    <X size={14} />
                  </button>
                </div>
              )}
            </div>

            {/* Herroepingsrecht — mandatory, unchecked by default */}
            <label
              className="mt-7 flex items-start gap-3 p-4 rounded-xl border cursor-pointer select-none transition-colors"
              style={{ borderColor: consent ? "#1A4FFF" : "#e5e5e5", background: consent ? "#F5F8FF" : "#FAFAFA" }}
              data-testid="waiver-label"
            >
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                data-testid="waiver-checkbox"
                className="mt-0.5 shrink-0 w-4 h-4 accent-[#1A4FFF]"
              />
              <span className="text-[12.5px] leading-relaxed text-[#333]">
                <b>Herroepingsrecht (verplicht):</b>{" "}
                {WAIVER_TEXT}
              </span>
            </label>

            <button
              onClick={startCheckout}
              disabled={!consent || submitting}
              data-testid="start-tier-checkout"
              className="zy-btn-primary mt-6 w-full disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? (
                <><Loader2 size={15} className="animate-spin" /> Redirecting to Stripe…</>
              ) : (
                <>Verder naar veilige betaling <ArrowRight size={15} /></>
              )}
            </button>
          </div>

          <p className="text-[12px] text-[#888] mt-6 leading-relaxed">
            <ShieldCheck size={11} className="inline mr-1 -mt-0.5" />
            Betaling wordt veilig afgehandeld door Stripe. Je kaartgegevens komen nooit op onze servers.
            {" "}Zie ook onze{" "}
            <Link to="/legal/terms-of-service" className="underline">Algemene voorwaarden</Link>.
          </p>
        </div>
      </main>
    </div>
  );
}
