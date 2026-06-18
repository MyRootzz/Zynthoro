import { ArrowRight, Play } from "lucide-react";
import { HOME } from "@/constants/testIds";
import { usePresaleDialog } from "@/components/sections/PresaleDialog";

export default function Hero() {
  const { openDialog } = usePresaleDialog();

  const scrollToDomains = () => {
    const el = document.getElementById("domains");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section
      id="top"
      data-testid={HOME.hero}
      className="relative overflow-hidden"
      style={{ paddingTop: 140, paddingBottom: 140 }}
    >
      <div className="zy-hero-bg" aria-hidden="true">
        <div className="zy-hero-grid" />
        <div className="zy-hero-orb zy-hero-orb-a" />
        <div className="zy-hero-orb zy-hero-orb-b" />
      </div>

      <div className="zy-container relative">
        <div className="max-w-4xl mx-auto text-center">
          <div className="zy-badge zy-reveal" style={{ transitionDelay: "0ms" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-[#1A4FFF]" />
            Powered by Anthropic Claude AI
          </div>

          <h1
            data-testid={HOME.heroHeadline}
            className="zy-h1 mt-6 zy-reveal"
            style={{ transitionDelay: "80ms" }}
          >
            The Next-Gen <span style={{ color: "var(--zy-blue)" }}>AI ERP</span> Ecosystem
          </h1>

          <p
            data-testid={HOME.heroSubheadline}
            className="zy-body mt-7 max-w-2xl mx-auto zy-reveal"
            style={{ transitionDelay: "160ms" }}
          >
            One platform. One AI. One truth. Replace 15+ tools with Zynthoro.
          </p>

          <div
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 zy-reveal"
            style={{ transitionDelay: "240ms" }}
          >
            <button
              data-testid={HOME.heroPrimaryCta}
              onClick={openDialog}
              className="zy-btn-primary"
            >
              Claim Your Presale Spot
              <ArrowRight size={18} />
            </button>
            <button
              data-testid={HOME.heroSecondaryCta}
              onClick={scrollToDomains}
              className="zy-btn-outline"
            >
              <Play size={16} />
              Watch Demo
            </button>
          </div>

          <p className="mt-7 text-sm text-[#666] zy-reveal" style={{ transitionDelay: "320ms" }}>
            Founding member pricing locked for life · No risk · Cancel anytime
          </p>
        </div>
      </div>
    </section>
  );
}
