import { Link } from "react-router-dom";
import { ArrowRight, Play } from "lucide-react";
import { HOME } from "@/constants/testIds";

// Zynthoro product walkthrough on YouTube. Opens in a new tab so we don't
// rely on YouTube's embed policy (some videos disable iframe embeds).
const DEMO_VIDEO_URL =
  process.env.REACT_APP_DEMO_VIDEO_URL ||
  "https://www.youtube.com/watch?v=_5psEgtULpg";

export default function Hero() {
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
            <Link
              to="/signup"
              data-testid={HOME.heroPrimaryCta}
              className="zy-btn-primary"
            >
              Get started
              <ArrowRight size={18} />
            </Link>
            <a
              href={DEMO_VIDEO_URL}
              target="_blank"
              rel="noopener noreferrer"
              data-testid={HOME.heroSecondaryCta}
              className="zy-btn-outline"
              aria-label="Watch the Zynthoro product demo on YouTube"
            >
              <Play size={16} />
              Watch Demo
            </a>
          </div>

          <p className="mt-7 text-sm text-[#666] zy-reveal" style={{ transitionDelay: "320ms" }}>
            Starting at €499/month · No risk · Cancel anytime
          </p>
        </div>
      </div>
    </section>
  );
}
