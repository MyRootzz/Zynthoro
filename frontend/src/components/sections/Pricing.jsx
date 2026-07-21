import { Check, ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { HOME } from "@/constants/testIds";
import { usePresaleDialog } from "@/components/sections/PresaleDialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const plans = [
  {
    name: "Starter",
    plan_key: "Starter",
    price: "€499",
    price_annual: "€4,990",
    suffix: "/mo",
    suffix_annual: "/yr",
    desc: "Basic modules for solo founders just getting started.",
    features: [
      "Basic planning & time tracking",
      "Basic content & communication",
      "1 company workspace",
      "1 user · 1 email · 3 aliases",
      "No ERP",
    ],
    cta: "Subscribe to Starter",
  },
  {
    name: "Creator",
    plan_key: "Creator",
    price: "€699",
    price_annual: "€6,990",
    suffix: "/mo",
    suffix_annual: "/yr",
    desc: "Everything in Starter, plus the full AI creative suite.",
    features: [
      "AI video suite",
      "AI photo suite",
      "AI funnels & landing pages",
      "1 company workspace",
      "3 users · 3 emails · unlimited aliases",
      "No ERP",
    ],
    cta: "Subscribe to Creator",
  },
  {
    name: "Business",
    plan_key: "Business",
    price: "€899",
    price_annual: "€8,990",
    suffix: "/mo",
    suffix_annual: "/yr",
    desc: "More modules for growing SMEs and entrepreneurs.",
    features: [
      "Everything in Creator",
      "Full time tracking & sales",
      "Basic accounting & operations",
      "3 company workspaces",
      "10 users · unlimited emails",
      "No ERP",
    ],
    cta: "Subscribe to Business",
    popular: true,
  },
  {
    name: "Agency",
    plan_key: "Agency",
    price: "€1,199",
    price_annual: "€11,990",
    suffix: "/mo",
    suffix_annual: "/yr",
    desc: "Full non-ERP suite for agencies and multi-client teams.",
    features: [
      "Everything in Business",
      "Full accounting & inventory",
      "Pro project management & marketing",
      "5 company workspaces",
      "25 users · team structures",
      "No ERP",
    ],
    cta: "Subscribe to Agency",
  },
  {
    name: "Enterprise",
    plan_key: "Enterprise Basic",
    price: "from €2,499",
    price_annual: "from €24,990",
    suffix: "/mo",
    suffix_annual: "/yr",
    desc: "All 12 domains, full ERP, unlimited companies.",
    features: [
      "All 12 domains · full ERP",
      "Unlimited users",
      "Unlimited company workspaces",
      "SSO, audit trail, security policies",
      "Dedicated support & onboarding",
    ],
    cta: "Talk to Sales",
    enterprise: true,
  },
];

export default function Pricing() {
  const { openDialog } = usePresaleDialog();
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState({});
  const [annual, setAnnual] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const { data } = await axios.get(`${API}/pricing/catalog`);
        if (!active) return;
        const map = {};
        (data?.plans || []).forEach((p) => { map[p.plan_key] = p.payment_link; });
        setCatalog(map);
      } catch {
        /* graceful: keep CTA as presale */
      }
    })();
    return () => { active = false; };
  }, []);

  const onCta = (plan) => {
    const link = catalog[plan.plan_key];
    if (plan.enterprise) {
      navigate("/#enterprise");
      return;
    }
    if (link) {
      window.location.href = link;
      return;
    }
    // Fallback while catalog is loading
    openDialog();
  };

  return (
    <section id="pricing" data-testid={HOME.pricing} className="zy-section bg-white">
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-10 zy-reveal">
          <p className="zy-eyebrow mb-4">Pricing</p>
          <h2 className="zy-h2">Simple, transparent pricing. No surprises.</h2>
          <p className="zy-body mt-5">
            Founding member pricing locked for life when you join the presale.
          </p>
        </div>

        {/* Monthly / Annual toggle (2 months free on annual) */}
        <div className="flex justify-center mb-10 zy-reveal">
          <div
            role="tablist"
            aria-label="Billing period"
            className="inline-flex items-center gap-1 p-1 rounded-full border border-[#e5e7ee] bg-white shadow-sm"
            data-testid="pricing-billing-toggle"
          >
            <button
              type="button"
              role="tab"
              aria-selected={!annual}
              onClick={() => setAnnual(false)}
              className={`px-4 py-1.5 rounded-full text-[13.5px] font-medium transition-colors ${
                !annual ? "bg-[#1A4FFF] text-white" : "text-[#333] hover:text-black"
              }`}
              data-testid="pricing-toggle-monthly"
            >
              Monthly
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={annual}
              onClick={() => setAnnual(true)}
              className={`px-4 py-1.5 rounded-full text-[13.5px] font-medium transition-colors flex items-center gap-2 ${
                annual ? "bg-[#1A4FFF] text-white" : "text-[#333] hover:text-black"
              }`}
              data-testid="pricing-toggle-annual"
            >
              Annual
              <span
                className={`text-[10.5px] px-1.5 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                  annual ? "bg-white/25 text-white" : "bg-[#E8FFE9] text-[#0F7A2A]"
                }`}
              >
                2 months free
              </span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-5">
          {plans.map((p, i) => (
            <div
              key={p.name}
              data-testid={`pricing-card-${p.name.toLowerCase()}`}
              className={`zy-price-card zy-reveal ${p.popular ? "popular" : ""} ${p.enterprise ? "enterprise" : ""}`}
              style={{ transitionDelay: `${i * 70}ms` }}
            >
              {p.popular && (
                <span
                  className="absolute -top-3 left-6 text-[11px] font-bold tracking-wide uppercase px-3 py-1 rounded-full text-white"
                  style={{ background: "var(--zy-blue)" }}
                >
                  Most Popular
                </span>
              )}
              {p.enterprise && (
                <span
                  className="absolute -top-3 left-6 text-[11px] font-bold tracking-wide uppercase px-3 py-1 rounded-full"
                  style={{ background: "var(--zy-gold)", color: "#1a1300" }}
                >
                  Enterprise
                </span>
              )}

              <h3 className="zy-h3 text-[1.05rem]">{p.name}</h3>
              <div className="mt-3 flex items-baseline gap-1">
                <span className="text-[28px] font-bold tracking-tight text-black" data-testid={`pricing-card-${p.name.toLowerCase()}-price`}>
                  {annual ? (p.price_annual || p.price) : p.price}
                </span>
                <span className="text-[#666] text-[14px]">
                  {annual ? (p.suffix_annual || p.suffix) : p.suffix}
                </span>
              </div>
              <p className="text-[13.5px] text-[#555] mt-2 leading-relaxed min-h-[40px]">{p.desc}</p>

              <ul className="mt-5 space-y-2.5 flex-1">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-[13.5px] text-[#333]">
                    <Check size={14} className="mt-0.5 shrink-0" style={{ color: "var(--zy-blue)" }} />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => onCta(p)}
                className={p.enterprise ? "zy-btn-gold mt-6 w-full" : "zy-btn-primary mt-6 w-full"}
                style={{ fontSize: 14, padding: "12px 18px" }}
                data-testid={`pricing-cta-${p.name.toLowerCase()}`}
              >
                {p.cta}
              </button>
            </div>
          ))}
        </div>

        <div className="mt-12 text-center zy-reveal">
          <a href="#enterprise" className="zy-link">
            See enterprise features <ArrowRight size={16} />
          </a>
        </div>
      </div>
    </section>
  );
}
