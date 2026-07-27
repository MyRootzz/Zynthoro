/**
 * Brief 3-card pricing teaser for the slim homepage.
 * Full tier tables, comparisons, and Enterprise details live at /pricing.
 */
import { Link } from "react-router-dom";
import { ArrowRight, Sparkles, Repeat, Building2 } from "lucide-react";

const CARDS = [
  {
    key: "kickstart",
    icon: Sparkles,
    label: "Kickstart",
    price: "from €79",
    priceSuffix: "lifetime",
    line: "One-time payment. Own it forever. Perfect for early founders.",
    accent: "#1A4FFF",
  },
  {
    key: "subscription",
    icon: Repeat,
    label: "Subscriptions",
    price: "from €24.99",
    priceSuffix: "/ mo",
    line: "Full platform + AI credits. Cancel any time, no lock-in.",
    accent: "#1A4FFF",
    highlight: true,
  },
  {
    key: "enterprise",
    icon: Building2,
    label: "Enterprise",
    price: "Custom",
    priceSuffix: "annual",
    line: "SSO, dedicated support, unlimited seats. Built for teams > 25.",
    accent: "#D4AF37",
  },
];

export default function HomePricingBrief() {
  return (
    <section
      id="pricing"
      data-testid="home-pricing-brief"
      className="zy-section bg-white"
    >
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-12 zy-reveal">
          <p className="zy-eyebrow mb-4">Pricing</p>
          <h2 className="zy-h2">Three ways to buy Zynthoro.</h2>
          <p className="zy-body mt-5">
            Lifetime deals, monthly subscriptions, or Enterprise. No seat fees, no surprises.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {CARDS.map((c, i) => {
            const Icon = c.icon;
            const isHighlight = c.highlight;
            return (
              <article
                key={c.key}
                data-testid={`home-pricing-brief-${c.key}`}
                className={`zy-reveal rounded-2xl p-7 flex flex-col transition-all border ${
                  isHighlight
                    ? "border-[#1A4FFF] bg-[#1A4FFF] text-white shadow-[0_20px_48px_-24px_rgba(26,79,255,0.55)]"
                    : "border-[#0A162814] bg-white text-[#0A1628] hover:shadow-[0_18px_44px_-24px_rgba(10,22,40,0.22)]"
                }`}
                style={{ transitionDelay: `${i * 80}ms` }}
              >
                <div
                  className="w-11 h-11 rounded-xl mb-5 flex items-center justify-center"
                  style={{
                    background: isHighlight ? "rgba(255,255,255,0.16)" : `${c.accent}14`,
                  }}
                >
                  <Icon size={20} style={{ color: isHighlight ? "#fff" : c.accent }} />
                </div>
                <p
                  className="text-[12px] font-semibold tracking-[0.14em] uppercase"
                  style={{ color: isHighlight ? "rgba(255,255,255,0.8)" : "#0A1628A0" }}
                >
                  {c.label}
                </p>
                <div className="mt-2 flex items-baseline gap-1.5">
                  <span className="text-[32px] font-bold tracking-tight">{c.price}</span>
                  <span className={`text-[13px] ${isHighlight ? "text-white/75" : "text-[#0A1628]/55"}`}>
                    {c.priceSuffix}
                  </span>
                </div>
                <p className={`mt-3 text-[14px] leading-relaxed ${isHighlight ? "text-white/85" : "text-[#0A1628]/70"}`}>
                  {c.line}
                </p>
              </article>
            );
          })}
        </div>

        <div className="mt-10 flex justify-center zy-reveal">
          <Link
            to="/pricing"
            data-testid="home-pricing-brief-cta"
            className="inline-flex items-center gap-2 rounded-full bg-[#0A1628] text-white px-6 py-3 text-[14px] font-semibold hover:opacity-90 transition-opacity"
          >
            See full pricing & compare tiers <ArrowRight size={15} />
          </Link>
        </div>
      </div>
    </section>
  );
}
