import { Check, ArrowRight } from "lucide-react";
import { HOME } from "@/constants/testIds";
import { usePresaleDialog } from "@/components/sections/PresaleDialog";

const plans = [
  {
    name: "Starter",
    price: "€499",
    suffix: "/mo",
    desc: "For solo founders and small teams getting started.",
    features: ["All 12 domains (essentials)", "1 workspace, up to 3 users", "Zynthoro Assist (basic)", "EU hosting & GDPR"],
    cta: "Start Free Trial",
  },
  {
    name: "Business",
    price: "€899",
    suffix: "/mo",
    desc: "The most popular plan for growing SMEs.",
    features: ["Everything in Starter", "Up to 15 users", "Full AI automations", "Priority support"],
    cta: "Start Free Trial",
    popular: true,
  },
  {
    name: "Agency",
    price: "€1,199",
    suffix: "/mo",
    desc: "For agencies managing multiple clients.",
    features: ["Everything in Business", "Multi-client workspaces", "White-label invoices", "API access"],
    cta: "Start Free Trial",
  },
  {
    name: "Enterprise",
    price: "from €2,499",
    suffix: "/mo",
    desc: "For organisations with advanced needs.",
    features: ["Unlimited users", "Dedicated AI tuning", "SSO + custom roles", "SLA & onboarding"],
    cta: "Talk to Sales",
    enterprise: true,
  },
];

export default function Pricing() {
  const { openDialog } = usePresaleDialog();
  return (
    <section id="pricing" data-testid={HOME.pricing} className="zy-section bg-white">
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-16 zy-reveal">
          <p className="zy-eyebrow mb-4">Pricing</p>
          <h2 className="zy-h2">Simple, transparent pricing. No surprises.</h2>
          <p className="zy-body mt-5">
            Founding member pricing locked for life when you join the presale.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {plans.map((p, i) => (
            <div
              key={p.name}
              data-testid={`pricing-card-${p.name.toLowerCase()}`}
              className={`zy-price-card zy-reveal ${p.popular ? "popular" : ""} ${p.enterprise ? "enterprise" : ""}`}
              style={{ transitionDelay: `${i * 80}ms` }}
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
                <span className="text-[34px] font-bold tracking-tight text-black">{p.price}</span>
                <span className="text-[#666] text-[15px]">{p.suffix}</span>
              </div>
              <p className="text-[14px] text-[#555] mt-2 leading-relaxed">{p.desc}</p>

              <ul className="mt-6 space-y-3 flex-1">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-[14px] text-[#333]">
                    <Check size={16} className="mt-0.5 shrink-0" style={{ color: "var(--zy-blue)" }} />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={openDialog}
                className={p.enterprise ? "zy-btn-gold mt-7 w-full" : "zy-btn-primary mt-7 w-full"}
              >
                {p.cta}
              </button>
            </div>
          ))}
        </div>

        <div className="mt-12 text-center zy-reveal">
          <a href="#presale" className="zy-link">
            See all plans <ArrowRight size={16} />
          </a>
        </div>
      </div>
    </section>
  );
}
