import { useEffect, useState } from "react";
import axios from "axios";
import { Link, Navigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, ArrowLeft, Loader2, ShieldCheck, Check } from "lucide-react";
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
      });
      window.location.href = data.url;
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Kon checkout niet starten.");
      setSubmitting(false);
    }
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
