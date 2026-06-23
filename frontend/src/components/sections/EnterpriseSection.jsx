import { useState } from "react";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@/components/ui/accordion";
import { Checkbox } from "@/components/ui/checkbox";
import { Check, Mail, Layers, ArrowRight } from "lucide-react";
import { usePresaleDialog } from "@/components/sections/PresaleDialog";

const TIERS = [
  {
    key: "basic",
    name: "Enterprise Basic",
    price: "€2,499",
    pricePerMonth: true,
    scope: "1 company workspace · 1 TB storage",
    features: [
      "All 12 domains · full ERP",
      "Unlimited users",
      "SSO (Google / Microsoft)",
      "Security policies & audit trail",
      "14 exclusive enterprise modules",
    ],
    accent: "blue",
  },
  {
    key: "plus",
    name: "Enterprise Plus",
    price: "€3,999",
    pricePerMonth: true,
    scope: "3 company workspaces · 3 TB storage",
    features: [
      "Everything in Basic",
      "Custom roles & dashboards",
      "Priority support",
      "IP restrictions",
    ],
    accent: "blue",
  },
  {
    key: "advanced",
    name: "Enterprise Advanced",
    price: "€5,999",
    pricePerMonth: true,
    scope: "10 company workspaces · 10 TB storage",
    features: [
      "Everything in Plus",
      "Multi-tenant management",
      "Advanced audit trail",
      "5× API limits",
      "24/7 support",
    ],
    accent: "blue",
  },
  {
    key: "elite",
    name: "Enterprise Elite",
    price: "Contact us",
    contact: true,
    scope: "Unlimited companies · Unlimited storage",
    features: [
      "Dedicated account manager",
      "Custom AI models",
      "Private cloud",
      "SLA 99.99%",
    ],
    accent: "gold",
  },
  {
    key: "unlimited",
    name: "Enterprise Unlimited",
    price: "Contact us",
    contact: true,
    scope: "Dedicated servers · On-premise · Full white-label",
    features: [
      "Dedicated servers",
      "Custom workflows & modules",
      "On-premise option",
      "Full white-label",
    ],
    accent: "gold",
  },
];

const MODULES = [
  "Planning & Organisation",
  "Time Tracking",
  "Purchase Admin",
  "Sales Admin",
  "Accounting",
  "Invoicing & Finance",
  "Project Management",
  "HR & Personnel",
  "Operations & Processes",
  "Marketing & Content (incl. Video & Design)",
  "Communication & Collaboration",
  "Compliance & Security",
];

export default function EnterpriseSection() {
  const { openDialog } = usePresaleDialog();
  const [selected, setSelected] = useState(() => MODULES.map((m) => m)); // all selected by default

  const toggle = (m) =>
    setSelected((s) => (s.includes(m) ? s.filter((x) => x !== m) : [...s, m]));

  const fullSuite = selected.length === MODULES.length;

  return (
    <section
      id="enterprise"
      data-testid="section-enterprise"
      className="zy-section relative"
      style={{ background: "#FAFAFB" }}
    >
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-14 zy-reveal">
          <p className="zy-eyebrow mb-4" style={{ color: "#8a6e1d" }}>Enterprise</p>
          <h2 className="zy-h2">Built for scale</h2>
          <p className="zy-body mt-5">
            Normally €10,000–€35,000/month across separate ERP, CRM and HR systems. Zynthoro Enterprise delivers everything from €2,499/month.
          </p>
        </div>

        {/* Tier accordion */}
        <div className="max-w-3xl mx-auto zy-reveal">
          <Accordion type="single" collapsible className="space-y-3" data-testid="enterprise-accordion">
            {TIERS.map((t) => {
              const isGold = t.accent === "gold";
              return (
                <AccordionItem
                  key={t.key}
                  value={t.key}
                  className="rounded-xl bg-white border data-[state=open]:shadow-md transition-shadow"
                  style={{
                    borderColor: isGold ? "#D4AF37" : "#eee",
                    borderWidth: isGold ? 1.5 : 1,
                  }}
                >
                  <AccordionTrigger
                    className="px-5 py-4 hover:no-underline group"
                    data-testid={`enterprise-tier-${t.key}`}
                  >
                    <div className="flex-1 flex items-center justify-between gap-3">
                      <div className="text-left">
                        <p
                          className="text-[15.5px] font-bold tracking-tight"
                          style={{ color: isGold ? "#8a6e1d" : "#000" }}
                        >
                          {t.name}
                        </p>
                        <p className="text-[12.5px] text-[#666] mt-0.5">{t.scope}</p>
                      </div>
                      <div className="text-right shrink-0">
                        {t.contact ? (
                          <span
                            className="text-[12.5px] font-semibold tracking-wide uppercase"
                            style={{ color: "#8a6e1d" }}
                          >
                            Contact us
                          </span>
                        ) : (
                          <span className="text-[18px] font-bold tracking-tight text-black">
                            {t.price}
                            <span className="text-[12px] text-[#666] font-normal ml-0.5">/mo</span>
                          </span>
                        )}
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-5 pb-5 pt-1">
                    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1">
                      {t.features.map((f) => (
                        <li key={f} className="flex items-start gap-2 text-[13.5px] text-[#333]">
                          <Check
                            size={14}
                            className="mt-0.5 shrink-0"
                            style={{ color: isGold ? "#D4AF37" : "#1A4FFF" }}
                          />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                    <div className="mt-5">
                      {t.contact ? (
                        <a
                          href="mailto:enterprise@zynthoro.ai"
                          className="zy-btn-gold inline-flex"
                          data-testid={`enterprise-contact-${t.key}`}
                        >
                          <Mail size={15} /> Contact us for pricing
                        </a>
                      ) : (
                        <button
                          onClick={openDialog}
                          className="zy-btn-primary"
                          data-testid={`enterprise-claim-${t.key}`}
                        >
                          Claim Presale Spot <ArrowRight size={15} />
                        </button>
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </div>

        {/* Module discovery tool */}
        <div
          className="mt-20 max-w-5xl mx-auto bg-white border rounded-2xl p-6 sm:p-8 zy-reveal"
          style={{ borderColor: "#D4AF37" }}
          data-testid="enterprise-calculator"
        >
          <div className="flex items-center gap-2 mb-1.5">
            <Layers size={16} style={{ color: "#1A4FFF" }} />
            <p className="zy-eyebrow" style={{ fontSize: 11 }}>What you need · what&apos;s included</p>
          </div>
          <h3 className="text-[22px] sm:text-[26px] font-bold tracking-tight">
            Pick the modules you need — all 12 are included.
          </h3>
          <p className="text-[14px] text-[#555] mt-2 max-w-2xl">
            Tick the modules your business depends on. Whatever you choose, <b>Enterprise Basic includes all 12 modules from €2,499/month</b> — there&apos;s nothing to add on later.
          </p>

          <div className="mt-7 grid grid-cols-1 md:grid-cols-3 gap-7">
            <div className="md:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {MODULES.map((m) => {
                const checked = selected.includes(m);
                return (
                  <label
                    key={m}
                    className="flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors"
                    style={{
                      borderColor: checked ? "#1A4FFF" : "#eee",
                      background: checked ? "rgba(26,79,255,0.04)" : "#fff",
                    }}
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={() => toggle(m)}
                      data-testid={`module-${m.toLowerCase().replace(/[^a-z]+/g, "-")}`}
                    />
                    <span className="text-[13.5px] font-medium text-black">{m}</span>
                  </label>
                );
              })}
            </div>

            <aside
              className="rounded-xl p-5 self-start"
              style={{
                background: "linear-gradient(180deg, rgba(26,79,255,0.04), rgba(212,175,55,0.06))",
                border: "1px solid #eee",
              }}
            >
              <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[#666]">
                Your selection
              </p>
              <p
                className="mt-2 text-[20px] font-bold tracking-tight text-black"
                style={{ fontVariantNumeric: "tabular-nums" }}
                data-testid="calculator-selection-summary"
              >
                {selected.length}/{MODULES.length} modules
                {fullSuite && (
                  <span
                    className="ml-2 align-middle text-[10.5px] font-bold tracking-wide uppercase px-2 py-0.5 rounded-full"
                    style={{ background: "rgba(212,175,55,0.18)", color: "#8a6e1d" }}
                  >
                    Full suite
                  </span>
                )}
              </p>

              <div
                className="mt-4 rounded-lg p-3.5"
                style={{ background: "#fff", border: "1px dashed #D4AF37" }}
              >
                <p
                  className="text-[13.5px] font-semibold leading-snug"
                  style={{ color: "#1a1300" }}
                  data-testid="calculator-message"
                >
                  All 12 modules included from <span style={{ color: "#8a6e1d" }}>€2,499/month</span>.
                </p>
                <p className="text-[12.5px] text-[#555] mt-1.5">
                  Your selected modules are all part of Enterprise Basic — no per-module pricing, no add-ons.
                </p>
              </div>

              <a
                href="mailto:enterprise@zynthoro.ai?subject=Zynthoro%20Enterprise%20demo%20request"
                className="zy-btn-primary w-full mt-5 inline-flex"
                data-testid="calculator-demo-cta"
              >
                Request a demo <ArrowRight size={15} />
              </a>
              <p className="mt-3 text-[11.5px] text-[#888] leading-relaxed">
                We&apos;ll walk through your selection plus the 14 enterprise modules and SSO, audit trail and SLA options.
              </p>
            </aside>
          </div>
        </div>
      </div>
    </section>
  );
}
