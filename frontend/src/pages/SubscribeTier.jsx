import { useEffect, useState } from "react";
import axios from "axios";
import { Link, Navigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, ArrowLeft, Loader2, ShieldCheck, Check, Tag, X } from "lucide-react";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import { ZyLogo } from "@/components/ZyLogo";

const WAIVER_TEXT =
  "I agree to the immediate performance of the agreement and expressly waive my right to withdraw within the statutory 14-day cooling-off period (art. 6:230p Dutch Civil Code).";

const BILLING_LABEL = {
  lifetime: "One-time · lifetime access",
  monthly: "€ per month · cancel anytime",
  one_time_week: "One-time · valid for 7 days",
  one_time_month: "One-time · valid for 30 days",
};

const FEATURE_MATRIX = {
  kickstart_1: [
    "AI Assistants (Zyntha, Thoro, Zyona) — 50 credits/month",
    "Planning & Time Tracking (basic)",
    "Communication module (basic)",
    "Canva Studio",
    "1 workspace · 1 user",
  ],
  kickstart_2: [
    "Everything in Kickstart 1 — 150 credits/month",
    "Finance & Invoicing (basic)",
    "Sales module (basic)",
    "AI photo/video suite",
    "1 workspace · 1 user",
  ],
  kickstart_3: [
    "Everything in Kickstart 2 — 300 credits/month",
    "Full Time Tracking & Sales",
    "Accounting & Operations (basic)",
    "Project management (basic)",
    "Marketing & Content (basic)",
    "1 workspace · 2 users",
  ],
  compleet: [
    "Unlimited AI credits",
    "Unlimited social posts",
    "Tools: aliases, document upload, voice input",
    "Full Planning & Time Tracking",
    "Extra workspace",
    "Cancel monthly",
  ],
  ai_social_week: [
    "30 AI credits — valid for 7 days",
    "Social posts top-up",
    "Access to Zyntha, Thoro, Zyona",
    "No extra Tools",
  ],
  ai_social_month: [
    "150 AI credits — valid for 30 days",
    "Social posts top-up",
    "Access to Zyntha, Thoro, Zyona",
    "No extra Tools",
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
          setTierError("Unknown tier.");
          return;
        }
        setTier(found);
      } catch {
        setTierError("Couldn't load pricing. Please try again.");
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
        <Link to="/" className="zy-btn-outline">Back to home</Link>
      </div>
    );
  }

  const startCheckout = async () => {
    if (!consent) {
      toast.error("Please confirm the waiver of your withdrawal right first.");
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
      toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't start checkout.");
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
        first_time_only: data.first_time_only,
      });
    } catch (e) {
      setPromo(null);
      setPromoError(formatApiError(e?.response?.data?.detail) || "Invalid promo code.");
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
          <ArrowLeft size={14} /> All plans
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
                {tier.billing === "monthly" ? "/month" : ""}
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
                    Promo code (optional)
                  </label>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Tag size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#999] pointer-events-none" />
                      <input
                        value={promoInput}
                        onChange={(e) => { setPromoInput(e.target.value.toUpperCase()); setPromoError(""); }}
                        onKeyDown={(e) => e.key === "Enter" && applyPromo()}
                        placeholder="e.g. PH2026"
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
                      {promoApplying ? <Loader2 size={13} className="animate-spin" /> : "Apply"}
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
                        Code <span className="font-mono">{promo.code}</span> applied
                      </div>
                      <div className="text-[#555]">
                        {promo.percent_off ? `${promo.percent_off}% off` :
                         promo.amount_off_eur ? `€${promo.amount_off_eur.toFixed(2)} off` : "Discount applied"}
                        {" · "}
                        New total: <b>€{promo.discounted_total_eur.toFixed(2)}</b>
                        {" "}
                        <span className="text-[#888] line-through">€{tier.amount_eur}</span>
                      </div>
                      {promo.first_time_only && (
                        <div
                          className="mt-1 text-[12px] text-[#B45309]"
                          data-testid="promo-first-time-only-warning"
                        >
                          First-time customers only — Stripe rejects this code if you already have a prior purchase on this account.
                        </div>
                      )}
                    </div>
                  </div>
                  <button onClick={removePromo} className="text-[#888] hover:text-[#c00]" data-testid="promo-code-remove-btn" aria-label="Remove promo code">
                    <X size={14} />
                  </button>
                </div>
              )}
            </div>

            {/* Withdrawal-right waiver — mandatory, unchecked by default */}
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
                <b>Right of withdrawal (required):</b>{" "}
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
                <>Continue to secure payment <ArrowRight size={15} /></>
              )}
            </button>
          </div>

          <p className="text-[12px] text-[#888] mt-6 leading-relaxed">
            <ShieldCheck size={11} className="inline mr-1 -mt-0.5" />
            Payment is handled securely by Stripe. Your card details never touch our servers.
            {" "}See also our{" "}
            <Link to="/legal/terms-of-service" className="underline">Terms of Service</Link>.
          </p>
        </div>
      </main>
    </div>
  );
}
