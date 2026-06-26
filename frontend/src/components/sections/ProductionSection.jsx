import { Factory, ClipboardList, Boxes, ShieldCheck, ScanLine, BarChart3, ArrowRight } from "lucide-react";
import { HOME } from "@/constants/testIds";

const FEATURES = [
  { icon: ClipboardList, title: "Recipes & formulas",   desc: "AI-suggested optimisation, allergen tracking, automatic cost-per-unit roll-up." },
  { icon: Boxes,         title: "Multi-level BOM",      desc: "Raw → semi-finished → finished. Versioned, with cost roll-up at every level." },
  { icon: Factory,       title: "Production planning",  desc: "Orders, capacity planning, schedule calendar — synced to inventory and finance." },
  { icon: ShieldCheck,   title: "Quality control",      desc: "Per-batch checklists, pass/fail, non-conformance reports and AI trend analysis." },
  { icon: ScanLine,      title: "Full traceability",    desc: "Lot numbers, expiry tracking and one-click recall across the entire supply chain." },
  { icon: BarChart3,     title: "Production costs",     desc: "Labour + materials + overhead → real margin per product, real-time." },
];

const INDUSTRIES = [
  { tag: "Food & beverage" },
  { tag: "Cosmetics" },
  { tag: "Pharma & supplements" },
  { tag: "Light manufacturing" },
];

export default function ProductionSection() {
  return (
    <section
      id="production"
      data-testid={HOME.production || "home-production"}
      className="zy-section"
      style={{ background: "#fff" }}
    >
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-14 zy-reveal">
          <p className="zy-eyebrow mb-4" style={{ color: "#1A4FFF" }}>Operations & Production</p>
          <h2 className="zy-h2">Replace SAP & Oracle for <span style={{ color: "#1A4FFF" }}>€899/month</span></h2>
          <p className="zy-body mt-5">
            Recipes, BOMs, work orders, quality checks and full lot traceability — the entire production stack, built for SMEs in food, cosmetics, pharma and light manufacturing.
          </p>
          <div className="flex flex-wrap justify-center gap-2 mt-6">
            {INDUSTRIES.map((i) => (
              <span
                key={i.tag}
                className="inline-flex items-center px-3 py-1.5 rounded-full text-[12px] font-semibold"
                style={{ background: "#EAF0FF", color: "#1A4FFF" }}
              >
                {i.tag}
              </span>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="zy-reveal p-6 rounded-2xl border bg-white hover:border-[#1A4FFF] transition-colors"
                style={{ borderColor: "#eee", animationDelay: `${i * 40}ms` }}
              >
                <span
                  className="inline-flex items-center justify-center w-11 h-11 rounded-xl mb-4"
                  style={{ background: "#EAF0FF" }}
                >
                  <Icon size={20} style={{ color: "#1A4FFF" }} />
                </span>
                <h3 className="text-[16px] font-bold tracking-tight mb-1.5">{f.title}</h3>
                <p className="text-[13.5px] text-[#555] leading-relaxed">{f.desc}</p>
              </div>
            );
          })}
        </div>

        <div className="mt-12 text-center zy-reveal">
          <a
            href="#pricing"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-md font-semibold text-white"
            style={{ background: "#1A4FFF" }}
            data-testid="production-cta"
          >
            See Business plan — €899/mo <ArrowRight size={16} />
          </a>
          <p className="text-[12px] text-[#888] mt-3">Includes recipes, production orders and work orders. Full BOM + QC from Agency. Full traceability from Enterprise.</p>
        </div>
      </div>
    </section>
  );
}
